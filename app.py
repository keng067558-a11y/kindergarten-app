import streamlit as st
import pandas as pd
from datetime import date, datetime
import math

# ==========================================
# 0. 基礎設定 (系統核心)
# ==========================================
st.set_page_config(page_title="新生與經費管理系統", layout="wide", page_icon="🏫")

# 嘗試匯入 gspread (容錯模式)
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# 嘗試匯入 st_keyup (搜尋優化)
try:
    from streamlit_keyup import st_keyup
except ImportError:
    def st_keyup(label, placeholder=None, key=None):
        return st.text_input(label, placeholder=placeholder, key=key)

st.markdown("""
<style>
    .stApp { font-family: "Microsoft JhengHei", sans-serif; }
    .streamlit-expanderHeader { background-color: #f8f9fa; border: 1px solid #eee; font-weight: bold; color: #333; }
    .stSpinner { margin-top: 20px; }
    .big-grade { font-size: 2em; font-weight: bold; color: #ff4b4b; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 資料存取邏輯
# ==========================================
SHEET_NAME = 'kindergarten_db'
LOCAL_CSV = 'kindergarten_local_db.csv'
EXPENSE_CSV = 'kindergarten_expenses.csv'

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

# --- 學生資料讀取 ---
def connect_to_gsheets_students():
    c = get_gsheet_client()
    return c.open(SHEET_NAME).sheet1 if c else None

@st.cache_data(ttl=300)
def load_registered_data():
    sheet = connect_to_gsheets_students()
    df = pd.DataFrame()
    if sheet:
        try:
            data = sheet.get_all_values()
            if data: df = pd.DataFrame(data[1:], columns=data[0])
        except: pass
    
    if df.empty:
        try: df = pd.read_csv(LOCAL_CSV)
        except: df = pd.DataFrame(columns=['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註', '重要性'])

    if '電話' in df.columns:
        df['電話'] = df['電話'].astype(str).str.strip().apply(lambda x: '0' + x if len(x) == 9 and x.startswith('9') else x)
    if '聯繫狀態' not in df.columns: df['聯繫狀態'] = '未聯繫'
    if '報名狀態' not in df.columns: df['報名狀態'] = '排隊中'
    if '重要性' not in df.columns: df['重要性'] = '中' 
    return df

def sync_data_to_gsheets(new_df):
    try:
        save_df = new_df.copy()
        for c in ['is_contacted', 'original_index', 'sort_val']: 
            if c in save_df.columns: save_df = save_df.drop(columns=[c])
        
        final_cols = ['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註', '重要性']
        for c in final_cols: 
            if c not in save_df.columns: save_df[c] = ""
        
        save_df['重要性'] = save_df['重要性'].replace('', '中').fillna('中')
        save_df = save_df[final_cols].astype(str)

        sheet = connect_to_gsheets_students()
        if sheet:
            try:
                sheet.clear()
                sheet.append_row(final_cols)
                if not save_df.empty: sheet.append_rows(save_df.values.tolist())
            except: pass 

        save_df.to_csv(LOCAL_CSV, index=False)
        load_registered_data.clear() 
        return True
    except Exception as e:
        st.error(f"儲存錯誤: {e}")
        return False

# --- 廠商發票資料讀取 ---
def connect_to_gsheets_expenses():
    c = get_gsheet_client()
    if c:
        try: return c.open(SHEET_NAME).worksheet('expenses')
        except: return None
    return None

@st.cache_data(ttl=300)
def load_expenses_data():
    sheet = connect_to_gsheets_expenses()
    df = pd.DataFrame()
    if sheet:
        try:
            data = sheet.get_all_values()
            if data: df = pd.DataFrame(data[1:], columns=data[0])
        except: pass
    
    if df.empty:
        try: df = pd.read_csv(EXPENSE_CSV)
        except: df = pd.DataFrame(columns=['日期', '廠商名稱', '計畫類別', '項目說明', '金額', '發票狀態', '備註'])
    
    if '金額' in df.columns:
        df['金額'] = pd.to_numeric(df['金額'], errors='coerce').fillna(0).astype(int)
    return df

def sync_expenses_to_gsheets(new_df):
    try:
        save_df = new_df.copy()
        final_cols = ['日期', '廠商名稱', '計畫類別', '項目說明', '金額', '發票狀態', '備註']
        for c in final_cols:
            if c not in save_df.columns: save_df[c] = ""
        save_df = save_df[final_cols]
        save_str_df = save_df.astype(str)

        sheet = connect_to_gsheets_expenses()
        if sheet:
            try:
                sheet.clear()
                sheet.append_row(final_cols)
                if not save_str_df.empty: sheet.append_rows(save_str_df.values.tolist())
            except: pass

        save_df.to_csv(EXPENSE_CSV, index=False)
        load_expenses_data.clear()
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
if 'msg_error' not in st.session_state: st.session_state['msg_error'] = None

if st.session_state['msg_error']: 
    st.error(st.session_state['msg_error'])
    st.session_state['msg_error'] = None

def add_child_cb():
    y, m, d = st.session_state.get("y_add", 112), st.session_state.get("m_add", 1), st.session_state.get("d_add", 1)
    try: dob = date(y+1911, m, d)
    except: dob = date.today()
    plans = calculate_admission_roadmap(dob)
    st.session_state.temp_children.append({
        "幼兒姓名": st.session_state.get("input_c_name", "") or "(未填)",
        "幼兒生日": to_roc_str(dob),
        "報名狀態": "預約參觀", # 預設改為預約參觀
        "預計入學資訊": plans[0] if plans else "待確認",
        "備註": st.session_state.get("input_note", ""),
        "重要性": "中"
    })
    st.session_state.input_c_name = ""
    st.session_state.input_note = ""

def submit_all_cb():
    if not st.session_state.temp_children: return
    p_name, phone = st.session_state.input_p_name, st.session_state.input_phone
    if not p_name or not phone: st.session_state['msg_error'] = "❌ 家長與電話必填"; return
    
    with st.spinner('正在雲端儲存中...'):
        cur_df = load_registered_data()
        rows = []
        for c in st.session_state.temp_children:
            rows.append({
                '報名狀態': c['報名狀態'], '聯繫狀態': '未聯繫', '登記日期': to_roc_str(date.today()),
                '幼兒姓名': c['幼兒姓名'], '家長稱呼': f"{p_name} {st.session_state.input_p_title}",
                '電話': str(phone), '幼兒生日': c['幼兒生日'], '預計入學資訊': c['預計入學資訊'],
                '推薦人': st.session_state.input_referrer, '備註': c['備註'], '重要性': c['重要性']
            })
        if sync_data_to_gsheets(pd.concat([cur_df, pd.DataFrame(rows)], ignore_index=True)):
            st.toast(f"✅ 成功新增 {len(rows)} 筆資料", icon="🎉")
            st.session_state.temp_children = []
            st.session_state.input_p_name = ""
            st.session_state.input_phone = ""

# ==========================================
# 4. 主程式與選單
# ==========================================
st.title("🏫 幼兒園新生管理系統")

with st.spinner("載入資料庫..."):
    df = load_registered_data()
    df_exp = load_expenses_data()

menu = st.sidebar.radio("功能導航", ["👶 新增報名", "📂 資料管理中心", "🎓 學年快速查詢", "💰 廠商發票管理", "📅 未來入學預覽", "👩‍🏫 師資人力預估"])

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

# --- 頁面 2: 資料管理 ---
elif menu == "📂 資料管理中心":
    st.header("📂 資料管理中心")
    col_search, col_dl = st.columns([4, 1])
    kw = st_keyup("🔍 搜尋", placeholder="電話或姓名...", key="search_kw")
    if not df.empty: col_dl.download_button("📥", df.to_csv(index=False).encode('utf-8-sig'), 'data.csv')

    if not df.empty:
        disp = df.copy()
        disp['original_index'] = disp.index
        
        # 排序優化
        prio_map = {"優": 0, "中": 1, "差": 2}
        disp['sort_val'] = disp['重要性'].map(prio_map).fillna(1)
        disp = disp.sort_values(by=['sort_val', '登記日期'], ascending=[True, False])
        
        if kw: disp = disp[disp.astype(str).apply(lambda x: x.str.contains(kw, case=False)).any(axis=1)]
        disp['is_contacted'] = disp['聯繫狀態'] == '已聯繫'

        t1, t2, t3 = st.tabs(["待聯繫", "已聯繫", "全部"])

        def render_cards_in_form(tdf, key_pfx):
            prio_opts = ["優", "中", "差"]
            counter = 1 
            
            for ph, gp in tdf.groupby('電話', sort=False):
                row_data = gp.iloc[0]
                curr_prio = row_data.get('重要性', '中')
                if curr_prio not in prio_opts: curr_prio = "中"
                
                icon_map = {"優": "🔴", "中": "🟡", "差": "⚪"}
                prio_icon = icon_map.get(curr_prio, "⚪")

                plan_str = str(row_data['預計入學資訊'])
                grade_show = plan_str.split(" - ")[-1] if " - " in plan_str else (plan_str if plan_str and plan_str != "nan" else "未定")
                
                raw_note = str(row_data['備註']).strip()
                note_str = f" | 📝 {raw_note}" if raw_note else ""
                
                expander_title = f"{counter}. {prio_icon} 【{grade_show}】 {row_data['家長稱呼']} | 📞 {ph}{note_str}"
                counter += 1
                
                with st.expander(expander_title):
                    for _, r in gp.iterrows():
                        oid = r['original_index']
                        uk = f"{key_pfx}_{oid}"
                        
                        st.markdown(f"**{r['幼兒姓名']}** | 生日：{r['幼兒生日']}")
                        
                        c1, c2 = st.columns([1, 1])
                        c1.checkbox("已聯繫", r['is_contacted'], key=f"c_{uk}")
                        
                        # [狀態選單] 加入預約參觀
                        opts = ["預約參觀", "排隊中", "確認入學", "已安排", "考慮中", "放棄", "超齡/畢業"]
                        val = r['報名狀態'] if r['報名狀態'] in opts else "排隊中"
                        c2.selectbox("狀態", opts, index=opts.index(val), key=f"s_{uk}")

                        c3, c4 = st.columns([1, 1])
                        plans = [str(r['預計入學資訊'])]
                        try:
                            dob = date(int(str(r['幼兒生日']).split('/')[0])+1911, int(str(r['幼兒生日']).split('/')[1]), int(str(r['幼兒生日']).split('/')[2]))
                            plans = calculate_admission_roadmap(dob)
                            if str(r['預計入學資訊']) not in plans: plans.insert(0, str(r['預計入學資訊']))
                        except: pass

                        c3.selectbox("預計年段", plans, index=0 if str(r['預計入學資訊']) == plans[0] else 0, key=f"p_{uk}")
                        c4.selectbox("優先等級", prio_opts, index=prio_opts.index(curr_prio), key=f"imp_{uk}")

                        st.text_area("備註內容", r['備註'], key=f"n_{uk}", height=80, placeholder="備註...")
                        st.markdown("---")
                        st.checkbox("🗑️ 刪除此筆資料 (勾選後按下方「儲存」生效)", key=f"del_{uk}")

        def process_save(tdf, key_pfx):
            with st.spinner("正在更新資料庫..."):
                fulldf = load_registered_data()
                changes_made = False
                indices_to_drop = [] 
                
                for _, r in tdf.iterrows():
                    oid = r['original_index']
                    uk = f"{key_pfx}_{oid}"
                    
                    if st.session_state.get(f"del_{uk}"):
                        indices_to_drop.append(oid)
                        changes_made = True
                        continue 
                    
                    new_contact = st.session_state.get(f"c_{uk}")
                    new_status = st.session_state.get(f"s_{uk}")
                    new_plan = st.session_state.get(f"p_{uk}")
                    new_note = st.session_state.get(f"n_{uk}")
                    new_imp = st.session_state.get(f"imp_{uk}")
                    
                    if new_contact is not None:
                        ncon_str = "已聯繫" if new_contact else "未聯繫"
                        if fulldf.at[oid, '聯繫狀態'] != ncon_str: fulldf.at[oid, '聯繫狀態'] = ncon_str; changes_made = True
                    
                    if new_status is not None and fulldf.at[oid, '報名狀態'] != new_status:
                        fulldf.at[oid, '報名狀態'] = new_status; changes_made = True
                        
                    if new_plan is not None and fulldf.at[oid, '預計入學資訊'] != new_plan:
                        fulldf.at[oid, '預計入學資訊'] = new_plan; changes_made = True
                        
                    if new_note is not None and fulldf.at[oid, '備註'] != new_note:
                        fulldf.at[oid, '備註'] = new_note; changes_made = True
                        
                    if new_imp is not None and fulldf.at[oid, '重要性'] != new_imp:
                        fulldf.at[oid, '重要性'] = new_imp; changes_made = True

                if indices_to_drop:
                    fulldf = fulldf.drop(indices_to_drop)

                if changes_made:
                    if sync_data_to_gsheets(fulldf):
                        st.toast("✅ 資料已批次更新/刪除！", icon="💾")
                        st.rerun() 
                else:
                    st.toast("沒有偵測到變更", icon="ℹ️")

        with t1:
            # 修正：檢查是否有資料，避免建立空表單導致錯誤
            target_data = disp[~disp['is_contacted']]
            if not target_data.empty:
                with st.form("form_t1"):
                    render_cards_in_form(target_data, "t1")
                    st.form_submit_button("💾 儲存本頁變更", type="primary", use_container_width=True, on_click=lambda: process_save(target_data, "t1"))
            else:
                st.info("目前沒有待聯繫的資料。")

        with t2:
            target_data = disp[disp['is_contacted']]
            if not target_data.empty:
                with st.form("form_t2"):
                    render_cards_in_form(target_data, "t2")
                    st.form_submit_button("💾 儲存本頁變更", type="primary", use_container_width=True, on_click=lambda: process_save(target_data, "t2"))
            else:
                st.info("目前沒有已聯繫的資料。")

        with t3:
            if not disp.empty:
                with st.form("form_t3"):
                    render_cards_in_form(disp, "t3")
                    st.form_submit_button("💾 儲存本頁變更", type="primary", use_container_width=True, on_click=lambda: process_save(disp, "t3"))
            else:
                st.info("目前沒有任何資料。")

# --- 頁面 2.5: 學年快速查詢 ---
elif menu == "🎓 學年快速查詢":
    st.header("🎓 學年段快速查詢")
    st.caption("輸入出生年月日，立即查看該生目前的學齡與未來入學規劃，無需建立資料。")
    
    dob = roc_date_input("請選擇幼兒生日", date(2023, 1, 1), key_suffix="quick_check")
    
    if dob:
        st.divider()
        roadmap = calculate_admission_roadmap(dob)
        
        st.subheader(f"👶 這位小朋友目前是：")
        current_status = roadmap[0] if roadmap else "年齡不符"
        grade_display = current_status.split(" - ")[-1] if " - " in current_status else current_status
        year_display = current_status.split(" - ")[0] if " - " in current_status else "目前"
        
        st.markdown(f"<div class='big-grade'>{grade_display}</div>", unsafe_allow_html=True)
        st.caption(f"學年度：{year_display}")
        
        st.markdown("### 🗓️ 未來入學路徑")
        roadmap_data = []
        for item in roadmap:
            parts = item.split(" - ")
            if len(parts) == 2:
                roadmap_data.append({"學年度": parts[0], "年段": parts[1]})
        
        if roadmap_data:
            st.dataframe(pd.DataFrame(roadmap_data), use_container_width=True, hide_index=True)
        else:
            st.warning("年齡超出範圍或無法計算。")

# --- 頁面 3: 廠商發票管理 ---
elif menu == "💰 廠商發票管理":
    st.header("💰 廠商發票管理")
    
    with st.expander("➕ 新增一筆發票/請款紀錄", expanded=False):
        with st.form("add_expense_form"):
            c1, c2 = st.columns(2)
            e_date = c1.date_input("請款日期", value=date.today())
            e_vendor = c2.text_input("廠商名稱", placeholder="輸入廠商...")
            
            c3, c4 = st.columns(2)
            proj_opts = ["一般行政", "115教保計畫", "餐點費", "教學設備", "環境修繕", "其他"]
            e_proj = c3.selectbox("計畫/經費類別", proj_opts + ["自訂..."])
            if e_proj == "自訂...": e_proj = st.text_input("輸入自訂計畫名稱")
            e_item = c4.text_input("項目說明", placeholder="買了什麼...")
            
            c5, c6 = st.columns(2)
            e_amount = c5.number_input("金額 (元)", min_value=0, step=100)
            e_status = c6.radio("發票狀態", ["✅ 已收到", "❌ 未收到"], horizontal=True)
            e_note = st.text_area("備註", height=50)

            if st.form_submit_button("💾 新增紀錄"):
                with st.spinner("儲存中..."):
                    new_row = {
                        '日期': str(e_date), '廠商名稱': e_vendor, '計畫類別': e_proj,
                        '項目說明': e_item, '金額': e_amount, '發票狀態': e_status, '備註': e_note
                    }
                    new_df = pd.concat([df_exp, pd.DataFrame([new_row])], ignore_index=True)
                    if sync_expenses_to_gsheets(new_df):
                        st.toast("已新增支出紀錄！", icon="💰")
                        st.rerun()

    if not df_exp.empty:
        total_amt = df_exp['金額'].sum()
        missing_inv = df_exp[df_exp['發票狀態'].str.contains("未收到")]
        
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 總支出金額", f"${total_amt:,}")
        m2.metric("🧾 登記筆數", f"{len(df_exp)} 筆")
        m3.metric("⚠️ 發票未到", f"{len(missing_inv)} 筆", delta_color="inverse")
        
        st.divider()
        st.subheader("📋 支出明細表")
        
        col_fil1, col_fil2 = st.columns([1, 1])
        filter_proj = col_fil1.multiselect("篩選計畫/類別", df_exp['計畫類別'].unique())
        filter_vendor = col_fil2.text_input("搜尋廠商或項目")
        
        show_df = df_exp.copy()
        if filter_proj: show_df = show_df[show_df['計畫類別'].isin(filter_proj)]
        if filter_vendor:
            show_df = show_df[
                show_df['廠商名稱'].astype(str).str.contains(filter_vendor) | 
                show_df['項目說明'].astype(str).str.contains(filter_vendor)
            ]
        
        edited_exp = st.data_editor(
            show_df,
            column_config={
                "日期": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "金額": st.column_config.NumberColumn(format="$%d"),
                "發票狀態": st.column_config.SelectboxColumn(options=["✅ 已收到", "❌ 未收到"]),
                "計畫類別": st.column_config.TextColumn(width="medium"),
            },
            num_rows="dynamic",
            use_container_width=True,
            key="expense_editor"
        )
        
        if st.button("💾 更新發票/經費紀錄"):
            with st.spinner("更新中..."):
                if sync_expenses_to_gsheets(edited_exp):
                    st.toast("資料已更新！", icon="✅")
                    st.rerun()

# --- 頁面 4: 未來預覽 ---
elif menu == "📅 未來入學預覽":
    st.header("📅 未來入學名單預覽")
    cur_y = date.today().year - 1911
    search_y = st.number_input("查詢學年", value=cur_y+1, min_value=cur_y)
    st.caption(f"💡 系統依據生日自動推算 {search_y} 學年的班級。")
    st.divider()

    if not df.empty:
        roster = {k: {"conf": [], "pend": []} for k in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]}
        stats = {"tot": 0, "conf": 0, "pend": 0}
        all_pending_list = []

        for idx, row in df.iterrows():
            try:
                grade = None
                p_str = str(row['預計入學資訊'])
                if f"{search_y} 學年" in p_str:
                    parts = p_str.split(" - ")
                    if len(parts) > 1: grade = parts[1].strip()
                if not grade:
                    dob = date(int(str(row['幼兒生日']).split('/')[0])+1911, int(str(row['幼兒生日']).split('/')[1]), int(str(row['幼兒生日']).split('/')[2]))
                    grade = get_grade_for_year(dob, search_y)

                status = str(row['報名狀態'])
                is_conf = "確認入學" in status
                is_drop = "放棄" in status

                if grade in roster and not is_drop:
                    stats['tot'] += 1
                    item = row.to_dict(); item['idx'] = idx; item['班級'] = grade
                    
                    if is_conf:
                        stats['conf'] += 1
                        roster[grade]["conf"].append(item)
                    else:
                        stats['pend'] += 1
                        roster[grade]["pend"].append(item)
                        all_pending_list.append(item)
            except: pass

        c1, c2, c3 = st.columns(3)
        c1.metric("✅ 確定入學", stats['conf'])
        c2.metric("⏳ 潛在/排隊", stats['pend'])
        c3.metric("📋 總符合人數", stats['tot'])
        
        with st.expander(f"📋 查看全校【待確認】總表 (共{len(all_pending_list)}人) - 可直接編輯", expanded=False):
            if all_pending_list:
                p_all_df = pd.DataFrame(all_pending_list)
                p_all_df['已聯繫'] = p_all_df['聯繫狀態'] == '已聯繫'
                with st.form("master_pending_form"):
                    edited_master = st.data_editor(
                        p_all_df,
                        column_order=['班級', '已聯繫', '報名狀態', '幼兒姓名', '家長稱呼', '電話', '備註'],
                        column_config={
                            "idx": None, "聯繫狀態": None,
                            "班級": st.column_config.TextColumn(width="small", disabled=True),
                            "已聯繫": st.column_config.CheckboxColumn(width="small"),
                            # [狀態選單] 這裡也加入預約參觀
                            "報名狀態": st.column_config.SelectboxColumn(options=["預約參觀", "排隊中", "確認入學", "已安排", "考慮中", "放棄"], width="medium"),
                            "幼兒姓名": st.column_config.TextColumn(disabled=True),
                            "家長稱呼": st.column_config.TextColumn(disabled=True),
                            "電話": st.column_config.TextColumn(disabled=True),
                            "備註": st.column_config.TextColumn(width="large"),
                        },
                        hide_index=True, use_container_width=True
                    )
                    st.caption("ℹ️ 將狀態改為「確認入學」並儲存，學生就會移動到下方的確認名單。")
                    if st.form_submit_button("💾 儲存待確認清單變更"):
                        with st.spinner("更新中..."):
                            fulldf = load_registered_data()
                            chg = False
                            for i, r in edited_master.iterrows():
                                oid = r['idx']
                                ncon = "已聯繫" if r['已聯繫'] else "未聯繫"
                                if fulldf.at[oid, '聯繫狀態']!=ncon: fulldf.at[oid, '聯繫狀態']=ncon; chg=True
                                if fulldf.at[oid, '報名狀態']!=r['報名狀態']: fulldf.at[oid, '報名狀態']=r['報名狀態']; chg=True
                                if fulldf.at[oid, '備註']!=r['備註']: fulldf.at[oid, '備註']=r['備註']; chg=True
                            if chg and sync_data_to_gsheets(fulldf):
                                st.toast("更新成功", icon="✅")
                                st.rerun()
            else: st.info("目前沒有待確認的學生。")

        st.markdown("---")
        st.subheader(f"🏆 {search_y} 學年度 - 確認入學名單 (僅顯示確認入學)")
        col_l, col_m, col_s = st.columns(3)
        def render_board(column, title, data):
            with column:
                st.markdown(f"##### {title} ({len(data)}人)")
                if data:
                    disp_df = pd.DataFrame(data)[['家長稱呼', '電話', '備註']]
                    st.dataframe(disp_df, hide_index=True, use_container_width=True)
                else: st.info("尚無名單")

        render_board(col_l, "🐘 大班", roster["大班"]["conf"])
        render_board(col_m, "🦁 中班", roster["中班"]["conf"])
        render_board(col_s, "🐰 小班", roster["小班"]["conf"])
        st.write("") 
        col_t, col_d, col_x = st.columns(3)
        render_board(col_t, "🐥 幼幼班", roster["幼幼班"]["conf"])
        render_board(col_d, "🍼 托嬰中心", roster["托嬰中心"]["conf"])
        
# --- 頁面 5: 師資預估 ---
elif menu == "👩‍🏫 師資人力預估":
    st.header("📊 師資人力預估")
    cal_y = st.number_input("預估學年", value=date.today().year - 1911 + 1)
    
    default_ratio = 12 if cal_y >= 115 else 15
    if cal_y >= 115: st.caption("ℹ️ 115學年度起準公幼師生比調整為 **1:12**。")

    with st.expander("⚙️ 師生比參數設定", expanded=True):
        c1, c2, c3 = st.columns(3)
        r_d = c1.number_input("托嬰 (0-2歲) 1:", 5)
        r_t = c2.number_input("幼幼 (2-3歲) 1:", 8)
        r_k = c3.number_input("小中大 (3-6歲) 1:", value=default_ratio)
    
    cts = {k: {"c": 0, "w": 0} for k in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]}
    for _, r in df.iterrows():
        try:
            gr = None
            if f"{cal_y} 學年" in str(r['預計入學資訊']): gr = str(r['預計入學資訊']).split("-")[1].strip()
            if not gr:
                dob = date(int(str(r['幼兒生日']).split('/')[0])+1911, int(str(r['幼兒生日']).split('/')[1]), int(str(r['幼兒生日']).split('/')[2]))
                gr = get_grade_for_year(dob, cal_y)
            
            if gr in cts:
                if "確認入學" in str(r['報名狀態']): cts[gr]["c"] += 1
                else: cts[gr]["w"] += 1
        except: pass

    data = []
    for g, rat in [("托嬰中心", r_d), ("幼幼班", r_t), ("小班", r_k), ("中班", r_k), ("大班", r_k)]:
        c, w = cts[g]["c"], cts[g]["w"]
        data.append({"班級": g, "師生比": f"1:{rat}", "確認入學": c, "排隊/潛在": w, 
                     "需老師(確)": math.ceil(c/rat), "需老師(含排)": math.ceil((c+w)/rat)})
    st.dataframe(pd.DataFrame(data), use_container_width=True)
