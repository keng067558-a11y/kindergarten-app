import streamlit as st
import pandas as pd
from datetime import date
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 設定 ---
# 這是您的 Google 試算表名稱，請確保一定要跟雲端硬碟的一樣
SHEET_NAME = 'kindergarten_db'

# --- [核心] 連線 Google Sheets ---
def connect_to_gsheets():
    # 從 Streamlit Secrets 讀取鑰匙
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # 這裡會讀取您在 Streamlit 後台設定的 secrets
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

# --- [功能] 讀取資料 ---
def load_data():
    try:
        sheet = connect_to_gsheets()
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        # 確保欄位順序正確
        expected_cols = ['登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊']
        # 如果是空的表，回傳空 DataFrame
        if df.empty:
            return pd.DataFrame(columns=expected_cols)
        return df
    except Exception as e:
        st.error(f"無法讀取資料表，請檢查 Google Sheet 設定。錯誤: {e}")
        return pd.DataFrame()

# --- [功能] 新增資料 ---
def add_row_to_gsheets(row_data):
    sheet = connect_to_gsheets()
    sheet.append_row(row_data)

# --- [功能] 刪除資料 (根據姓名和電話) ---
def delete_row_from_gsheets(name, phone):
    sheet = connect_to_gsheets()
    # 尋找符合的列 (Row)
    cell = sheet.find(name)
    # 簡單防呆：確認該列的電話也相符才刪除，避免刪錯同名的人
    row_num = cell.row
    row_values = sheet.row_values(row_num)
    # row_values[3] 是電話欄位 (第4欄)
    if str(row_values[3]) == str(phone):
        sheet.delete_rows(row_num)
        return True
    return False

# --- 工具函式 (民國日期等) ---
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

# 1. 讀取 Google Sheet 資料
df = load_data()

tab1, tab2 = st.tabs(["➕ 新增報名", "🗑️ 管理與刪除"])

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

    if st.button("提交並儲存至雲端", type="primary"):
        if child_name and p_name and phone and selected_plan != "不符資格":
            row = [
                to_roc_str(date.today()),
                child_name,
                f"{p_name} {p_title}",
                phone,
                to_roc_str(dob),
                selected_plan
            ]
            add_row_to_gsheets(row)
            st.success("✅ 資料已安全儲存到 Google 試算表！")
            st.cache_data.clear() # 清除快取以顯示最新資料
            st.rerun()
        else:
            st.error("資料不完整")

# --- 分頁 2: 管理與刪除 ---
with tab2:
    st.subheader("📋 目前資料庫清單")
    st.dataframe(df, use_container_width=True)
    
    st.divider()
    st.subheader("🗑️ 刪除資料")
    st.write("請選擇要刪除的對象：")
    
    if not df.empty:
        # 製作一個選單，顯示 "姓名 - 電話" 避免刪錯人
        delete_options = df.apply(lambda x: f"{x['幼兒姓名']} (電話: {x['電話']})", axis=1).tolist()
        to_delete = st.selectbox("選擇刪除對象", delete_options)
        
        if st.button("確認刪除此筆資料"):
            # 解析出姓名和電話
            target_name = to_delete.split(" (電話: ")[0]
            target_phone = to_delete.split(" (電話: ")[1].replace(")", "")
            
            try:
                success = delete_row_from_gsheets(target_name, target_phone)
                if success:
                    st.success(f"已刪除 {target_name}")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("找不到相符資料，可能已被刪除")
            except Exception as e:
                st.error(f"刪除失敗: {e}")
    else:
        st.info("目前沒有資料可以刪除")
