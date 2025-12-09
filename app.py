import streamlit as st
import pandas as pd
from datetime import date, datetime
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 🔒 安全鎖
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if not st.session_state.password_correct:
        st.title("🔒 請登入新生管理系統")
        password = st.text_input("請輸入通關密碼", type="password")
        if st.button("登入"):
            if password == "1234": 
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
STUDENT_CSV = 'students.csv'

# 快取 Resource：連線物件不用一直重連
@st.cache_resource
def get_gsheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def connect_to_gsheets():
    client = get_gsheet_client()
    return client.open(SHEET_NAME).sheet1

# 快取 Data：資料讀取後暫存 60 秒，或直到我們手動清除
@st.cache_data(ttl=60)
def load_registered_data():
    try:
        sheet = connect_to_gsheets()
        data = sheet.get_all_values()
        if not data: return pd.DataFrame()
        
        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        
        if '電話' in df.columns:
            df['電話'] = df['電話'].astype(str).str.strip()
            df['電話'] = df['電話'].apply(lambda x: '0' + x if len(x) == 9 and x.startswith('9') else x)
            
        return df
    except Exception as e:
        return pd.DataFrame()

def load_current_students():
    try:
        return pd.read_csv(STUDENT_CSV)
    except:
        return pd.DataFrame(columns=['姓名', '出生年月日', '目前班級'])

def sync_data_to_gsheets(new_df):
    try:
        sheet = connect_to_gsheets()
        save_df = new_df.copy()
        
        if '已聯繫' in save_df.columns:
            save_df['聯繫狀態'] = save_df['已聯繫'].apply(lambda x: '已聯繫' if x is True else '未聯繫')
            save_df = save_df.drop(columns=['已聯繫'])
        
        final_cols = ['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註']
        
        for col in final_cols:
            if col not in save_df.columns: save_df[col] = ""
            
        save_df = save_df[final_cols]
        save_df = save_df.astype(str)
        
        sheet.clear()
        sheet.append_row(final_cols)
        if not save_df.empty:
            sheet.append_rows(save_df.values.tolist())
            
        # 關鍵：儲存成功後，清除快取，這樣下次讀取才會是新的
        load_registered_data.clear()
        return True
    except Exception as e:
        st.error(f"儲存失敗: {e}")
        return False

# ==========================================
# 🧠 核心邏輯
# ==========================================
# [修改] 完全改成下拉選單 (Selectbox)，不用打字
def roc_date_input(label, default_date=None, key_suffix=""):
    st.markdown(f"**{label}**")
    c1, c2, c3 = st.columns([1, 1, 1])
    if default_date is None: default_date = date.today()
    
    # 年份選單：民國 100 ~ 120 年
    roc_year = c1.selectbox("民國(年)", range(100, 121), index=(default_date.year - 1911) - 100, key=f"y{key_suffix}")
    # 月份選單
    month = c2.selectbox("月", range(1, 13), index=default_date.month-1, key=f"m{key_suffix}")
    # 日期選單
    day = c3.selectbox("日", range(1, 32), index=default_date.day-1, key=f"d{key_suffix}")
    
    try: return date(roc_year + 1911, month, day)
    except: return date.today()

def to_roc_str(d):
    return f"{d.year-1911}/{d.month:02d}/{d.day:02d}"

def get_grade_for_year(birth_date, target_roc_year):
    if birth_date is None: return "未知"
    birth_year_roc = birth_date.year - 1911
    offset = 1 if (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2) else 0
    age = target_roc_year - birth_year_roc - offset
    if age < 2: return "托嬰中心"
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
            roadmap.append(f"{target} 學年 - {grade}")
    return roadmap

# ==========================================
# 📱 APP 介面
# ==========================================
st.set_page_config(page_title="新生管理系統", layout="wide")
st.title("🏫 新生管理系統")

menu = st.sidebar.radio("系統切換", ["👶 新生報名管理", "👩‍🏫 師生人力預估系統"])

if menu == "👶 新生報名管理":
    # 初始化 Session State (用於多寶暫存)
    if 'temp_children' not in st.session_state:
        st.session_state.temp_children = []

    # 讀取資料 (現在會使用快取，速度變快)
    df = load_registered_data()
    
    if not df.empty and '聯繫狀態' not in df.columns: df['聯繫狀態'] = '未聯繫'
    if not df.empty and '報名狀態' not in df.columns: df['報名狀態'] = '排隊候補'
    if not df.empty:
        df['已聯繫'] = df['聯繫狀態'].apply(lambda x: True if str(x).strip() == '已聯繫' else False)

    tab1, tab2, tab3 = st.tabs(["➕ 新增報名 (多寶模式)", "📂 新生資料庫", "📅 未來入學名單預覽"])

    # --- Tab 1: 新增 (改版：支援多寶) ---
    with tab1:
        st.subheader("第一步：填寫家長資料 (共用)")
        c_p1, c_p2, c_p3 = st.columns([2, 1, 2])
        p_name = c_p1.text_input("家長姓氏 (必填)", key="input_p_name")
        p_title = c_p2.selectbox("稱謂", ["先生", "小姐", "爸爸", "媽媽"], key="input_p_title")
        phone = c_p3.text_input("聯絡電話 (必填)", key="input_phone")
        referrer = st.text_input("推薦人 (選填)", key="input_referrer")
        
        st.divider()
        st.subheader("第二步：新增幼兒 (可加入多位)")
        
        c_k1, c_k2 = st.columns([1, 2])
        with c_k1:
            # 幼兒姓名
            child_name = st.text_input("幼兒姓名 (選填)", key="input_c_name")
            # 生日 (全下拉選單)
            dob = roc_date_input("幼兒出生年月日", date(2021, 9, 2), key_suffix="_add")
        
        with c_k2:
            status = st.selectbox("報名狀態", ["排隊候補", "已確認/已繳費", "考慮中/參觀"], key="input_status")
            note = st.text_area("備註事項", placeholder="例如：雙胞胎哥哥、過敏...", height=100, key="input_note")

        if st.button("⬇️ 加入暫存清單 (還有下一位)", type="secondary"):
            # 加入前先計算入學年段
            auto_plans = calculate_admission_roadmap(dob)
            auto_plan = auto_plans[0] if auto_plans else "年齡不符/待確認"
            
            # 加到 Session State
            st.session_state.temp_children.append({
                "幼兒姓名": child_name if child_name else "(未填)",
                "幼兒生日": to_roc_str(dob),
                "報名狀態": status,
                "預計入學資訊": auto_plan,
                "備註": note
            })
            st.success("已加入一位幼兒，請繼續填寫下一位，或按下方按鈕送出。")

        # 顯示目前暫存的清單
        if st.session_state.temp_children:
            st.markdown("##### 🛒 準備送出的名單：")
            st.table(pd.DataFrame(st.session_state.temp_children))
            
            if st.button("✅ 確認送出所有資料 (結束)", type="primary"):
                if p_name and phone:
                    current_df = load_registered_data()
                    new_rows = []
                    
                    for child in st.session_state.temp_children:
                        new_rows.append({
                            '報名狀態': child['報名狀態'],
                            '已聯繫': False,
                            '登記日期': to_roc_str(date.today()),
                            '幼兒姓名': child['幼兒姓名'] if child['幼兒姓名'] != "(未填)" else "",
                            '家長稱呼': f"{p_name} {p_title}",
                            '電話': str(phone), 
                            '幼兒生日': child['幼兒生日'],
                            '預計入學資訊': child['預計入學資訊'],
                            '推薦人': referrer,
                            '備註': child['備註']
                        })
                    
                    new_df_chunk = pd.DataFrame(new_rows)
                    updated_df = pd.concat([current_df, new_df_chunk], ignore_index=True)
                    
                    if sync_data_to_gsheets(updated_df):
                        st.balloons()
                        s
