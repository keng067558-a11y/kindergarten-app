import streamlit as st
import pandas as pd
from datetime import date
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 設定 ---
SHEET_NAME = 'kindergarten_db'

# --- 連線設定 ---
def connect_to_gsheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

# --- 讀取資料 ---
def load_data():
    try:
        sheet = connect_to_gsheets()
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 確保欄位順序與存在
        expected_cols = ['聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊']
        
        if df.empty:
            return pd.DataFrame(columns=expected_cols)
        
        # 如果 Google Sheet 裡原本沒有「聯繫狀態」，幫它補上預設值
        if '聯繫狀態' not in df.columns:
            df['聯繫狀態'] = '未聯繫'
            
        # 為了讓 App 顯示勾選框，我們把 "已聯繫" 轉成 True，其他轉成 False
        df['已聯繫'] = df['聯繫狀態'] == '已聯繫'
        
        # 調整欄位顯示順序 (把勾選框放到最前面)
        cols_order = ['已聯繫'] + [c for c in expected_cols if c != '聯繫狀態']
        return df[cols_order]
        
    except Exception as e:
        st.error(f"無法讀取資料，請確認 Google Sheet 是否已新增「聯繫狀態」欄位。錯誤: {e}")
        return pd.DataFrame()

# --- [核心功能] 同步所有變更回 Google Sheet ---
def sync_data_to_gsheets(new_df):
    try:
        sheet = connect_to_gsheets()
        
        # 1. 處理資料格式：把 App 上的 True/False 轉回文字 "已聯繫"/"未聯繫"
        save_df = new_df.copy()
        save_df['聯繫狀態'] = save_df['已聯繫'].apply(lambda x: '已聯繫' if x else '未聯繫')
        
        # 2. 移除暫時用的 Boolean 欄位
        save_df = save_df.drop(columns=['已聯繫'])
        
        # 3. 確保欄位順序正確
        final_cols = ['登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '聯繫狀態']
        save_df = save_df[final_cols]
        
        # 4. 全表更新 (Clear -> Update)
        sheet.clear() # 清空舊資料
        # 寫入標題
        sheet.append_row(final_cols)
        # 寫入內容 (如果有的話)
        if not save_df.empty:
            # gspread 需要 list of lists
            sheet.append_rows(save_df.values.tolist())
            
        return True
    except Exception as e:
        st.error(f"儲存失敗: {e}")
        return False

# --- 工具函式 ---
def roc_date_input(label, default_date=None):
    st.markdown(f"**{label}**")
    c1, c2, c3 = st.columns([1, 1, 1])
    if default_date is None: default_date = date.today()
    roc_year = c1.number_input("民國(年)", 100, 120, default_date.year - 1911)
    month = c2.selectbox("月", range(1, 13), index=default_date.month-1)
    day = c3.selectbox("日", range(1, 32), index=default_date.day-1)
    try: return date(roc_year + 1911, month, day)
    except: return date.today()

def to_roc_str(d):
    return f"{d.year-1911}/{d.month:02d}/{d.day:02d}"

def calculate_admission_roadmap(dob):
    today = date.today()
    current_roc = today.year - 1911
    if today.month < 8: current_roc -= 1
    offset = 1 if (dob.month > 9) or (dob.month == 9 and dob.day >= 2) else 0
    roadmap = []
    for i in range(4):
        target = current_roc + i
        age = target - (dob.year - 1911) - offset
        if age == 2: grade = "幼幼班"
        elif age == 3: grade = "小班"
        elif age == 4: grade = "中班"
        elif age == 5: grade = "大班"
        elif age < 2: grade = "托嬰中心"
        else: grade = "畢業/超齡"
        if "畢業" not in grade:
            roadmap.append(f"{target} 學年 - {grade} (民國 {target} 年 8 月入學)")
    return roadmap

# ==================== 介面開始 ====================
st.set_page_config(page_title="幼兒園新生管理", layout="wide")
st.title("☁️ 雲端幼兒園新生管理系統")

# 每次重新整理都重新讀取最新資料
if 'df_cache' not in st.session_state:
    st.session_state.df_cache = load_data()

tab1, tab2 = st.tabs(["➕ 新增報名", "✏️ 管理列表 (勾選/刪除)"])

# --- 分頁 1: 新增 ---
with tab1:
    col_main, col_roadmap = st.columns([1, 1])
    
    with col_main:
        st.subheader("輸入資料")
        child_name = st.text_input("幼兒姓名")
        dob = roc_date_input("幼兒生日", date(2021, 9, 2))
        c1, c2 = st.columns(2)
        p_name = c1.text_input("家長姓氏")
        p_title = c2.selectbox("稱謂", ["先生", "小姐", "爸爸", "媽媽"])
        phone = st.text_input("聯絡電話")

    with col_roadmap:
        st.subheader("入學判定")
        options = calculate_admission_roadmap(dob)
        if options:
            st.info("可登記入學時間：")
            selected_plan = st.radio("請選擇一個方案", options)
        else:
            st.warning("年齡不符，無法排程")
            selected_plan = "不符資格"

    if st.button("提交並儲存", type="primary"):
        if child_name and p_name and phone and selected_plan != "不符資格":
            # 先讀取最新的資料
            current_df = load_data()
            
            # 建立新的一筆 (注意欄位要對應)
            new_row = pd.DataFrame([{
                '已聯繫': False, # 預設未聯繫
                '登記日期': to_roc_str(date.today()),
                '幼兒姓名': child_name,
                '家長稱呼': f"{p_name} {p_title}",
                '電話': phone,
                '幼兒生日': to_roc_str(dob),
                '預計入學資訊': selected_plan
            }])
            
            # 合併並存回雲端
            updated_df = pd.concat([current_df, new_row], ignore_index=True)
            if sync_data_to_gsheets(updated_df):
                st.success("✅ 資料已新增！")
                st.session_state.df_cache = load_data() # 更新快取
                st.rerun()
        else:
            st.error("資料不完整")

# --- 分頁 2: 管理與刪除 (新功能) ---
with tab2:
    st.subheader("📋 報名資料管理")
    st.caption("💡 提示：您可以直接在表格上勾選「已聯繫」，或選取多人進行刪除，最後記得按「儲存變更」。")

    # 1. 顯示可編輯的表格 (Data Editor)
    # df_cache 是我們暫存的資料
    edit_df = st.data_editor(
        st.session_state.df_cache,
        column_config={
            "已聯繫": st.column_config.CheckboxColumn(
                "已聯繫?",
                help="勾選表示已聯繫家長",
                default=False,
            ),
            "預計入學資訊": st.column_config.TextColumn("預計入學資訊", width="medium"),
        },
        disabled=["登記日期", "幼兒姓名", "電話"], # 禁止修改這幾欄，怕亂掉
        hide_index=True,
        use_container_width=True,
        key="editor"
    )

    st.divider()
    
    col_del, col_save = st.columns([2, 1])

    # 2. 多選刪除功能
    with col_del:
        st.write("🗑️ **批次刪除**")
        # 製作一個選單，顯示姓名+電話
        if not edit_df.empty:
            options = edit_df.apply(lambda x: f"{x['幼兒姓名']} ({x['電話']})", axis=1).tolist()
            delete_list = st.multiselect("選擇要刪除的資料 (可多選)", options)
        else:
            delete_list = []

    # 3. 儲存按鈕
    with col_save:
        st.write("💾 **儲存所有變更**")
        if st.button("確認執行修改與刪除", type="primary"):
            # A. 處理刪除：過濾掉被選中的人
            final_df = edit_df.copy()
            if delete_list:
                # 找出要保留的資料 (不在刪除清單裡的)
                # 我們重建識別字串來比對
                final_df['id_temp'] = final_df.apply(lambda x: f"{x['幼兒姓名']} ({x['電話']})", axis=1)
                final_df = final_df[~final_df['id_temp'].isin(delete_list)]
                # 刪掉暫時用的欄位
                final_df = final_df.drop(columns=['id_temp'])
            
            # B. 執行同步回 Google Sheet
            if sync_data_to_gsheets(final_df):
                st.success("✅ 所有變更已儲存！(狀態更新 + 刪除執行)")
                st.session_state.df_cache = load_data() # 重新讀取確保一致
                st.rerun()
