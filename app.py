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
            
        load_registered_data.clear()
        return True
    except Exception as e:
        st.error(f"儲存失敗: {e}")
        return False

# ==========================================
# 🧠 核心邏輯
# ==========================================
def roc_date_input(label, default_date=None, key_suffix=""):
    st.markdown(f"**{label}**")
    c1, c2, c3 = st.columns([1, 1, 1])
    if default_date is None: default_date = date.today()
    
    # [修正] 這裡的 key 命名方式統一，避免 Callback 找不到
    k_y = f"year_{key_suffix}"
    k_m = f"month_{key_suffix}"
    k_d = f"day_{key_suffix}"
    
    roc_year = c1.selectbox("民國(年)", range(100, 121), index=(default_date.year - 1911) - 100, key=k_y)
    month = c2.selectbox("月", range(1, 13), index=default_date.month-1, key=k_m)
    day = c3.selectbox("日", range(1, 32), index=default_date.day-1, key=k_d)
    
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

# [修正] Callback 函數，確保正確讀取 Session State
def add_child_callback():
    # 讀取輸入框
    c_name = st.session_state.input_c_name
    note = st.session_state.input_note
    status = st.session_state.input_status
    
    # 讀取日期 (修正 key 名稱)
    y = st.session_state.year_add
    m = st.session_state.month_add
    d = st.session_state.day_add
    
    try:
        dob_obj = date(y + 1911, m, d)
    except:
        dob_obj = date.today()
        
    auto_plans = calculate_admission_roadmap(dob_obj)
    auto_plan = auto_plans[0] if auto_plans else "年齡不符/待確認"
    
    # 加入清單
    st.session_state.temp_children.append({
        "幼兒姓名": c_name if c_name else "(未填)",
        "幼兒生日": to_roc_str(dob_obj),
        "報名狀態": status,
        "預計入學資訊": auto_plan,
        "備註": note
    })
    
    # 清空輸入框 (保留日期，方便雙胞胎)
    st.session_state.input_c_name = "" 
    st.session_state.input_note = ""

# ==========================================
# 📱 APP 介面
# ==========================================
st.set_page_config(page_title="新生管理系統", layout="wide")
st.title("🏫 新生管理系統")

menu = st.sidebar.radio("系統切換", ["👶 新生報名管理", "👩‍🏫 師生人力預估系統"])

if menu == "👶 新生報名管理":
    if 'temp_children' not in st.session_state:
        st.session_state.temp_children = []

    df = load_registered_data()
    
    if not df.empty and '聯繫狀態' not in df.columns: df['聯繫狀態'] = '未聯繫'
    if not df.empty and '報名狀態' not in df.columns: df['報名狀態'] = '排隊候補'
    if not df.empty:
        df['已聯繫'] = df['聯繫狀態'].apply(lambda x: True if str(x).strip() == '已聯繫' else False)

    tab1, tab2, tab3 = st.tabs(["➕ 新增報名 (多寶模式)", "📂 新生資料庫", "📅 未來入學名單預覽"])

    # --- Tab 1: 新增 ---
    with tab1:
        st.subheader("第一步：填寫家長資料 (共用)")
        c_p1, c_p2, c_p3 = st.columns([2, 1, 2])
        p_name = c_p1.text_input("家長姓氏 (必填)", key="input_p_name")
        p_title = c_p2.selectbox("稱謂", ["先生", "小姐", "爸爸", "媽媽"], key="input_p_title")
        phone = c_p3.text_input("聯絡電話 (必填)", key="input_phone")
        referrer = st.text_input("推薦人 (選填)", key="input_referrer")
        
        st.divider()
        st.subheader("第二步：新增幼兒 (可連續加入)")
        st.caption("💡 提示：輸入完一位幼兒後，請務必按下 **「⬇️ 加入暫存清單」**，再輸入下一位。")
        
        c_k1, c_k2 = st.columns([1, 2])
        with c_k1:
            st.text_input("幼兒姓名 (選填)", key="input_c_name")
            # [修正] key_suffix 設為 "add" (不加底線，程式碼內部會自己加)
            roc_date_input("幼兒出生年月日", date(2021, 9, 2), key_suffix="add")
        
        with c_k2:
            st.selectbox("報名狀態", ["排隊候補", "已確認/已繳費", "考慮中/參觀"], key="input_status")
            st.text_area("備註事項", placeholder="例如：雙胞胎哥哥、過敏...", height=100, key="input_note")

        st.button("⬇️ 加入暫存清單 (還有下一位)", on_click=add_child_callback, type="secondary")

        # 顯示暫存區
        if st.session_state.temp_children:
            st.success(f"目前已暫存 {len(st.session_state.temp_children)} 位幼兒，確認無誤請按下方紅色按鈕送出。")
            st.table(pd.DataFrame(st.session_state.temp_children))
            
            if st.button("✅ 確認送出所有資料 (結束)", type="primary"):
                if p_name and phone:
                    if st.session_state.input_c_name != "":
                        st.warning("⚠️ 警告：您輸入框裡還有名字，但沒有按「加入暫存」。請先加入暫存，或清空輸入框再送出。")
                    else:
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
                            st.success(f"✅ 成功新增 {len(new_rows)} 位幼兒資料！")
                            # [修正] 清空所有輸入欄位
                            st.session_state.temp_children = [] 
                            st.session_state.input_p_name = ""
                            st.session_state.input_phone = ""
                            st.session_state.input_referrer = ""
                            st.rerun()
                else:
                    st.error("❌ 無法送出：請確認「家長姓氏」與「電話」已填寫")
        else:
            st.info("尚未加入任何幼兒資料。請填寫上方資料並按下「加入暫存清單」。")

    # --- Tab 2: 新生資料庫 ---
    with tab2:
        st.subheader("📂 新生資料庫")
        
        if not df.empty:
            total_count = len(df)
            uncontacted_count = len(df[df['已聯繫'] == False])
            confirmed_count = len(df[df['報名狀態'].str.contains("已確認") | df['報名狀態'].str.contains("繳費")])
            waitlist_count = len(df[df['報名狀態'].str.contains("排隊")])

            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("總登記人數", total_count)
            kpi2.metric("待聯繫", uncontacted_count, delta=f"-{uncontacted_count} 需處理", delta_color="inverse")
            kpi3.metric("已確認入學", confirmed_count, "🎉")
            kpi4.metric("排隊候補中", waitlist_count)

            st.divider()
            
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載 Excel", data=csv, file_name='kindergarten_data.csv', mime='text/csv')

            display_df = df.copy()

            main_cols = ['已聯繫', '報名狀態', '幼兒生日', '登記日期', '家長稱呼', '電話', '推薦人', '備註', '幼兒姓名', '預計入學資訊']
            for c in main_cols:
                if c not in display_df.columns: display_df[c] = ""
            display_df['電話'] = display_df['電話'].astype(str)

            cols_config = {
                "已聯繫": st.column_config.Ch
