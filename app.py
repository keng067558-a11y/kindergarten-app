import streamlit as st
import pandas as pd
from datetime import date, datetime
import math
import time
import uuid

# ==========================================
# 0. 基礎設定與函式庫匯入 (這段絕不能少)
# ==========================================
st.set_page_config(page_title="新生管理系統", layout="wide", page_icon="🏫")

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

# 自定義 CSS
st.markdown("""
<style>
    .stApp { font-family: "Microsoft JhengHei", sans-serif; }
    .streamlit-expanderHeader { background-color: #f8f9fa; border: 1px solid #eee; }
    .parent-card { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 3px 6px rgba(0,0,0,0.08); margin-bottom: 15px; border-top: 5px solid #2196F3; }
    .child-info-block { background-color: #f8f9fa; padding: 10px; border-radius: 8px; margin-top: 10px; border-left: 4px solid #4CAF50; }
    .card-tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold; color: white; float: right; }
    .tag-green { background-color: #28a745; }
    .tag-yellow { background-color: #f1c40f; color: #333; }
    .tag-blue { background-color: #17a2b8; }
    div.stButton > button { border-radius: 8px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 安全與連線設定
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

SHEET_NAME = 'kindergarten_db'
LOCAL_CSV = 'kindergarten_local_db.csv'
STUDENT_CSV = 'students.csv'

@st.cache_resource
def get_gsheet_client():
    if not HAS_GSPREAD: return None
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        if "gcp_service_account" not in st.secrets: return None
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception: return None

def connect_to_gsheets():
    client = get_gsheet_client()
    if client:
        try: return client.open(SHEET_NAME).sheet1
        except Exception: return None 
    return None

@st.cache_data(ttl=60)
def load_registered_data():
    sheet = connect_to_gsheets()
    df = pd.DataFrame()
    if sheet:
        try:
            data = sheet.get_all_values()
            if data:
                headers = data[0]
                rows = data[1:]
                df = pd.DataFrame(rows, columns=headers)
        except Exception: pass
    
    if df.empty:
        try: df = pd.read_csv(LOCAL_CSV)
        except FileNotFoundError: df = pd.DataFrame(columns=['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註'])

    if '電話' in df.columns:
        df['電話'] = df['電話'].astype(str).str.strip().apply(lambda x: '0' + x if len(x) == 9 and x.startswith('9') else x)
    if '聯繫狀態' not in df.columns: df['聯繫狀態'] = '未聯繫'
    if '報名狀態' not in df.columns: df['報名狀態'] = '排隊中'
    return df

def load_current_students():
    try: return pd.read_csv(STUDENT_CSV)
    except: return pd.DataFrame(columns=['姓名', '出生年月日', '目前班級'])

def sync_data_to_gsheets(new_df):
    try:
        save_df = new_df.copy()
        for col in ['is_contacted', 'original_index']:
            if col in save_df.columns: save_df = save_df.drop(columns=[col])
        
        final_cols = ['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註']
        for col in final_cols:
            if col not in save_df.columns: save_df[col] = ""
        save_df = save_df[final_cols].astype(str)

        sheet = connect_to_gsheets()
        if sheet:
            try:
                sheet.clear()
                sheet.append_row(final_cols)
                if not save_df.empty: sheet.append_rows(save_df.values.tolist())
            except Exception as e: st.warning(f"Google Sheet 同步失敗: {e}")

        save_df.to_csv(LOCAL_CSV, index=False)
        load_registered_data.clear()
        return True
    except Exception as e:
        st.error(f"儲存發生嚴重錯誤: {e}")
        return False

# ==========================================
# 2. 核心計算邏輯
# ==========================================
def roc_date_input(label, default_date=None, key_suffix=""):
    st.write(f"**{label}**")
    c1, c2, c3 = st.columns([1, 1, 1])
    if default_date is None: default_date = date.today()
    current_roc_year = (default_date.year - 1911)
    
    k_y, k_m, k_d = f"y_{key_suffix}", f"m_{key_suffix}", f"d_{key_suffix}"
    roc_year = c1.selectbox("年", range(90, 131), index=(current_roc_year - 90), key=k_y)
    month = c2.selectbox("月", range(1, 13), index=default_date.month-1, key=k_m)
    day = c3.selectbox("日", range(1, 32), index=default_date.day-1, key=k_d)
    try: return date(roc_year + 1911, month, day)
    except: return date.today()

def to_roc_str(d): return f"{d.year-1911}/{d.month:02d}/{d.day:02d}"

def get_grade_for_year(birth_date, target_roc_year):
    if birth_date is None: return "未知"
    birth_year_roc = birth_date.year - 1911
    offset = 1 if (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2) else 0
    age_in_sept = target_roc_year - birth_year_roc - offset
    if age_in_sept < 2: return "托嬰中心"
    elif age_in_sept == 2: return "幼幼班"
    elif age_in_sept == 3: return "小班"
    elif age_in_sept == 4: return "中班"
    elif age_in_sept == 5: return "大班"
    return "畢業/超齡"

def calculate_admission_roadmap(dob):
    today = date.today()
    cur_roc = today.year - 1911
    if today.month < 8: cur_roc -= 1
    roadmap = []
    for i in range(6): 
        target = cur_roc + i
        grade = get_grade_for_year(dob, target)
        if "畢業" not in grade: roadmap.append(f"{target} 學年 - {grade}")
    return roadmap if roadmap else ["年齡不符/超齡"]

def add_child_callback():
    y, m, d = st.session_state.get("y_add", 112), st.session_state.get("m_add", 1), st.session_state.get("d_add", 1)
    try: dob_obj = date(y + 1911, m, d)
    except: dob_obj = date.today()
    auto_plans = calculate_admission_roadmap(dob_obj)
    
    st.session_state.temp_children.append({
        "幼兒姓名": st.session_state.get("input_c_name", "") or "(未填)",
        "幼兒生日": to_roc_str(dob_obj),
        "報名狀態": "排隊中",
        "預計入學資訊": auto_plans[0] if auto_plans else "待確認",
        "備註": st.session_state.get("input_note", "")
    })
    st.session_state.input_c_name = "" 
    st.session_state.input_note = ""

def remove_child_callback(idx):
    if 0 <= idx < len(st.session_state.temp_children): st.session_state.temp_children.pop(idx)

def submit_all_callback():
    p_name, phone = st.session_state.input_p_name, st.session_state.input_phone
    if not p_name or not phone:
        st.session_state['msg_error'] = "❌ 請填寫家長姓氏與電話"
        return
    if st.session_state.temp_children:
        current_df = load_registered_data()
        new_rows = []
        for child in st.session_state.temp_children:
            new_rows.append({
                '報名狀態': child['報名狀態'], '聯繫狀態': '未聯繫', '登記日期': to_roc_str(date.today()),
                '幼兒姓名': child['幼兒姓名'] if child['幼兒姓名'] != "(未填)" else "",
                '家長稱呼': f"{p_name} {st.session_state.input_p_title}", '電話': str(phone),
                '幼兒生日': child['幼兒生日'], '預計入學資訊': child['預計入學資訊'],
                '推薦人': st.session_state.input_referrer, '備註': child['備註']
            })
        if sync_data_to_gsheets(pd.concat([current_df, pd.DataFrame(new_rows)], ignore_index=True)):
            st.session_state['msg_success'] = f"✅ 成功新增 {len(new_rows)} 位幼兒資料！"
            st.session_state.temp_children = []
            st.session_state.input_p_name = ""
            st.session_state.input_phone = ""
    else:
        st.session_state['msg_error'] = "❌ 沒有資料可送出"

# ==========================================
# 3. 頁面 UI 構建
# ==========================================
st.title("🏫 幼兒園新生管理系統")

# 初始化 Session State
for k in ['msg_success', 'msg_error', 'msg_warning']: 
    if k not in st.session_state: st.session_state[k] = None
if 'temp_children' not in st.session_state: st.session_state.temp_children = []
if 'edited_rows' not in st.session_state: st.session_state.edited_rows = {}

if st.session_state['msg_success']: st.success(st.session_state['msg_success']); st.session_state['msg_success'] = None
if st.session_state['msg_error']: st.error(st.session_state['msg_error']); st.session_state['msg_error'] = None
if st.session_state['msg_warning']: st.warning(st.session_state['msg_warning']); st.session_state['msg_warning'] = None

df = load_registered_data()

# --------------------------------------------------------
# 核心導航 (這裡定義了 menu，所以後面的 if/elif 才不會錯)
# --------------------------------------------------------
menu = st.sidebar.radio("功能導航", ["👶 新增報名", "📂 資料管理中心", "📅 未來入學預覽", "👩‍🏫 師資人力預估"])

# --- 頁面 1: 新增報名 ---
if menu == "👶 新增報名":
    st.markdown("### 📝 新生報名登記")
    st.markdown("---")
    col1, col2 = st.columns([1, 1])
    with col1:
        st.info("👤 **第一步：家長資訊**")
        st.text_input("家長姓氏 (必填)", key="input_p_name")
        st.selectbox("稱謂", ["先生", "小姐", "爸爸", "媽媽"], key="input_p_title")
        st.text_input("聯絡電話 (必填)", key="input_phone")
        st.text_input("推薦人 (選填)", key="input_referrer")
    with col2:
        st.success("👶 **第二步：幼兒資訊**")
        st.text_input("幼兒姓名 (選填)", key="input_c_name")
        roc_date_input("幼兒出生年月日", date(2022, 1, 1), key_suffix="add")
        st.text_area("備註事項", key="input_note", height=100)
        st.button("⬇️ 加入暫存", on_click=add_child_callback, type="secondary")

    if st.session_state.temp_children:
        st.markdown(f"#### 🛒 待送出名單 ({len(st.session_state.temp_children)} 位)")
        for i, child in enumerate(st.session_state.temp_children):
            st.info(f"👶 {child['幼兒姓名']} | 🎂 {child['幼兒生日']} | {child['預計入學資訊']}")
            st.button(f"刪除 #{i+1}", key=f"del_{i}", on_click=remove_child_callback, args=(i,))
        st.button("✅ 確認送出所有資料", type="primary", on_click=submit_all_callback, use_container_width=True)

# --- 頁面 2: 資料管理中心 ---
elif menu == "📂 資料管理中心":
    st.markdown("### 📂 資料管理中心")
    col_search, col_dl = st.columns([4, 1])
    search_keyword = st_keyup("🔍 搜尋資料 (輸入電話或姓名)", placeholder="開始打字...", key="search_main")
    if not df.empty:
        col_dl.download_button("📥 下載", df.to_csv(index=False).encode('utf-8-sig'), f'kindergarten_{date.today()}.csv', 'text/csv')

    if not df.empty:
        display_df = df.copy()
        display_df['original_index'] = display_df.index
        if search_keyword:
            display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search_keyword, case=False)).any(axis=1)]
        display_df['is_contacted'] = display_df['聯繫狀態'].apply(lambda x: True if str(x).strip() == '已聯繫' else False)

        tab_todo, tab_done, tab_all = st.tabs(["📞 待聯繫名單", "✅ 已聯繫名單 (含入學設定)", "📋 全部資料"])

        def show_summary_dashboard():
            confirmed_df = df[(df['聯繫狀態']=='已聯繫') & (df['報名狀態'].astype(str).str.contains('已安排|已確認'))]
            if not confirmed_df.empty:
                st.markdown("#### 📊 目前已安排入學人數")
                st.dataframe(confirmed_df.groupby('預計入學資訊').size().reset_index(name='已安排人數'), use_container_width=True, hide_index=True)

        def render_list(target_df, tab_key, show_stats=False):
            if show_stats: show_summary_dashboard()
            if target_df.empty: st.info("無資料"); return
            
            for phone, group in target_df.groupby('電話'):
                with st.expander(f"👤 {group.iloc[0]['家長稱呼']} | 📞 {phone}"):
                    for _, row in group.iterrows():
                        oid = row['original_index']
                        uid = f"{tab_key}_{oid}"
                        
                        st.markdown(f"**👶 {row['幼兒姓名']}** | {row['幼兒生日']} | 狀態: {row['報名狀態']}")
                        c1, c2 = st.columns(2)
                        
                        def update(idx=oid, u=uid):
                            if idx not in st.session_state.edited_rows: st.session_state.edited_rows[idx] = {}
                            st.session_state.edited_rows[idx]['聯繫狀態'] = "已聯繫" if st.session_state[f"c_{u}"] else "未聯繫"
                            st.session_state.edited_rows[idx]['報名狀態'] = st.session_state[f"s_{u}"]
                            st.session_state.edited_rows[idx]['預計入學資訊'] = st.session_state[f"p_{u}"]
                            st.session_state.edited_rows[idx]['備註'] = st.session_state[f"n_{u}"]

                        c1.checkbox("已聯繫", row['is_contacted'], key=f"c_{uid}", on_change=update)
                        status_opts = ["排隊中", "已安排", "考慮中", "放棄", "超齡/畢業"]
                        curr_stat = row['報名狀態'] if row['報名狀態'] in status_opts else status_opts[0]
                        c2.selectbox("狀態", status_opts, index=status_opts.index(curr_stat), key=f"s_{uid}", on_change=update)
                        
                        try: 
                            dob_parts = str(row['幼兒生日']).split('/')
                            dob_obj = date(int(dob_parts[0])+1911, int(dob_parts[1]), int(dob_parts[2]))
                            plan_opts = calculate_admission_roadmap(dob_obj)
                        except: plan_opts = ["無法計算"]
                        curr_plan = str(row['預計入學資訊'])
                        if curr_plan not in plan_opts: plan_opts.insert(0, curr_plan)
                        st.selectbox("預計就讀年段", plan_opts, index=plan_opts.index(curr_plan), key=f"p_{uid}", on_change=update)
                        st.text_area("備註", row['備註'], key=f"n_{uid}", height=60, on_change=update)
                        st.divider()

        with tab_todo: render_list(display_df[~display_df['is_contacted']], "todo")
        with tab_done: render_list(display_df[display_df['is_contacted']], "done", True)
        with tab_all: render_list(display_df, "all")

        if st.button("💾 儲存所有變更", type="primary", use_container_width=True):
            if st.session_state.edited_rows:
                full_df = df.copy()
                for idx, changes in st.session_state.edited_rows.items():
                    if idx in full_df.index:
                        for col, val in changes.items(): full_df.at[idx, col] = val
                if sync_data_to_gsheets(full_df):
                    st.success("儲存成功！"); st.session_state.edited_rows = {}; time.sleep(1); st.rerun()

# --- 頁面 3: 未來入學預覽 (您要求修改的核心) ---
elif menu == "📅 未來入學預覽":
    st.markdown("### 📅 未來入學名單預覽")
    this_year = date.today().year - 1911
    search_year = st.number_input("查詢學年 (民國)", value=this_year+1, min_value=this_year)
    st.divider()

    if not df.empty:
        roster = {k: {"confirmed": [], "pending": []} for k in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]}
        stats = {"total_qualified": 0, "confirmed": 0, "pending": 0}

        for idx, row in df.iterrows():
            try:
                # 1. 優先使用手動設定的年段
                grade = None
                plan_str = str(row['預計入學資訊'])
                if f"{search_year} 學年" in plan_str:
                    parts = plan_str.split(" - ")
                    if len(parts) > 1: grade = parts[1].strip()
                
                # 2. 若無手動設定，則用生日推算
                if not grade:
                    dob_parts = str(row['幼兒生日']).split('/')
                    dob_obj = date(int(dob_parts[0])+1911, int(dob_parts[1]), int(dob_parts[2]))
                    grade = get_grade_for_year(dob_obj, search_year)

                status = str(row['報名狀態'])
                is_confirmed = "已安排" in status or "已確認" in status
                is_abandon = "放棄" in status

                if grade in roster and not is_abandon:
                    stats['total_qualified'] += 1
                    item = row.to_dict(); item['original_index'] = idx
                    
                    if is_confirmed:
                        stats['confirmed'] += 1
                        roster[grade]["confirmed"].append(item)
                    else:
                        stats['pending'] += 1
                        roster[grade]["pending"].append(item)
            except: pass

        # 頂部儀表板：顯示扣除後的數字
        m1, m2, m3 = st.columns(3)
        m1.metric("✅ 已安排入學", f"{stats['confirmed']} 人")
        m2.metric("⏳ 待確認 (已扣除已安排)", f"{stats['pending']} 人", help="這是您還需要努力確認的潛在名單")
        m3.metric("📋 總符合資格", f"{stats['total_qualified']} 人")
        st.divider()

        for g in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]:
            conf = roster[g]["confirmed"]
            pend = roster[g]["pending"]
            
            with st.expander(f"📍 {g} (已安排: {len(conf)} / 待確認: {len(pend)})", expanded=(len(conf)+len(pend)>0)):
                if conf:
                    st.markdown(f"**✅ 已安排 ({len(conf)}人)**")
                    st.dataframe(pd.DataFrame(conf)[['幼兒姓名', '家長稱呼', '電話', '備註']], hide_index=True, use_container_width=True)
                
                if pend:
                    if conf: st.divider()
                    st.markdown(f"**⏳ 待確認 ({len(pend)}人) - 可直接更新狀態**")
                    
                    # 簡易編輯器
                    p_df = pd.DataFrame(pend)
                    p_df['已聯繫'] = p_df['聯繫狀態'] == '已聯繫'
                    edited = st.data_editor(
                        p_df,
                        column_config={
                            "original_index": None,
                            "聯繫狀態": None,
                            "已聯繫": st.column_config.CheckboxColumn(width="small"),
                            "報名狀態": st.column_config.SelectboxColumn(options=["排隊中", "已安排", "考慮中", "放棄"]),
                            "家長稱呼": st.column_config.TextColumn(disabled=True),
                            "電話": st.column_config.TextColumn(disabled=True),
                        },
                        hide_index=True, use_container_width=True, key=f"edit_{search_year}_{g}"
                    )

                    if st.button(f"💾 更新 {g}", key=f"btn_{search_year}_{g}"):
                        full_df = load_registered_data()
                        has_chg = False
                        for i, r in edited.iterrows():
                            oid = r['original_index']
                            new_con = "已聯繫" if r['已聯繫'] else "未聯繫"
                            if full_df.at[oid, '聯繫狀態'] != new_con: full_df.at[oid, '聯繫狀態'] = new_con; has_chg=True
                            if full_df.at[oid, '報名狀態'] != r['報名狀態']: full_df.at[oid, '報名狀態'] = r['報名狀態']; has_chg=True
                            if full_df.at[oid, '備註'] != r['備註']: full_df.at[oid, '備註'] = r['備註']; has_chg=True
                        
                        if has_chg and sync_data_to_gsheets(full_df):
                            st.success("更新成功！"); time.sleep(0.5); st.rerun()

# --- 頁面 4: 師資預估 ---
elif menu == "👩‍🏫 師資人力預估":
    st.header("📊 未來學年師生人力預估")
    ratio_daycare = st.number_input("托嬰 (0-2歲) 師生比 1:", value=5)
    ratio_toddler = st.number_input("幼幼 (2-3歲) 師生比 1:", value=8)
    ratio_normal = st.number_input("小中大 (3-6歲) 師生比 1:", value=15)
    
    calc_year = st.number_input("預估學年", value=date.today().year - 1911 + 1)
    
    counts = {k: {"confirmed": 0, "wait": 0} for k in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]}
    for _, row in df.iterrows():
        try:
            # 優先用手動設定的年段
            grade = None
            if f"{calc_year} 學年" in str(row['預計入學資訊']):
                grade = str(row['預計入學資訊']).split(" - ")[1].strip()
            
            # 否則用生日算
            if not grade:
                dob_parts = str(row['幼兒生日']).split('/')
                dob = date(int(dob_parts[0])+1911, int(dob_parts[1]), int(dob_parts[2]))
                grade = get_grade_for_year(dob, calc_year)
            
            if grade in counts:
                if "已安排" in str(row['報名狀態']): counts[grade]["confirmed"] += 1
                else: counts[grade]["wait"] += 1
        except: pass

    res = []
    rules = [("托嬰中心", ratio_daycare), ("幼幼班", ratio_toddler), ("小班", ratio_normal), ("中班", ratio_normal), ("大班", ratio_normal)]
    for g, r in rules:
        c, w = counts[g]["confirmed"], counts[g]["wait"]
        res.append({
            "班級": g, "師生比": f"1:{r}", 
            "已安排": c, "排隊中": w, 
            "預估老師數 (僅已安排)": math.ceil(c/r),
            "預估老師數 (含排隊)": math.ceil((c+w)/r)
        })
    st.dataframe(pd.DataFrame(res), use_container_width=True)
