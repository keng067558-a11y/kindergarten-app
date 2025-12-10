import streamlit as st
import pandas as pd
from datetime import date, datetime
import math
import time
import uuid

# 嘗試匯入 gspread，如果沒有安裝或設定失敗，將使用本地 CSV 模式
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

try:
    from streamlit_keyup import st_keyup
except ImportError:
    def st_keyup(label, placeholder=None, key=None):
        return st.text_input(label, placeholder=placeholder, key=key)

# ==========================================
# 🎨 自定義 CSS
# ==========================================
st.set_page_config(page_title="新生管理系統", layout="wide", page_icon="🏫")

st.markdown("""
<style>
    .stApp { font-family: "Microsoft JhengHei", sans-serif; }
    
    .streamlit-expanderHeader {
        background-color: #f8f9fa;
        border-radius: 8px;
        font-size: 16px;
        color: #333;
        border: 1px solid #eee;
    }
    
    .parent-card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 3px 6px rgba(0,0,0,0.08);
        margin-bottom: 15px;
        border-top: 5px solid #2196F3;
        transition: all 0.2s ease;
    }
    
    .child-info-block {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
        margin-top: 10px;
        border-left: 4px solid #4CAF50;
    }
    
    .card-tag {
        display: inline-block; padding: 2px 8px; border-radius: 10px; 
        font-size: 11px; font-weight: bold; color: white; float: right;
    }
    .tag-green { background-color: #28a745; }
    .tag-yellow { background-color: #f1c40f; color: #333; }
    .tag-blue { background-color: #17a2b8; }
    
    div.stButton > button { border-radius: 8px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔒 安全鎖
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if not st.session_state.password_correct:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.title("🔒 系統登入")
            password = st.text_input("請輸入通關密碼", type="password")
            if st.button("登入系統", type="primary"):
                if password == "1234":  # 可自行修改密碼
                    st.session_state.password_correct = True
                    st.rerun()
                else:
                    st.error("密碼錯誤")
        return False
    return True

if not check_password():
    st.stop()

# ==========================================
# ⚙️ 設定與連線 (含容錯機制)
# ==========================================
SHEET_NAME = 'kindergarten_db'
LOCAL_CSV = 'kindergarten_local_db.csv'
STUDENT_CSV = 'students.csv'

@st.cache_resource
def get_gsheet_client():
    if not HAS_GSPREAD: return None
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        # 檢查是否有 secrets 設定，否則回傳 None
        if "gcp_service_account" not in st.secrets:
            return None
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        return None

def connect_to_gsheets():
    client = get_gsheet_client()
    if client:
        try:
            return client.open(SHEET_NAME).sheet1
        except Exception:
            return None # 找不到試算表
    return None

@st.cache_data(ttl=60)
def load_registered_data():
    # 優先嘗試 Google Sheets
    sheet = connect_to_gsheets()
    df = pd.DataFrame()
    
    if sheet:
        try:
            data = sheet.get_all_values()
            if data:
                headers = data[0]
                rows = data[1:]
                df = pd.DataFrame(rows, columns=headers)
        except Exception:
            pass
    
    # 如果 GSheet 失敗或沒資料，嘗試讀取本地 CSV
    if df.empty:
        try:
            df = pd.read_csv(LOCAL_CSV)
        except FileNotFoundError:
            # 初始化空 DataFrame
            df = pd.DataFrame(columns=['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註'])

    # 資料清洗與標準化
    if '電話' in df.columns:
        df['電話'] = df['電話'].astype(str).str.strip()
        # 簡單的格式修正
        df['電話'] = df['電話'].apply(lambda x: '0' + x if len(x) == 9 and x.startswith('9') else x)
    
    if '聯繫狀態' not in df.columns: df['聯繫狀態'] = '未聯繫'
    if '報名狀態' not in df.columns: df['報名狀態'] = '排隊中'
    
    return df

def load_current_students():
    try:
        return pd.read_csv(STUDENT_CSV)
    except:
        return pd.DataFrame(columns=['姓名', '出生年月日', '目前班級'])

def sync_data_to_gsheets(new_df):
    try:
        save_df = new_df.copy()
        
        # 清理暫時欄位
        if 'is_contacted' in save_df.columns:
            save_df = save_df.drop(columns=['is_contacted'])
        
        final_cols = ['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註']
        for col in final_cols:
            if col not in save_df.columns: save_df[col] = ""
        save_df = save_df[final_cols]
        save_df = save_df.astype(str) # 轉字串避免 JSON 錯誤

        # 1. 嘗試存入 Google Sheets
        sheet = connect_to_gsheets()
        gsheet_success = False
        if sheet:
            try:
                sheet.clear()
                sheet.append_row(final_cols)
                if not save_df.empty:
                    sheet.append_rows(save_df.values.tolist())
                gsheet_success = True
            except Exception as e:
                st.warning(f"Google Sheet 同步失敗，僅儲存於本地 CSV: {e}")

        # 2. 總是存入本地 CSV 作為備份
        save_df.to_csv(LOCAL_CSV, index=False)
        
        # 清除快取以顯示最新資料
        load_registered_data.clear()
        
        return True
    except Exception as e:
        st.error(f"儲存發生嚴重錯誤: {e}")
        return False

# ==========================================
# 🧠 核心邏輯
# ==========================================
def roc_date_input(label, default_date=None, key_suffix=""):
    st.write(f"**{label}**")
    c1, c2, c3 = st.columns([1, 1, 1])
    if default_date is None: default_date = date.today()
    
    k_y = f"year_{key_suffix}"
    k_m = f"month_{key_suffix}"
    k_d = f"day_{key_suffix}"
    
    # 這裡的邏輯：如果 session state 有值就用 session state，否則用預設
    current_roc_year = (default_date.year - 1911)
    
    roc_year = c1.selectbox("年", range(90, 131), index=(current_roc_year - 90), key=k_y)
    month = c2.selectbox("月", range(1, 13), index=default_date.month-1, key=k_m)
    day = c3.selectbox("日", range(1, 32), index=default_date.day-1, key=k_d)
    
    try: 
        return date(roc_year + 1911, month, day)
    except: 
        return date.today()

def to_roc_str(d):
    return f"{d.year-1911}/{d.month:02d}/{d.day:02d}"

def get_grade_for_year(birth_date, target_roc_year):
    if birth_date is None: return "未知"
    
    # 學年定義：該年 8/1 開學。
    # 判斷學齡：看該年 9/1 (含) 之前的年齡
    # 簡單算法：學年 - 出生民國年
    # 如果生日在 9/2 之後，入學年齡算小一歲 (offset = 1)
    
    birth_year_roc = birth_date.year - 1911
    # 9月2日以後出生，算下一屆，所以年齡-1
    offset = 1 if (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2) else 0
    
    age_in_sept = target_roc_year - birth_year_roc - offset
    
    if age_in_sept < 2: return "托嬰中心"
    if age_in_sept == 2: return "幼幼班"
    if age_in_sept == 3: return "小班"
    if age_in_sept == 4: return "中班"
    if age_in_sept == 5: return "大班"
    return "畢業/超齡"

def calculate_admission_roadmap(dob):
    today = date.today()
    # 判斷現在是哪個學年 (8月之後算新學年)
    current_roc_academic_year = today.year - 1911
    if today.month < 8: 
        current_roc_academic_year -= 1
        
    roadmap = []
    
    # 預測未來 6 年
    for i in range(6): 
        target_academic_year = current_roc_academic_year + i
        grade = get_grade_for_year(dob, target_academic_year)
        
        if "畢業" not in grade:
            option_str = f"{target_academic_year} 學年 - {grade}"
            roadmap.append(option_str)
            
    if not roadmap:
        roadmap.append("年齡不符/超齡")
        
    return roadmap

def add_child_callback():
    c_name = st.session_state.get("input_c_name", "")
    note = st.session_state.get("input_note", "")
    
    # 讀取日期元件的值
    y = st.session_state.get("year_add", 112)
    m = st.session_state.get("month_add", 1)
    d = st.session_state.get("day_add", 1)
    
    try: dob_obj = date(y + 1911, m, d)
    except: dob_obj = date.today()
    
    auto_plans = calculate_admission_roadmap(dob_obj)
    auto_plan = auto_plans[0] if auto_plans else "待確認"
    
    st.session_state.temp_children.append({
        "幼兒姓名": c_name if c_name else "(未填)",
        "幼兒生日": to_roc_str(dob_obj),
        "報名狀態": "排隊中",
        "預計入學資訊": auto_plan,
        "備註": note,
        "uuid": str(uuid.uuid4()) # 增加唯一 ID 方便操作
    })
    
    # 重置輸入框 (需要配合 key)
    st.session_state.input_c_name = "" 
    st.session_state.input_note = ""

def remove_child_callback(idx):
    if 0 <= idx < len(st.session_state.temp_children):
        st.session_state.temp_children.pop(idx)

def submit_all_callback():
    p_name = st.session_state.input_p_name
    p_title = st.session_state.input_p_title
    phone = st.session_state.input_phone
    referrer = st.session_state.input_referrer
    
    if not p_name or not phone:
        st.session_state['msg_error'] = "❌ 請填寫家長姓氏與電話"
        return
        
    # 檢查是否有未加入暫存的資料
    if st.session_state.get("input_c_name", "") != "":
        st.session_state['msg_warning'] = "⚠️ 輸入框裡還有資料，請先按「⬇️ 加入暫存」再送出。"
        return

    if not st.session_state.temp_children:
         st.session_state['msg_error'] = "❌ 沒有任何幼兒資料可送出"
         return

    current_df = load_registered_data()
    new_rows = []
    
    for child in st.session_state.temp_children:
        new_rows.append({
            '報名狀態': child['報名狀態'],
            '聯繫狀態': '未聯繫',
            '登記日期': to_roc_str(date.today()),
            '幼兒姓名': child['幼兒姓名'] if child['幼兒姓名'] != "(未填)" else "",
            '家長稱呼': f"{p_name} {p_title}",
            '電話': str(phone), 
            '幼兒生日': child['幼兒生日'],
            '預計入學資訊': child['預計入學資訊'],
            '推薦人': referrer,
            '備註': child['備註']
        })
    
    if new_rows:
        new_df_chunk = pd.DataFrame(new_rows)
        # 合併並重置 index
        updated_df = pd.concat([current_df, new_df_chunk], ignore_index=True)
        
        if sync_data_to_gsheets(updated_df):
            st.session_state['msg_success'] = f"✅ 成功新增 {len(new_rows)} 位幼兒資料！"
            st.session_state.temp_children = []
            st.session_state.input_p_name = ""
            st.session_state.input_phone = ""
            st.session_state.input_referrer = ""
    else:
        st.session_state['msg_error'] = "❌ 資料處理錯誤"

# ==========================================
# 📱 APP 介面主體
# ==========================================
st.title("🏫 幼兒園新生管理系統")

# 初始化 session state
if 'msg_success' not in st.session_state: st.session_state['msg_success'] = None
if 'msg_error' not in st.session_state: st.session_state['msg_error'] = None
if 'msg_warning' not in st.session_state: st.session_state['msg_warning'] = None
if 'temp_children' not in st.session_state: st.session_state.temp_children = []
if 'edited_rows' not in st.session_state: st.session_state.edited_rows = {}

# 顯示全域訊息
if st.session_state['msg_success']:
    st.balloons()
    st.success(st.session_state['msg_success'])
    st.session_state['msg_success'] = None
if st.session_state['msg_error']:
    st.error(st.session_state['msg_error'])
    st.session_state['msg_error'] = None
if st.session_state['msg_warning']:
    st.warning(st.session_state['msg_warning'])
    st.session_state['msg_warning'] = None

# 讀取資料
df = load_registered_data()

menu = st.sidebar.radio("功能導航", ["👶 新增報名", "📂 資料管理中心", "📅 未來入學預覽", "👩‍🏫 師資人力預估"])

# --- 頁面 1: 新增報名 ---
if menu == "👶 新增報名":
    st.markdown("### 📝 新生報名登記")
    st.markdown("---")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.info("👤 **第一步：家長資訊**")
        p_name = st.text_input("家長姓氏 (必填)", key="input_p_name", placeholder="例如：陳")
        p_title = st.selectbox("稱謂", ["先生", "小姐", "爸爸", "媽媽"], key="input_p_title")
        phone = st.text_input("聯絡電話 (必填)", key="input_phone", placeholder="例如：0912345678")
        referrer = st.text_input("推薦人 (選填)", key="input_referrer")

    with col2:
        st.success("👶 **第二步：幼兒資訊 (可多位)**")
        st.text_input("幼兒姓名 (選填)", key="input_c_name", placeholder="尚未取名可不填")
        roc_date_input("幼兒出生年月日", date(2022, 1, 1), key_suffix="add")
        st.text_area("備註事項", placeholder="例如：雙胞胎、過敏體質...", height=100, key="input_note")
        
        st.button("⬇️ 加入暫存 (還有下一位)", on_click=add_child_callback, type="secondary")

    st.markdown("---")
    if st.session_state.temp_children:
        st.markdown(f"#### 🛒 待送出名單 ({len(st.session_state.temp_children)} 位)")
        
        for i, child in enumerate(st.session_state.temp_children):
            c_info, c_del = st.columns([5, 1])
            with c_info:
                st.markdown(f"""
                <div class="parent-card" style="border-left: 5px solid #2196F3; margin-bottom:0; padding: 15px;">
                    <div class="card-title">👶 {child['幼兒姓名']}</div>
                    <div class="card-subtitle">🎂 生日：{child['幼兒生日']} | 📅 {child['預計入學資訊']}</div>
                    <div style="color: #666; font-size: 12px;">📝 {child['備註'] if child['備註'] else "無備註"}</div>
                </div>
                """, unsafe_allow_html=True)
            with c_del:
                st.write("") 
                st.button(f"🗑️", key=f"del_temp_{i}", on_click=remove_child_callback, args=(i,), type="primary")
            st.write("") 

        st.button("✅ 確認送出所有資料", type="primary", on_click=submit_all_callback, use_container_width=True)
    else:
        st.caption("請在右側輸入幼兒資料並加入暫存。")

# --- 頁面 2: 資料管理中心 ---
elif menu == "📂 資料管理中心":
    st.markdown("### 📂 資料管理中心")
    
    col_search, col_dl = st.columns([4, 1])
    with col_search:
        search_keyword = st_keyup("🔍 搜尋資料 (輸入電話或姓名)", placeholder="開始打字即自動過濾...")
    with col_dl:
        if not df.empty:
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載", data=csv, file_name=f'kindergarten_data_{date.today()}.csv', mime='text/csv', use_container_width=True)

    if not df.empty:
        display_df = df.copy()
        # 為每一行加上原始索引，確保編輯時不會錯位
        display_df['original_index'] = display_df.index
        
        if search_keyword:
            display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search_keyword, case=False)).any(axis=1)]

        # 預先計算 is_contacted
        display_df['is_contacted'] = display_df['聯繫狀態'].apply(lambda x: True if str(x).strip() == '已聯繫' else False)

        tab_todo, tab_done, tab_all = st.tabs(["📞 待聯繫名單 (優先)", "✅ 已聯繫名單", "📋 全部資料"])

        # 定義顯示函數
        def render_student_list(target_df, tab_key_suffix):
            if target_df.empty:
                st.info("此區塊目前無資料。")
                return

            grouped_df_tab = target_df.groupby('電話')
            
            st.caption(f"共找到 {len(grouped_df_tab)} 個家庭")

            # 為了避免 widget key 重複，我們需要非常小心的命名 key
            for phone_num, group_data in grouped_df_tab:
                first_row = group_data.iloc[0]
                parent_name = first_row['家長稱呼']
                
                expander_title = f"👤 {parent_name} | 📞 {phone_num}"
                
                with st.expander(expander_title):
                    for _, row in group_data.iterrows():
                        # 使用原始 DataFrame 的 index 做為 key 的一部分，確保唯一性
                        orig_idx = row['original_index']
                        unique_key = f"{tab_key_suffix}_{orig_idx}"

                        status_color = "tag-yellow"
                        if "已安排" in str(row['報名狀態']): status_color = "tag-green"
                        elif "考慮" in str(row['報名狀態']): status_color = "tag-blue"
                        
                        child_name = row['幼兒姓名'] if row['幼兒姓名'] else "(未填姓名)"

                        st.markdown(f"""
                        <div class="child-info-block">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-size:1.1em; font-weight:bold; color:#333;">👶 {child_name}</span>
                                <span class="card-tag {status_color}">{row['報名狀態']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 編輯區塊
                        c1, c2 = st.columns([1, 1])
                        
                        # 狀態更新 callback
                        def update_state(oid=orig_idx, k_con=f"c_{unique_key}", k_sta=f"s_{unique_key}", k_note=f"n_{unique_key}"):
                            if oid not in st.session_state.edited_rows:
                                st.session_state.edited_rows[oid] = {}
                            
                            st.session_state.edited_rows[oid]['聯繫狀態'] = "已聯繫" if st.session_state[k_con] else "未聯繫"
                            st.session_state.edited_rows[oid]['報名狀態'] = st.session_state[k_sta]
                            st.session_state.edited_rows[oid]['備註'] = st.session_state[k_note]

                        # 已聯繫 Checkbox
                        is_con = st.checkbox("已聯繫", value=row['is_contacted'], key=f"c_{unique_key}", on_change=update_state)
                        
                        # 報名狀態 Selectbox
                        status_opts = ["排隊中", "已安排", "考慮中", "放棄"]
                        curr_val = row['報名狀態']
                        if curr_val not in status_opts: status_opts.insert(0, curr_val)
                        st.selectbox("報名狀態", status_opts, index=status_opts.index(curr_val), key=f"s_{unique_key}", on_change=update_state)

                        # 備註 Textarea
                        st.text_area("備註", value=row['備註'], height=68, key=f"n_{unique_key}", on_change=update_state)

                        # 刪除按鈕
                        if st.button("🗑️ 刪除", key=f"del_{unique_key}"):
                            new_df = df.drop(orig_idx)
                            if sync_data_to_gsheets(new_df):
                                st.success("已刪除")
                                time.sleep(0.5)
                                st.rerun()

        with tab_todo:
            st.warning("🔔 這裡顯示 **尚未聯繫** 的家長，請優先處理。")
            render_student_list(display_df[display_df['is_contacted'] == False], "todo")

        with tab_done:
            st.success("✅ 這裡顯示 **已經聯繫過** 的家長。")
            render_student_list(display_df[display_df['is_contacted'] == True], "done")

        with tab_all:
            render_student_list(display_df, "all")
        
        # 底部儲存按鈕
        st.write("")
        st.markdown("---")
        if st.button("💾 儲存所有變更", type="primary", use_container_width=True):
            if st.session_state.edited_rows:
                full_df = df.copy()
                for idx, changes in st.session_state.edited_rows.items():
                    # 確保 index 存在 (避免已被刪除)
                    if idx in full_df.index:
                        for col, val in changes.items():
                            full_df.at[idx, col] = val
                
                if sync_data_to_gsheets(full_df):
                    st.success("✅ 所有變更已儲存！")
                    st.session_state.edited_rows = {}
                    time.sleep(1)
                    st.rerun()
            else:
                st.info("沒有偵測到任何變更。")

    else:
        st.info("目前無資料。")

# --- 頁面 3: 未來入學預覽 ---
elif menu == "📅 未來入學預覽":
    st.markdown("### 📅 未來入學名單預覽")
    c_year, c_info = st.columns([1, 3])
    with c_year:
        this_year = date.today().year - 1911
        search_year = st.number_input("查詢學年 (民國)", min_value=this_year, max_value=this_year+10, value=this_year+1)
    
    st.divider()

    if not df.empty:
        confirmed_list = []
        roster = {"托嬰中心": [], "幼幼班": [], "小班": [], "中班": [], "大班": []}
        stats = {"total": 0, "confirmed": 0, "contacted": 0}
        
        for idx, row in df.iterrows():
            try:
                # 解析生日
                dob_parts = str(row['幼兒生日']).split('/')
                dob_obj = date(int(dob_parts[0])+1911, int(dob_parts[1]), int(dob_parts[2]))
                
                # 計算該學年應讀年級
                grade = get_grade_for_year(dob_obj, search_year)
                
                status_text = str(row['報名狀態'])
                is_contacted = str(row['聯繫狀態']) == "已聯繫"
                is_confirmed = "已安排" in status_text or "已確認" in status_text
                
                if grade in roster:
                    stats['total'] += 1
                    if is_contacted: stats['contacted'] += 1
                    
                    student_info = {
                        "原索引": idx, # 儲存原始 index 方便回寫
                        "已聯繫": is_contacted,
                        "報名狀態": row['報名狀態'],
                        "幼兒姓名": row['幼兒姓名'],
                        "家長": row['家長稱呼'],
                        "電話": row['電話'],
                        "備註": row['備註']
                    }

                    if is_confirmed: 
                        stats['confirmed'] += 1
                        confirmed_list.append(student_info)
                    
                    roster[grade].append(student_info)
            except: pass

        c1, c2, c3 = st.columns(3)
        c1.metric("符合資格總人數", stats['total'])
        c2.metric("已安排入學", stats['confirmed'])
        c3.metric("聯絡進度", f"{int(stats['contacted']/stats['total']*100)}%" if stats['total']>0 else "0%")
        st.progress(stats['contacted']/stats['total'] if stats['total']>0 else 0)
        
        if confirmed_list:
            with st.expander(f"📋 {search_year} 學年度 - 已安排入學名單 ({len(confirmed_list)}人)", expanded=True):
                st.dataframe(pd.DataFrame(confirmed_list)[['幼兒姓名', '家長', '電話', '備註']], use_container_width=True)

        st.divider()
        st.markdown("#### 🔽 各班級詳細名單 (可直接編輯)")

        for g in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]:
            students = roster[g]
            count = len(students)
            with st.expander(f"📍 {g} (共 {count} 人)", expanded=(count > 0)):
                if count > 0:
                    class_df = pd.DataFrame(students)
                    # 使用 Data Editor 進行批次編輯
                    edited_df = st.data_editor(
                        class_df,
                        column_config={
                            "原索引": None, # 隱藏索引欄
                            "已聯繫": st.column_config.CheckboxColumn(width="small"),
                            "報名狀態": st.column_config.SelectboxColumn(options=["排隊中", "已安排", "考慮中", "放棄"], width="medium"),
                            "家長": st.column_config.TextColumn(disabled=True),
                            "電話": st.column_config.TextColumn(disabled=True),
                        },
                        hide_index=True,
                        use_container_width=True,
                        key=f"editor_{search_year}_{g}"
                    )
                    
                    if st.button(f"💾 儲存 {g} 變更", key=f"btn_save_{search_year}_{g}"):
                        full_df = load_registered_data()
                        has_change = False
                        
                        # 比對並更新
                        for i, row in edited_df.iterrows():
                            orig_idx = row['原索引']
                            
                            # 更新聯繫狀態
                            new_contact = "已聯繫" if row['已聯繫'] else "未聯繫"
                            if full_df.at[orig_idx, '聯繫狀態'] != new_contact:
                                full_df.at[orig_idx, '聯繫狀態'] = new_contact
                                has_change = True
                            
                            # 更新報名狀態
                            if full_df.at[orig_idx, '報名狀態'] != row['報名狀態']:
                                full_df.at[orig_idx, '報名狀態'] = row['報名狀態']
                                has_change = True
                                
                            # 更新備註
                            if full_df.at[orig_idx, '備註'] != row['備註']:
                                full_df.at[orig_idx, '備註'] = row['備註']
                                has_change = True
                        
                        if has_change:
                            if sync_data_to_gsheets(full_df):
                                st.success(f"{g} 資料更新成功！")
                                time.sleep(0.5)
                                st.rerun()
                        else:
                            st.info("無變更")
                else:
                    st.caption("尚無符合資格的學生")

# --- 頁面 4: 師資人力預估 ---
elif menu == "👩‍🏫 師資人力預估":
    st.header("📊 未來學年師生人力預估")
    with st.expander("⚙️ 師生比參數設定", expanded=False):
        c1, c2, c3 = st.columns(3)
        ratio_daycare = c1.number_input("托嬰 (0-2歲)", value=5)
        ratio_toddler = c2.number_input("幼幼 (2-3歲)", value=8)
        ratio_normal = c3.number_input("小/中/大 (3-6歲)", value=15)

    df_current = load_current_students() 
    df_new = load_registered_data()
    
    today = date.today()
    this_roc_year = today.year - 1911
    if today.month < 8: this_roc_year -= 1
    
    target_years = st.multiselect("請選擇預估學年", [this_roc_year+1, this_roc_year+2, this_roc_year+3], default=[this_roc_year+1])

    if target_years:
        st.divider()
        for year in sorted(target_years):
            st.subheader(f"📅 民國 {year} 學年度")
            
            # 初始化計數器
            counts = {
                k: {"confirmed": 0, "waitlist": 0} 
                for k in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]
            }
            
            # 計算新生 (報名資料庫)
            if not df_new.empty:
                for _, row in df_new.iterrows():
                    try:
                        dob_parts = str(row['幼兒生日']).split('/')
                        dob_obj = date(int(dob_parts[0])+1911, int(dob_parts[1]), int(dob_parts[2]))
                        target_grade = get_grade_for_year(dob_obj, year)
                        
                        if target_grade in counts:
                            status = str(row['報名狀態'])
                            if "已安排" in status or "已確認" in status:
                                counts[target_grade]["confirmed"] += 1
                            else:
                                counts[target_grade]["waitlist"] += 1
                    except: pass

            # 製作報表
            data = []
            total_teachers_min = 0
            total_teachers_max = 0
            class_rules = [("托嬰中心", ratio_daycare), ("幼幼班", ratio_toddler), ("小班", ratio_normal), ("中班", ratio_normal), ("大班", ratio_normal)]
            
            for grade, ratio in class_rules:
                base = counts[grade]["confirmed"]
                wait = counts[grade]["waitlist"]
                total_possible = base + wait
                
                tea_min = math.ceil(base / ratio) if base > 0 else 0
                tea_max = math.ceil(total_possible / ratio) if total_possible > 0 else 0
                
                total_teachers_min += tea_min
                total_teachers_max += tea_max
                
                data.append({
                    "班級": grade,
                    "師生比": f"1:{ratio}",
                    "已安排人數": base,
                    "排隊中": wait,
                    "預估總人數": total_possible,
                    "需老師 (最少/最多)": f"{tea_min} ~ {tea_max} 位"
                })
            
            st.dataframe(pd.DataFrame(data), use_container_width=True)
            st.info(f"💡 結論：該學年老師需求介於 **{total_teachers_min}** 位 (僅已確認) 到 **{total_teachers_max}** 位 (含排隊) 之間")
            st.divider()
