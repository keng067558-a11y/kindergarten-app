import streamlit as st
import pandas as pd
from datetime import date, datetime
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

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
    st.write(f"**{label}**")
    c1, c2, c3 = st.columns([1, 1, 1])
    if default_date is None: default_date = date.today()
    k_y = f"year_{key_suffix}"
    k_m = f"month_{key_suffix}"
    k_d = f"day_{key_suffix}"
    roc_year = c1.selectbox("年", range(100, 121), index=(default_date.year - 1911) - 100, key=k_y)
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
    
    default_option = "年齡不符/待確認"
    has_valid_option = False
    
    for i in range(6): 
        target = current_roc + i
        age = target - (dob.year - 1911) - offset
        if age == 2: grade = "幼幼班"
        elif age == 3: grade = "小班"
        elif age == 4: grade = "中班"
        elif age == 5: grade = "大班"
        elif age < 2: grade = "托嬰中心"
        else: grade = "畢業/超齡"
        
        if "畢業" not in grade:
            option_str = f"{target} 學年 - {grade}"
            roadmap.append(option_str)
            has_valid_option = True
            
    if not has_valid_option:
        roadmap.append(default_option)
    return roadmap

def add_child_callback():
    c_name = st.session_state.input_c_name
    note = st.session_state.input_note
    status = "排隊中" 
    y = st.session_state.year_add
    m = st.session_state.month_add
    d = st.session_state.day_add
    try: dob_obj = date(y + 1911, m, d)
    except: dob_obj = date.today()
    auto_plans = calculate_admission_roadmap(dob_obj)
    auto_plan = auto_plans[0] if auto_plans else "年齡不符/待確認"
    st.session_state.temp_children.append({
        "幼兒姓名": c_name if c_name else "(未填)",
        "幼兒生日": to_roc_str(dob_obj),
        "報名狀態": status,
        "預計入學資訊": auto_plan,
        "備註": note
    })
    st.session_state.input_c_name = "" 
    st.session_state.input_note = ""

def remove_child_callback(index):
    if 0 <= index < len(st.session_state.temp_children):
        st.session_state.temp_children.pop(index)

def submit_all_callback():
    p_name = st.session_state.input_p_name
    p_title = st.session_state.input_p_title
    phone = st.session_state.input_phone
    referrer = st.session_state.input_referrer
    if not p_name or not phone:
        st.session_state['msg_error'] = "❌ 請填寫家長姓氏與電話"
        return
    if st.session_state.input_c_name != "":
        st.session_state['msg_warning'] = "⚠️ 您輸入框裡還有名字，但沒有按「加入暫存」。請先加入暫存再送出。"
        return
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
    if new_rows:
        new_df_chunk = pd.DataFrame(new_rows)
        updated_df = pd.concat([current_df, new_df_chunk], ignore_index=True)
        if sync_data_to_gsheets(updated_df):
            st.session_state['msg_success'] = f"✅ 成功新增 {len(new_rows)} 位幼兒資料！"
            st.session_state.temp_children = []
            st.session_state.input_p_name = ""
            st.session_state.input_phone = ""
            st.session_state.input_referrer = ""
    else:
        st.session_state['msg_error'] = "❌ 沒有任何幼兒資料可送出"

# ==========================================
# 📱 APP 介面主體
# ==========================================
st.title("🏫 幼兒園新生管理系統")

if 'msg_success' not in st.session_state: st.session_state['msg_success'] = None
if 'msg_error' not in st.session_state: st.session_state['msg_error'] = None
if 'msg_warning' not in st.session_state: st.session_state['msg_warning'] = None
if 'temp_children' not in st.session_state: st.session_state.temp_children = []
if 'edited_rows' not in st.session_state: st.session_state.edited_rows = {}

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

df = load_registered_data()
if not df.empty and '聯繫狀態' not in df.columns: df['聯繫狀態'] = '未聯繫'
if not df.empty and '報名狀態' not in df.columns: df['報名狀態'] = '排隊中'
if not df.empty:
    df['已聯繫'] = df['聯繫狀態'].apply(lambda x: True if str(x).strip() == '已聯繫' else False)

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
        roc_date_input("幼兒出生年月日", date(2021, 9, 2), key_suffix="add")
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

        st.button("✅ 確認送出所有資料", type="primary", on_click=submit_all_callback)
    else:
        st.caption("請在右側輸入幼兒資料並加入暫存。")

# --- 頁面 2: 資料管理中心 (含已聯繫分頁) ---
elif menu == "📂 資料管理中心":
    st.markdown("### 📂 資料管理中心")
    
    col_search, col_dl = st.columns([4, 1])
    with col_search:
        search_keyword = st_keyup("🔍 搜尋資料 (輸入電話或姓名)", placeholder="開始打字即自動過濾...")
    with col_dl:
        if not df.empty:
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載", data=csv, file_name='kindergarten_data.csv', mime='text/csv', use_container_width=True)

    if not df.empty:
        # 搜尋邏輯
        base_df = df.copy()
        if search_keyword:
            base_df = base_df[base_df.astype(str).apply(lambda x: x.str.contains(search_keyword, case=False)).any(axis=1)]

        # [修改] 加入 3 個分頁
        tab_todo, tab_done, tab_all = st.tabs(["📞 待聯繫名單 (優先)", "✅ 已聯繫名單", "📋 全部資料"])

        # 定義顯示函數 (複用邏輯)
        def render_student_list(target_df):
            if target_df.empty:
                st.info("此區塊目前無資料。")
                return

            grouped_df = target_df.groupby('電話')
            st.caption(f"共找到 {len(grouped_df)} 個家庭 (共 {len(target_df)} 位幼兒)")
            
            for phone_num, group_data in grouped_df:
                first_row = group_data.iloc[0]
                parent_name = first_row['家長稱呼']
                
                with st.expander(f"👤 {parent_name} | 📞 {phone_num} (共 {len(group_data)} 位幼兒)"):
                    for idx, row in group_data.iterrows():
                        status_color = "tag-yellow"
                        if "已安排" in str(row['報名狀態']): status_color = "tag-green"
                        elif "考慮" in str(row['報名狀態']): status_color = "tag-blue"
                        
                        child_name_display = row['幼兒姓名'] if row['幼兒姓名'] else "(未填姓名)"
                        
                        st.markdown(f"""
                        <div class="child-info-block">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-size:1.1em; font-weight:bold; color:#333;">👶 {child_name_display}</span>
                                <span class="card-tag {status_color}">{row['報名狀態']}</span>
                            </div>
                            <div style="color:#666; font-size:0.9em; margin-top:5px;">
                                🎂 生日：{row['幼兒生日']} | 🏫 {row['預計入學資訊']}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 編輯表單
                        def update_value(i, c, k):
                            if i not in st.session_state.edited_rows: st.session_state.edited_rows[i] = {}
                            st.session_state.edited_rows[i][c] = st.session_state[k]

                        k_contact = f"contact_{idx}"
                        st.checkbox("已聯繫", value=row['已聯繫'], key=k_contact, on_change=update_value, args=(idx, '已聯繫', k_contact))
                        
                        k_status = f"status_{idx}"
                        status_opts = ["排隊中", "已安排", "考慮中"]
                        curr_val = row['報名狀態']
                        if curr_val == "排隊候補": curr_val = "排隊中"
                        if "已確認" in curr_val: curr_val = "已安排"
                        if curr_val not in status_opts: status_opts.insert(0, curr_val)
                        st.selectbox("報名狀態", status_opts, index=status_opts.index(curr_val), key=k_status, on_change=update_value, args=(idx, '報名狀態', k_status))
                        
                        k_grade = f"grade_{idx}"
                        current_plan = row['預計入學資訊']
                        try:
                            dob_parts = str(row['幼兒生日']).split('/')
                            dob_obj = date(int(dob_parts[0])+1911, int(dob_parts[1]), int(dob_parts[2]))
                            possible_plans = calculate_admission_roadmap(dob_obj)
                        except: possible_plans = [current_plan, "無法計算"]
                        if current_plan not in possible_plans: possible_plans.insert(0, current_plan)
                        st.selectbox("入學年段", possible_plans, index=possible_plans.index(current_plan), key=k_grade, on_change=update_value, args=(idx, '預計入學資訊', k_grade))
                        
                        k_note = f"note_{idx}"
                        st.text_area("備註", value=row['備註'], height=68, key=k_note, on_change=update_value, args=(idx, '備註', k_note))

                        if st.button("🗑️ 刪除此幼兒", key=f"del_btn_{idx}"):
                            # 為了安全刪除，我們操作原始 df
                            df = df.drop(idx)
                            if sync_data_to_gsheets(df):
                                st.success("✅ 刪除成功！")
                                st.rerun()
                        st.divider()

        # 分頁 1: 待聯繫 (Contacted = False)
        with tab_todo:
            st.warning("🔔 這裡顯示 **尚未聯繫** 的家長，請優先處理。")
            render_student_list(base_df[base_df['已聯繫'] == False])

        # 分頁 2: 已聯繫 (Contacted = True)
        with tab_done:
            st.success("✅ 這裡顯示 **已經聯繫過** 的家長。")
            render_student_list(base_df[base_df['已聯繫'] == True])

        # 分頁 3: 全部
        with tab_all:
            render_student_list(base_df)
        
        st.write("")
        if st.button("💾 儲存所有變更", type="primary", use_container_width=True):
            has_changes = False
            for idx, changes in st.session_state.edited_rows.items():
                for col, val in changes.items():
                    df.at[idx, col] = val
                    has_changes = True
            
            if has_changes:
                if sync_data_to_gsheets(df):
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
                dob_parts = str(row['幼兒生日']).split('/')
                dob_obj = date(int(dob_parts[0])+1911, int(dob_parts[1]), int(dob_parts[2]))
                grade = get_grade_for_year(dob_obj, search_year)
                
                status_text = str(row['報名狀態'])
                is_confirmed = "已安排" in status_text or "已確認" in status_text or "繳費" in status_text
                
                if grade in roster:
                    stats['total'] += 1
                    if row['已聯繫']: stats['contacted'] += 1
                    if is_confirmed: 
                        stats['confirmed'] += 1
                        confirmed_list.append({
                            "班級": grade,
                            "家長": row['家長稱呼'],
                            "電話": row['電話'],
                            "備註": row['備註']
                        })
                    
                    roster[grade].append({
                        "index": idx,
                        "已聯繫": row['已聯繫'],
                        "報名狀態": row['報名狀態'],
                        "家長": row['家長稱呼'],
                        "電話": row['電話'],
                        "備註": row['備註']
                    })
            except: pass

        c1, c2, c3 = st.columns(3)
        c1.metric("符合資格總人數", stats['total'])
        c2.metric("已安排入學", stats['confirmed'])
        c3.metric("聯絡進度", f"{int(stats['contacted']/stats['total']*100)}%" if stats['total']>0 else "0%")
        st.progress(stats['contacted']/stats['total'] if stats['total']>0 else 0)
        
        if confirmed_list:
            with st.expander(f"📋 {search_year} 學年度 - 已安排入學名單總表 ({len(confirmed_list)}人)", expanded=True):
                st.dataframe(pd.DataFrame(confirmed_list), use_container_width=True)
        else:
            st.info(f"{search_year} 學年度目前尚未有「已安排」的學生。")

        st.divider()
        st.markdown("#### 🔽 各班級詳細名單 (含排隊中)")

        for g in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]:
            students = roster[g]
            count = len(students)
            with st.expander(f"{g} (共 {count} 人)", expanded=(count > 0)):
                if count > 0:
                    class_df = pd.DataFrame(students)
                    edited = st.data_editor(
                        class_df[["已聯繫", "報名狀態", "家長", "電話", "備註"]],
                        column_config={
                            "已聯繫": st.column_config.CheckboxColumn(width="small"),
                            "報名狀態": st.column_config.TextColumn(disabled=True),
                            "家長": st.column_config.TextColumn(disabled=True),
                            "電話": st.column_config.TextColumn(disabled=True),
                            "備註": st.column_config.TextColumn(disabled=True),
                        },
                        hide_index=True,
                        use_container_width=True,
                        key=f"editor_{search_year}_{g}"
                    )
                    if st.button(f"💾 儲存 {g} 變更", key=f"btn_{search_year}_{g}"):
                        full_df = df.copy()
                        has_change = False
                        for i, row in enumerate(students):
                            orig_idx = row['index']
                            new_val = edited.iloc[i]['已聯繫']
                            if full_df.at[orig_idx, '已聯繫'] != new_val:
                                full_df.at[orig_idx, '已聯繫'] = new_val
                                has_change = True
                        if has_change:
                            if sync_data_to_gsheets(full_df):
                                st.success("更新成功！")
                                time.sleep(0.5)
                                st.rerun()
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
    if not df_new.empty and '報名狀態' not in df_new.columns: df_new['報名狀態'] = '排隊中'

    today = date.today()
    this_roc_year = today.year - 1911
    if today.month < 8: this_roc_year -= 1
    
    target_years = st.multiselect("請選擇預估學年", [this_roc_year+1, this_roc_year+2, this_roc_year+3], default=[this_roc_year+1])

    if target_years:
        st.divider()
        for year in sorted(target_years):
            st.subheader(f"📅 民國 {year} 學年度")
            confirmed_counts = {"托嬰中心": 0, "幼幼班": 0, "小班": 0, "中班": 0, "大班": 0}
            waitlist_counts = {"托嬰中心": 0, "幼幼班": 0, "小班": 0, "中班": 0, "大班": 0}
            
            if not df_current.empty:
                for _, row in df_current.iterrows():
                    try:
                        dob_obj = datetime.strptime(str(row['出生年月日']), "%Y-%m-%d").date()
                        grade = get_grade_for_year(dob_obj, year)
                        if grade in confirmed_counts: confirmed_counts[grade] += 1
                    except: pass

            if not df_new.empty:
                for _, row in df_new.iterrows():
                    plan_str = str(row['預計入學資訊'])
                    status = str(row['報名狀態'])
                    try:
                        dob_str = str(row['幼兒生日'])
                        dob_parts = dob_str.split('/')
                        dob_obj = date(int(dob_parts[0])+1911, int(dob_parts[1]), int(dob_parts[2]))
                        grade = get_grade_for_year(dob_obj, year)
                        target_grade = grade if grade in confirmed_counts else None
                        if target_grade:
                            if "已安排" in status or "已確認" in status: confirmed_counts[target_grade] += 1
                            else: waitlist_counts[target_grade] += 1
                    except: pass

            data = []
            total_teachers_min = 0
            total_teachers_max = 0
            class_rules = [("托嬰中心", ratio_daycare), ("幼幼班", ratio_toddler), ("小班", ratio_normal), ("中班", ratio_normal), ("大班", ratio_normal)]
            
            for grade, ratio in class_rules:
                base = confirmed_counts[grade]
                wait = waitlist_counts[grade]
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
                    "需老師": f"{tea_min} ~ {tea_max} 位"
                })
            
            st.dataframe(pd.DataFrame(data), use_container_width=True)
            st.caption(f"💡 結論：老師需求介於 **{total_teachers_min}** ~ **{total_teachers_max}** 位")
            st.divider()
    else:
        st.info("請選擇學年。")
