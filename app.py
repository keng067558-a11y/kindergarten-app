import streamlit as st
import pandas as pd
from datetime import date, datetime
import math
import time
import uuid

# ==========================================
# 0. 基礎設定 (絕不能刪除)
# ==========================================
st.set_page_config(page_title="新生管理系統", layout="wide", page_icon="🏫")

# 嘗試匯入 gspread (容錯模式)
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
# 1. 資料存取邏輯
# ==========================================
SHEET_NAME = 'kindergarten_db'
LOCAL_CSV = 'kindergarten_local_db.csv'
STUDENT_CSV = 'students.csv'

def check_password():
    if "password_correct" not in st.session_state: st.session_state.password_correct = False
    if not st.session_state.password_correct:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.title("🔒 系統登入")
            pwd = st.text_input("請輸入通關密碼", type="password")
            if st.button("登入", type="primary"):
                if pwd == "1234": st.session_state.password_correct = True; st.rerun()
                else: st.error("密碼錯誤")
        return False
    return True

if not check_password(): st.stop()

@st.cache_resource
def get_gsheet_client():
    if not HAS_GSPREAD: return None
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        if "gcp_service_account" not in st.secrets: return None
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        return gspread.authorize(creds)
    except: return None

def connect_to_gsheets():
    c = get_gsheet_client()
    return c.open(SHEET_NAME).sheet1 if c else None

@st.cache_data(ttl=60)
def load_registered_data():
    sheet = connect_to_gsheets()
    df = pd.DataFrame()
    if sheet:
        try:
            data = sheet.get_all_values()
            if data: df = pd.DataFrame(data[1:], columns=data[0])
        except: pass
    
    if df.empty:
        try: df = pd.read_csv(LOCAL_CSV)
        except: df = pd.DataFrame(columns=['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註'])

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
        for c in ['is_contacted', 'original_index']: 
            if c in save_df.columns: save_df = save_df.drop(columns=[c])
        
        final_cols = ['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註']
        for c in final_cols: 
            if c not in save_df.columns: save_df[c] = ""
        save_df = save_df[final_cols].astype(str)

        sheet = connect_to_gsheets()
        if sheet:
            try:
                sheet.clear()
                sheet.append_row(final_cols)
                if not save_df.empty: sheet.append_rows(save_df.values.tolist())
            except: pass # GSheet 失敗不中斷

        save_df.to_csv(LOCAL_CSV, index=False)
        load_registered_data.clear()
        return True
    except Exception as e:
        st.error(f"儲存錯誤: {e}")
        return False

# ==========================================
# 2. 核心計算邏輯
# ==========================================
def roc_date_input(label, default_date=None, key_suffix=""):
    st.write(f"**{label}**")
    c1, c2, c3 = st.columns([1, 1, 1])
    if default_date is None: default_date = date.today()
    cur_roc = default_date.year - 1911
    
    y = c1.selectbox("年", range(90, 131), index=(cur_roc - 90), key=f"y_{key_suffix}")
    m = c2.selectbox("月", range(1, 13), index=default_date.month-1, key=f"m_{key_suffix}")
    d = c3.selectbox("日", range(1, 32), index=default_date.day-1, key=f"d_{key_suffix}")
    try: return date(y + 1911, m, d)
    except: return date.today()

def to_roc_str(d): return f"{d.year-1911}/{d.month:02d}/{d.day:02d}"

def get_grade_for_year(birth_date, target_roc_year):
    if not birth_date: return "未知"
    by_roc = birth_date.year - 1911
    offset = 1 if (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2) else 0
    age = target_roc_year - by_roc - offset
    if age < 2: return "托嬰中心"
    if age == 2: return "幼幼班"
    if age == 3: return "小班"
    if age == 4: return "中班"
    if age == 5: return "大班"
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
    return roadmap if roadmap else ["年齡不符"]

# ==========================================
# 3. 頁面邏輯 (狀態與Callback)
# ==========================================
if 'temp_children' not in st.session_state: st.session_state.temp_children = []
if 'edited_rows' not in st.session_state: st.session_state.edited_rows = {}
for k in ['msg_success', 'msg_error']: 
    if k not in st.session_state: st.session_state[k] = None

if st.session_state['msg_success']: st.success(st.session_state['msg_success']); st.session_state['msg_success']=None
if st.session_state['msg_error']: st.error(st.session_state['msg_error']); st.session_state['msg_error']=None

def add_child_cb():
    y, m, d = st.session_state.get("y_add", 112), st.session_state.get("m_add", 1), st.session_state.get("d_add", 1)
    try: dob = date(y+1911, m, d)
    except: dob = date.today()
    plans = calculate_admission_roadmap(dob)
    st.session_state.temp_children.append({
        "幼兒姓名": st.session_state.get("input_c_name", "") or "(未填)",
        "幼兒生日": to_roc_str(dob),
        "報名狀態": "排隊中",
        "預計入學資訊": plans[0] if plans else "待確認",
        "備註": st.session_state.get("input_note", "")
    })
    st.session_state.input_c_name = ""
    st.session_state.input_note = ""

def submit_all_cb():
    if not st.session_state.temp_children: return
    p_name, phone = st.session_state.input_p_name, st.session_state.input_phone
    if not p_name or not phone: st.session_state['msg_error'] = "❌ 家長與電話必填"; return
    
    cur_df = load_registered_data()
    rows = []
    for c in st.session_state.temp_children:
        rows.append({
            '報名狀態': c['報名狀態'], '聯繫狀態': '未聯繫', '登記日期': to_roc_str(date.today()),
            '幼兒姓名': c['幼兒姓名'], '家長稱呼': f"{p_name} {st.session_state.input_p_title}",
            '電話': str(phone), '幼兒生日': c['幼兒生日'], '預計入學資訊': c['預計入學資訊'],
            '推薦人': st.session_state.input_referrer, '備註': c['備註']
        })
    if sync_data_to_gsheets(pd.concat([cur_df, pd.DataFrame(rows)], ignore_index=True)):
        st.session_state['msg_success'] = f"✅ 新增 {len(rows)} 筆資料"
        st.session_state.temp_children = []
        st.session_state.input_p_name = ""
        st.session_state.input_phone = ""

# ==========================================
# 4. 主程式與選單 (最關鍵的結構)
# ==========================================
st.title("🏫 幼兒園新生管理系統")
df = load_registered_data()

# ⚠️ 這是控制頁面的總開關，絕對不能被覆蓋
menu = st.sidebar.radio("功能導航", ["👶 新增報名", "📂 資料管理中心", "📅 未來入學預覽", "👩‍🏫 師資人力預估"])

# --- 頁面 1: 新增 ---
if menu == "👶 新增報名":
    st.header("📝 新生報名登記")
    c1, c2 = st.columns(2)
    with c1:
        st.info("👤 **家長資訊**")
        st.text_input("家長姓氏", key="input_p_name")
        st.selectbox("稱謂", ["先生", "小姐", "爸爸", "媽媽"], key="input_p_title")
        st.text_input("電話", key="input_phone")
        st.text_input("推薦人", key="input_referrer")
    with c2:
        st.success("👶 **幼兒資訊**")
        st.text_input("幼兒姓名", key="input_c_name")
        roc_date_input("出生日", date(2022, 1, 1), key_suffix="add")
        st.text_area("備註", key="input_note", height=100)
        st.button("⬇️ 加入暫存", on_click=add_child_cb)
    
    if st.session_state.temp_children:
        st.divider()
        st.write(f"🛒 **待送出 ({len(st.session_state.temp_children)})**")
        for i, c in enumerate(st.session_state.temp_children):
            st.text(f"{i+1}. {c['幼兒姓名']} ({c['幼兒生日']}) - {c['預計入學資訊']}")
            if st.button("❌ 移除", key=f"rm_{i}"): 
                st.session_state.temp_children.pop(i)
                st.rerun()
        st.button("✅ 確認送出", type="primary", on_click=submit_all_cb, use_container_width=True)

# --- 頁面 2: 資料管理 (含刪除按鈕) ---
elif menu == "📂 資料管理中心":
    st.header("📂 資料管理中心")
    col_search, col_dl = st.columns([4, 1])
    kw = st_keyup("🔍 搜尋", placeholder="電話或姓名...", key="search_kw")
    if not df.empty: col_dl.download_button("📥", df.to_csv(index=False).encode('utf-8-sig'), 'data.csv')

    if not df.empty:
        disp = df.copy()
        disp['original_index'] = disp.index
        if kw: disp = disp[disp.astype(str).apply(lambda x: x.str.contains(kw, case=False)).any(axis=1)]
        disp['is_contacted'] = disp['聯繫狀態'] == '已聯繫'

        t1, t2, t3 = st.tabs(["待聯繫", "已聯繫", "全部"])

        def render_cards(tdf, key_pfx):
            if tdf.empty: st.caption("無資料"); return
            for ph, gp in tdf.groupby('電話'):
                with st.expander(f"👤 {gp.iloc[0]['家長稱呼']} | 📞 {ph}"):
                    for _, r in gp.iterrows():
                        oid = r['original_index']
                        uk = f"{key_pfx}_{oid}"
                        st.markdown(f"**{r['幼兒姓名']}** | {r['幼兒生日']}")
                        
                        c1, c2 = st.columns(2)
                        
                        def upd(idx=oid, k=uk):
                            if idx not in st.session_state.edited_rows: st.session_state.edited_rows[idx]={}
                            st.session_state.edited_rows[idx]['聯繫狀態'] = "已聯繫" if st.session_state[f"c_{k}"] else "未聯繫"
                            st.session_state.edited_rows[idx]['報名狀態'] = st.session_state[f"s_{k}"]
                            st.session_state.edited_rows[idx]['預計入學資訊'] = st.session_state[f"p_{k}"]
                            st.session_state.edited_rows[idx]['備註'] = st.session_state[f"n_{k}"]

                        c1.checkbox("已聯繫", r['is_contacted'], key=f"c_{uk}", on_change=upd)
                        opts = ["排隊中", "已安排", "考慮中", "放棄", "超齡/畢業"]
                        val = r['報名狀態'] if r['報名狀態'] in opts else opts[0]
                        c2.selectbox("狀態", opts, index=opts.index(val), key=f"s_{uk}", on_change=upd)

                        try: 
                            dob = date(int(str(r['幼兒生日']).split('/')[0])+1911, int(str(r['幼兒生日']).split('/')[1]), int(str(r['幼兒生日']).split('/')[2]))
                            plans = calculate_admission_roadmap(dob)
                        except: plans = ["無法計算"]
                        plan_val = str(r['預計入學資訊'])
                        if plan_val not in plans: plans.insert(0, plan_val)
                        st.selectbox("預計年段", plans, index=plans.index(plan_val), key=f"p_{uk}", on_change=upd)
                        st.text_area("備註", r['備註'], key=f"n_{uk}", height=60, on_change=upd)
                        
                        # [新增] 刪除按鈕
                        if st.button("🗑️ 刪除", key=f"del_{uk}"):
                            if sync_data_to_gsheets(df.drop(oid)):
                                st.success("已刪除"); time.sleep(0.5); st.rerun()
                        st.divider()

        with t1: render_cards(disp[~disp['is_contacted']], "t1")
        with t2: render_cards(disp[disp['is_contacted']], "t2")
        with t3: render_cards(disp, "t3")

        if st.button("💾 儲存所有變更", type="primary", use_container_width=True):
            if st.session_state.edited_rows:
                fulldf = df.copy()
                for i, chg in st.session_state.edited_rows.items():
                    if i in fulldf.index:
                        for k, v in chg.items(): fulldf.at[i, k] = v
                if sync_data_to_gsheets(fulldf):
                    st.success("儲存成功"); st.session_state.edited_rows={}; time.sleep(1); st.rerun()

# --- 頁面 3: 未來預覽 (移除 幼兒姓名/狀態/推薦人) ---
elif menu == "📅 未來入學預覽":
    st.header("📅 未來入學名單預覽")
    cur_y = date.today().year - 1911
    search_y = st.number_input("查詢學年", value=cur_y+1, min_value=cur_y)
    st.caption(f"💡 包含依生日自動推算至 {search_y} 學年的孩子")
    st.divider()

    if not df.empty:
        roster = {k: {"conf": [], "pend": []} for k in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]}
        stats = {"tot": 0, "conf": 0, "pend": 0}

        for idx, row in df.iterrows():
            try:
                # 1. 優先用手動設定
                grade = None
                p_str = str(row['預計入學資訊'])
                if f"{search_year} 學年" in p_str:
                    parts = p_str.split(" - ")
                    if len(parts) > 1: grade = parts[1].strip()
                
                # 2. 自動推算 (這就是為什麼 115中班 會出現在 116大班)
                if not grade:
                    dob = date(int(str(row['幼兒生日']).split('/')[0])+1911, int(str(row['幼兒生日']).split('/')[1]), int(str(row['幼兒生日']).split('/')[2]))
                    grade = get_grade_for_year(dob, search_y)

                status = str(row['報名狀態'])
                is_conf = "已安排" in status or "已確認" in status
                is_drop = "放棄" in status

                if grade in roster and not is_drop:
                    stats['tot'] += 1
                    item = row.to_dict(); item['idx'] = idx
                    if is_conf:
                        stats['conf'] += 1
                        roster[grade]["conf"].append(item)
                    else:
                        stats['pend'] += 1
                        roster[grade]["pend"].append(item)
            except: pass

        c1, c2, c3 = st.columns(3)
        c1.metric("✅ 已安排", stats['conf'])
        c2.metric("⏳ 待確認", stats['pend'])
        c3.metric("📋 總符合", stats['tot'])
        st.divider()

        for g in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]:
            cf = roster[g]["conf"]
            pd_list = roster[g]["pend"]
            
            with st.expander(f"📍 {g} (已安排: {len(cf)} / 待確認: {len(pd_list)})", expanded=(len(cf)+len(pd_list)>0)):
                if cf:
                    st.markdown(f"**✅ 已安排 ({len(cf)})**")
                    # [修改] 只顯示 家長/電話/備註 (隱藏 姓名/狀態/推薦人)
                    st.dataframe(pd.DataFrame(cf)[['家長稱呼', '電話', '備註']], hide_index=True, use_container_width=True)
                
                if pd_list:
                    if cf: st.divider()
                    st.markdown(f"**⏳ 待確認 ({len(pd_list)})**")
                    
                    pdf = pd.DataFrame(pd_list)
                    pdf['已聯繫'] = pdf['聯繫狀態'] == '已聯繫'
                    
                    # [修改] Data Editor 也只顯示有限欄位
                    edited = st.data_editor(
                        pdf,
                        column_order=['已聯繫', '家長稱呼', '電話', '備註'],
                        column_config={
                            "已聯繫": st.column_config.CheckboxColumn(width="small"),
                            "家長稱呼": st.column_config.TextColumn(disabled=True),
                            "電話": st.column_config.TextColumn(disabled=True),
                            "備註": st.column_config.TextColumn(width="large"),
                        },
                        hide_index=True, use_container_width=True, key=f"ed_{g}"
                    )
                    
                    if st.button(f"💾 更新 {g}", key=f"btn_{g}"):
                        fulldf = load_registered_data()
                        chg = False
                        for i, r in edited.iterrows():
                            oid = r['idx']
                            new_con = "已聯繫" if r['已聯繫'] else "未聯繫"
                            if fulldf.at[oid, '聯繫狀態'] != new_con: fulldf.at[oid, '聯繫狀態']=new_con; chg=True
                            if fulldf.at[oid, '備註'] != r['備註']: fulldf.at[oid, '備註']=r['備註']; chg=True
                        
                        if chg and sync_data_to_gsheets(fulldf):
                            st.success("更新成功"); time.sleep(0.5); st.rerun()

# --- 頁面 4: 師資預估 ---
elif menu == "👩‍🏫 師資人力預估":
    st.header("📊 師資人力預估")
    r_d = st.number_input("托嬰 (0-2歲) 1:", 5)
    r_t = st.number_input("幼幼 (2-3歲) 1:", 8)
    r_k = st.number_input("小中大 (3-6歲) 1:", 15)
    cal_y = st.number_input("預估學年", date.today().year - 1911 + 1)
    
    cts = {k: {"c": 0, "w": 0} for k in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]}
    for _, r in df.iterrows():
        try:
            gr = None
            if f"{cal_y} 學年" in str(r['預計入學資訊']): gr = str(r['預計入學資訊']).split("-")[1].strip()
            if not gr:
                dob = date(int(str(r['幼兒生日']).split('/')[0])+1911, int(str(r['幼兒生日']).split('/')[1]), int(str(r['幼兒生日']).split('/')[2]))
                gr = get_grade_for_year(dob, cal_y)
            
            if gr in cts:
                if "已安排" in str(r['報名狀態']): cts[gr]["c"] += 1
                else: cts[gr]["w"] += 1
        except: pass

    data = []
    for g, rat in [("托嬰中心", r_d), ("幼幼班", r_t), ("小班", r_k), ("中班", r_k), ("大班", r_k)]:
        c, w = cts[g]["c"], cts[g]["w"]
        data.append({"班級": g, "師生比": f"1:{rat}", "已安排": c, "排隊": w, 
                     "需老師(確)": math.ceil(c/rat), "需老師(含排)": math.ceil((c+w)/rat)})
    st.dataframe(pd.DataFrame(data), use_container_width=True)
