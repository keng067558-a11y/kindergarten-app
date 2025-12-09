import streamlit as st
import pandas as pd
from datetime import date, datetime
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 🔒 安全鎖：登入系統
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if not st.session_state.password_correct:
        st.title("🔒 請登入新生管理系統")
        password = st.text_input("請輸入通關密碼", type="password")
        if st.button("登入"):
            if password == "1234":  # 修改這裡設定您的密碼
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("密碼錯誤")
        return False
    return True

if not check_password():
    st.stop()

# ==========================================
# ⚙️ 設定與連線
# ==========================================
SHEET_NAME = 'kindergarten_db'
STUDENT_CSV = 'students.csv' # 假設舊生資料還是在 CSV，未來可整合

def connect_to_gsheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def load_registered_data():
    try:
        sheet = connect_to_gsheets()
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame()
        return df
    except:
        return pd.DataFrame()

def load_current_students():
    # 讀取目前在校生 (CSV)
    try:
        return pd.read_csv(STUDENT_CSV)
    except:
        return pd.DataFrame(columns=['姓名', '出生年月日', '目前班級'])

def sync_data_to_gsheets(new_df):
    try:
        sheet = connect_to_gsheets()
        save_df = new_df.copy()
        if '已聯繫' in save_df.columns:
            save_df['聯繫狀態'] = save_df['已聯繫'].apply(lambda x: '已聯繫' if x else '未聯繫')
            save_df = save_df.drop(columns=['已聯繫'])
        
        final_cols = ['登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '聯繫狀態']
        # 確保欄位存在，若無則補空
        for col in final_cols:
            if col not in save_df.columns: save_df[col] = ""
            
        save_df = save_df[final_cols]
        sheet.clear()
        sheet.append_row(final_cols)
        if not save_df.empty:
            sheet.append_rows(save_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"儲存失敗: {e}")
        return False

# ==========================================
# 🧠 核心邏輯：年級運算
# ==========================================
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

def parse_roc_date(date_str):
    try:
        parts = date_str.split('/')
        return date(int(parts[0])+1911, int(parts[1]), int(parts[2]))
    except:
        return None

def get_grade_for_year(birth_date, target_roc_year):
    """給定生日與目標民國年，算出當時讀什麼班"""
    if birth_date is None: return "未知"
    
    birth_year_roc = birth_date.year - 1911
    # 9/2 分界邏輯
    offset = 1 if (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2) else 0
    
    # 學齡 = 學年度 - 出生年 - offset
    age = target_roc_year - birth_year_roc - offset
    
    if age < 2: return "托嬰中心" # 0-1歲
    if age == 2: return "幼幼班"
    if age == 3: return "小班"
    if age == 4: return "中班"
    if age == 5: return "大班"
    return "畢業/超齡"

def calculate_admission_roadmap(dob):
    today = date.today()
    current_roc = today.year - 1911
    if today.month < 8: current_roc -= 1
    offset = 1 if (dob.month > 9) or (dob.month == 9 and dob.day >= 2) else 0
    roadmap = []
    for i in range(4): # 算未來4年
        target = current_roc + i
        age = target - (dob.year - 1911) - offset
        
        if age == 2: grade = "幼幼班"
        elif age == 3: grade = "小班"
        elif age == 4: grade = "中班"
        elif age == 5: grade = "大班"
        elif age < 2: grade = "托嬰中心"
        else: grade = "畢業/超齡"
        
        if "畢業" not in grade:
            # 修正顯示格式：入學年段
            roadmap.append(f"{target} 學年 - {grade}")
    return roadmap

# ==========================================
# 📱 APP 介面開始
# ==========================================
st.set_page_config(page_title="新生管理系統", layout="wide")
st.title("🏫 新生管理系統")

# 側邊選單
menu = st.sidebar.radio("系統切換", ["👶 新生報名管理", "👩‍🏫 師生人力預估系統"])

# ------------------------------------------
# 系統一：新生報名管理 (修正版)
# ------------------------------------------
if menu == "👶 新生報名管理":
    # 讀取資料
    if 'df_cache' not in st.session_state:
        st.session_state.df_cache = load_registered_data()
        
    # 資料前處理 (補欄位)
    df = st.session_state.df_cache
    if not df.empty and '聯繫狀態' not in df.columns:
        df['聯繫狀態'] = '未聯繫'
    if not df.empty:
        df['已聯繫'] = df['聯繫狀態'] == '已聯繫'

    tab1, tab2 = st.tabs(["➕ 新增報名", "✏️ 管理列表"])

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
            # 修正名稱：入學年段
            st.subheader("入學年段判定")
            options = calculate_admission_roadmap(dob)
            if options:
                st.info("家長預計登記之年段：")
                selected_plan = st.radio("請選擇方案", options)
            else:
                st.warning("年齡不符")
                selected_plan = "不符資格"

        if st.button("提交並儲存", type="primary"):
            if child_name and p_name and phone and selected_plan != "不符資格":
                current_df = load_registered_data()
                new_row = pd.DataFrame([{
                    '已聯繫': False,
                    '登記日期': to_roc_str(date.today()),
                    '幼兒姓名': child_name,
                    '家長稱呼': f"{p_name} {p_title}",
                    '電話': phone,
                    '幼兒生日': to_roc_str(dob),
                    '預計入學資訊': selected_plan
                }])
                updated_df = pd.concat([current_df, new_row], ignore_index=True)
                if sync_data_to_gsheets(updated_df):
                    st.success("✅ 資料已新增！")
                    st.session_state.df_cache = load_registered_data()
                    st.rerun()
            else:
                st.error("資料不完整")

    with tab2:
        st.subheader("📋 報名資料管理")
        if not df.empty:
            edit_df = st.data_editor(
                df,
                column_config={
                    "已聯繫": st.column_config.CheckboxColumn("已聯繫?", default=False),
                    "預計入學資訊": st.column_config.TextColumn("入學年段", width="medium"),
                },
                disabled=["登記日期", "幼兒姓名", "電話"],
                hide_index=True,
                use_container_width=True
            )
            
            col_del, col_save = st.columns([2, 1])
            with col_del:
                options = edit_df.apply(lambda x: f"{x['幼兒姓名']} ({x['電話']})", axis=1).tolist()
                delete_list = st.multiselect("批次刪除", options)
            
            with col_save:
                if st.button("確認執行修改與刪除", type="primary"):
                    final_df = edit_df.copy()
                    if delete_list:
                        final_df['id_temp'] = final_df.apply(lambda x: f"{x['幼兒姓名']} ({x['電話']})", axis=1)
                        final_df = final_df[~final_df['id_temp'].isin(delete_list)]
                        final_df = final_df.drop(columns=['id_temp'])
                    
                    if sync_data_to_gsheets(final_df):
                        st.success("✅ 儲存成功！")
                        st.session_state.df_cache = load_registered_data()
                        st.rerun()
        else:
            st.info("目前無資料")

# ------------------------------------------
# 系統二：師生人力預估系統 (全新功能)
# ------------------------------------------
elif menu == "👩‍🏫 師生人力預估系統":
    st.header("📊 未來學年師生人力預估")
    st.markdown("""
    此系統會整合 **「目前在校生(升級)」** 與 **「新生報名(加入)」** 的資料，
    自動推算未來各學年的學生總數，並依照 **幼照法** 計算所需老師人數。
    """)

    # 1. 設定參數 (幼照法規)
    with st.expander("⚙️ 師生比參數設定 (依照幼照法)", expanded=True):
        c1, c2, c3 = st.columns(3)
        ratio_daycare = c1.number_input("托嬰 (0-2歲)", value=5, help="法規通常 1:5")
        ratio_toddler = c2.number_input("幼幼 (2-3歲)", value=8, help="法規通常 1:8")
        ratio_normal = c3.number_input("小/中/大 (3-6歲)", value=15, help="法規通常 1:15")

    # 2. 載入所有資料
    df_current = load_current_students() # 舊生 (CSV)
    df_new = load_registered_data()      # 新生 (Google Sheet)

    # 3. 選擇要預估的學年
    today = date.today()
    this_roc_year = today.year - 1911
    if today.month < 8: this_roc_year -= 1
    
    target_years = st.multiselect(
        "請選擇要預估的學年", 
        [this_roc_year, this_roc_year+1, this_roc_year+2, this_roc_year+3],
        default=[this_roc_year+1] # 預設選明年
    )

    if target_years:
        st.divider()
        
        for year in sorted(target_years):
            st.subheader(f"📅 民國 {year} 學年度 (預估)")
            
            # --- 步驟 A: 統計人數 ---
            # 初始化計數器
            counts = {"托嬰中心": 0, "幼幼班": 0, "小班": 0, "中班": 0, "大班": 0}
            
            # A1. 舊生升級 (Rolling)
            if not df_current.empty:
                for _, row in df_current.iterrows():
                    # 假設 CSV 有 '出生年月日' (格式 YYYY-MM-DD 或 YYYY/MM/DD)
