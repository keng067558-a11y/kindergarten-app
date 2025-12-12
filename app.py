import streamlit as st
import pandas as pd
from datetime import date, datetime
import math

# ==========================================
# 0. 基礎設定 (系統核心)
# ==========================================
st.set_page_config(page_title="新生與經費管理系統", layout="wide", page_icon="🏫")

# 嘗試匯入 gspread (容錯模式：若無安裝也不會當機)
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
    # 若無安裝，使用標準 text_input 替代
    def st_keyup(label, placeholder=None, key=None):
        return st.text_input(label, placeholder=placeholder, key=key)

# 自訂 CSS 樣式
st.markdown("""
<style>
    .stApp { font-family: "Microsoft JhengHei", sans-serif; }
    .streamlit-expanderHeader { background-color: #f8f9fa; border: 1px solid #eee; font-weight: bold; color: #333; }
    .stSpinner { margin-top: 20px; }
    .big-grade { font-size: 2em; font-weight: bold; color: #ff4b4b; }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        gap: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# 定義全域新的狀態選項 (簡化版)
NEW_STATUS_OPTIONS = ["預約參觀", "排隊等待", "確認入學", "確定不收"]

# ==========================================
# 1. 資料存取邏輯
# ==========================================
SHEET_NAME = 'kindergarten_db'
LOCAL_CSV = 'kindergarten_local_db.csv'

def check_password():
    """簡單的密碼驗證機制"""
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
    """連線 Google Sheets"""
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
    """讀取資料 (優先讀取 Google Sheets，失敗則讀取 CSV，再失敗則建立空表)"""
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

    # 資料清洗與預設值填充
    df = df.fillna("")
    if '電話' in df.columns:
        df['電話'] = df['電話'].astype(str).str.strip().apply(lambda x: '0' + x if len(x) == 9 and x.startswith('9') else x)
    if '聯繫狀態' not in df.columns: df['聯繫狀態'] = '未聯繫'
    if '報名狀態' not in df.columns: df['報名狀態'] = '排隊等待'
    if '重要性' not in df.columns: df['重要性'] = '中' 
    return df

def sync_data_to_gsheets(new_df):
    """將資料同步回 Google Sheets 與本地 CSV"""
    try:
        save_df = new_df.copy()
        # 清理暫存欄位 (這些欄位不需要存入資料庫)
        for c in ['is_contacted', 'original_index', 'sort_val', 'sort_temp']: 
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
        load_registered_data.clear() # 清除快取，確保下次讀取最新資料
        return True
    except Exception as e:
        st.error(f"儲存錯誤: {e}")
        return False

# ==========================================
# 2. 核心計算邏輯
# ==========================================
def roc_date_input(label, default_date=None, key_suffix=""):
    """民國日期選擇器"""
    st.write(f"**{label} (民國)**")
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
    """計算指定學年的年級 (依據 9/2 分界)"""
    if not birth_date: return "未知"
    by_roc = birth_date.year - 1911
    # 學制分界：9月2日 (含) 以後出生算下一年
    offset = 1 if (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2) else 0
    age = target_roc_year - by_roc - offset
    if age < 2: return "托嬰中心"
    if age == 2: return "幼幼班"
    if age == 3: return "小班"
    if age == 4: return "中班"
    if age == 5: return "大班"
    return "畢業/超齡"

def calculate_admission_roadmap(dob):
    """計算未來幾年的入學規劃"""
    today = date.today()
    cur_roc = today.year - 1911
    # 若現在是 1-7 月，學年要算前一年 (例如 2024/5 是 112 學年下學期)
    if today.month < 8: cur_roc -= 1
    roadmap = []
    for i in range(6): 
        target = cur_roc + i
        grade = get_grade_for_year(dob, target)
        if "畢業" not in grade: roadmap.append(f"{target} 學年 - {grade}")
    return roadmap if roadmap else ["年齡不符"]

# ==========================================
# 3. 暫存與提交邏輯
# ==========================================
if 'temp_children' not in st.session_state: st.session_state.temp_children = []
if 'msg_error' not in st.session_state: st.session_state['msg_error'] = None

if st.session_state['msg_error']: 
    st.error(st.session_state['msg_error'])
    st.session_state['msg_error'] = None

def add_child_cb():
    """將單筆資料加入暫存區"""
    y, m, d = st.session_state.get("y_add", 112), st.session_state.get("m_add", 1), st.session_state.get("d_add", 1)
    try: dob = date(y+1911, m, d)
    except: dob = date.today()
    plans = calculate_admission_roadmap(dob)
    st.session_state.temp_children.append({
        "幼兒姓名": st.session_state.get("input_c_name", "") or "(未填)",
        "幼兒生日": to_roc_str(dob),
        "報名狀態": "預約參觀", # 預設狀態
        "預計入學資訊": plans[0] if plans else "待確認",
        "備註": st.session_state.get("input_note", ""),
        "重要性": "中"
    })
    # 清空輸入欄位
    st.session_state.input_c_name = ""
    st.session_state.input_note = ""

def submit_all_cb():
    """將暫存區資料寫入資料庫"""
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

# 選單 (已移除廠商發票管理)
menu = st.sidebar.radio("功能導航", ["👶 新增報名", "📂 資料管理中心", "🎓 學年快速查詢", "📅 未來入學預覽", "👩‍🏫 師資人力預估"])

# ------------------------------------------
# 頁面 1: 新增報名
# ------------------------------------------
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

# ------------------------------------------
# 頁面 2: 資料管理中心 (卡片式 + 狀態分組)
# ------------------------------------------
elif menu == "📂 資料管理中心":
    st.header("📂 資料管理中心")
    col_search, col_dl = st.columns([4, 1])
    kw = st_keyup("🔍 搜尋", placeholder="電話或姓名...", key="search_kw")
    if not df.empty: col_dl.download_button("📥", df.to_csv(index=False).encode('utf-8-sig'), 'data.csv')

    if not df.empty:
        disp = df.copy()
        disp['original_index'] = disp.index
        
        # 全局搜尋過濾
        if kw: disp = disp[disp.astype(str).apply(lambda x: x.str.contains(kw, case=False)).any(axis=1)]
        disp['is_contacted'] = disp['聯繫狀態'] == '已聯繫'

        # 分頁籤
        t1, t2, t3 = st.tabs(["🔴 待聯繫", "🟢 已聯繫", "📁 全部資料"])

        # === 核心：狀態分類卡片渲染函數 ===
        def render_status_cards(tdf, key_pfx):
            # 定義新的簡化狀態分類
            status_groups = {
                "🔥 預約與參觀": ["預約參觀"],
                "⏳ 排隊等待 (含其他)": ["排隊等待"], # 預設 Catch-all
                "✅ 確認入學": ["確認入學"],
                "❌ 確定不收": ["確定不收"]
            }
            
            # 定義目前系統認定的所有狀態 (用於過濾 catch-all)
            known_list = ["預約參觀", "排隊等待", "確認入學", "確定不收"]

            # 依序渲染每個區塊
            for group_name, status_list in status_groups.items():
                if group_name == "⏳ 排隊等待 (含其他)":
                    # 包含「排隊等待」以及所有「非標準選項」(例如舊資料的 考慮中/已安排/放棄/空白)
                    sub_df = tdf[tdf['報名狀態'].isin(status_list) | ~tdf['報名狀態'].isin(known_list)]
                else:
                    sub_df = tdf[tdf['報名狀態'].isin(status_list)]

                if not sub_df.empty:
                    with st.expander(f"{group_name} (共 {len(sub_df)} 筆)", expanded=True):
                        # 依重要性排序 (優 > 中 > 差)
                        prio_map = {"優": 0, "中": 1, "差": 2}
                        sub_df['sort_temp'] = sub_df['重要性'].map(prio_map).fillna(1)
                        sub_df = sub_df.sort_values(by=['sort_temp', '登記日期'], ascending=[True, False])

                        for _, r in sub_df.iterrows():
                            oid = r['original_index']
                            uk = f"{key_pfx}_{oid}"
                            
                            # 卡片容器
                            with st.container(border=True):
                                # 1. 標題列
                                top_c1, top_c2 = st.columns([3, 1])
                                priority_icon = {"優": "🔴", "中": "🟡", "差": "⚪"}.get(r['重要性'], "⚪")
                                top_c1.markdown(f"**{priority_icon} {r['幼兒姓名']}** | {r['幼兒生日']} | {r['家長稱呼']}")
                                top_c2.caption(f"📞 {r['電話']}")

                                # 2. 操作列
                                r1, r2, r3, r4 = st.columns([1.2, 1.2, 1.5, 1])
                                
                                # 聯繫
                                r1.checkbox("已聯繫", r['is_contacted'], key=f"c_{uk}")
                                
                                # 狀態 (自動處理舊資料對應)
                                cur_stat = r['報名狀態']
                                # 如果目前狀態不在新選項中，UI 預設顯示「排隊等待」，但原資料不變直到使用者按下儲存
                                ui_stat_idx = NEW_STATUS_OPTIONS.index("排隊等待")
                                if cur_stat in NEW_STATUS_OPTIONS:
                                    ui_stat_idx = NEW_STATUS_OPTIONS.index(cur_stat)
                                
                                r2.selectbox("狀態", NEW_STATUS_OPTIONS, index=ui_stat_idx, key=f"s_{uk}", label_visibility="collapsed")

                                # 年段
                                curr_plan = str(r['預計入學資訊'])
                                if curr_plan == 'nan': curr_plan = ""
                                plans = [curr_plan]
                                try:
                                    dob_obj = date(int(str(r['幼兒生日']).split('/')[0])+1911, int(str(r['幼兒生日']).split('/')[1]), int(str(r['幼兒生日']).split('/')[2]))
                                    plans = calculate_admission_roadmap(dob_obj)
                                    if curr_plan and curr_plan not in plans: plans.insert(0, curr_plan)
                                except: pass
                                
                                p_idx = 0
                                if curr_plan in plans: p_idx = plans.index(curr_plan)
                                r3.selectbox("入學年段", plans, index=p_idx, key=f"p_{uk}", label_visibility="collapsed")
                                
                                # 優先度
                                r4.selectbox("優先", ["優", "中", "差"], index=["優", "中", "差"].index(r['重要性'] if r['重要性'] in ["優", "中", "差"] else "中"), key=f"imp_{uk}", label_visibility="collapsed")

                                # 3. 備註與刪除
                                n_val = r['備註'] if str(r['備註'])!='nan' else ""
                                st.text_area("備註", n_val, key=f"n_{uk}", height=68, placeholder="在此輸入備註...")
                                
                                b1, b2 = st.columns([5, 1])
                                with b1: st.caption(f"登記日: {r['登記日期']}")
                                with b2: st.checkbox("刪除", key=f"del_{uk}")

        # === 儲存邏輯 (使用返回值判斷，確保表單資料已更新) ===
        def process_save_status(tdf, key_pfx):
            with st.spinner("正在比對並儲存資料..."):
                fulldf = load_registered_data().copy()
                changes_made = False
                indices_to_drop = [] 
                
                for _, r in tdf.iterrows():
                    oid = r['original_index']
                    uk = f"{key_pfx}_{oid}"
                    
                    # 1. 檢查刪除
                    if st.session_state.get(f"del_{uk}"):
                        indices_to_drop.append(oid)
                        changes_made = True
                        continue 
                    
                    # 2. 讀取 Widget 值
                    new_contact = st.session_state.get(f"c_{uk}")
                    new_status = st.session_state.get(f"s_{uk}")
                    new_plan = st.session_state.get(f"p_{uk}")
                    new_note = st.session_state.get(f"n_{uk}")
                    new_imp = st.session_state.get(f"imp_{uk}")
                    
                    def strict_val(v): 
                        s = str(v).strip()
                        return "" if s == 'nan' else s

                    # 3. 比對變更
                    if new_contact is not None:
                        ncon_str = "已聯繫" if new_contact else "未聯繫"
                        if strict_val(fulldf.at[oid, '聯繫狀態']) != strict_val(ncon_str):
                            fulldf.at[oid, '聯繫狀態'] = ncon_str; changes_made = True
                    
                    if new_status is not None:
                        if strict_val(fulldf.at[oid, '報名狀態']) != strict_val(new_status):
                            fulldf.at[oid, '報名狀態'] = new_status; changes_made = True
                        
                    if new_plan is not None:
                        if strict_val(fulldf.at[oid, '預計入學資訊']) != strict_val(new_plan):
                            fulldf.at[oid, '預計入學資訊'] = new_plan; changes_made = True
                        
                    if new_note is not None:
                        if strict_val(fulldf.at[oid, '備註']) != strict_val(new_note):
                            fulldf.at[oid, '備註'] = new_note; changes_made = True
                        
                    if new_imp is not None:
                        if strict_val(fulldf.at[oid, '重要性']) != strict_val(new_imp):
                            fulldf.at[oid, '重要性'] = new_imp; changes_made = True

                # 4. 執行變更
                if indices_to_drop: fulldf = fulldf.drop(indices_to_drop)

                if changes_made:
                    if sync_data_to_gsheets(fulldf):
                        st.toast("✅ 資料已成功更新並儲存！", icon="💾")
                        st.rerun() 
                    else:
                        st.error("儲存失敗，請檢查網路或權限。")
                else:
                    st.toast("系統沒有偵測到任何資料變更。", icon="ℹ️")

        with t1:
            target_data = disp[~disp['is_contacted']]
            if not target_data.empty:
                with st.form("form_t1"):
                    render_status_cards(target_data, "t1")
                    st.write("")
                    submitted_t1 = st.form_submit_button("💾 儲存所有變更", type="primary", use_container_width=True)
                if submitted_t1: process_save_status(target_data, "t1")
            else: st.info("🎉 太棒了！目前沒有待聯繫的名單。")

        with t2:
            target_data = disp[disp['is_contacted']]
            if not target_data.empty:
                with st.form("form_t2"):
                    render_status_cards(target_data, "t2")
                    st.write("")
                    submitted_t2 = st.form_submit_button("💾 儲存所有變更", type="primary", use_container_width=True)
                if submitted_t2: process_save_status(target_data, "t2")
            else: st.info("目前沒有已聯繫的資料。")

        with t3:
            if not disp.empty:
                with st.form("form_t3"):
                    render_status_cards(disp, "t3")
                    st.write("")
                    submitted_t3 = st.form_submit_button("💾 儲存所有變更", type="primary", use_container_width=True)
                if submitted_t3: process_save_status(disp, "t3")
            else: st.info("資料庫是空的。")

# ------------------------------------------
# 頁面 3: 學年快速查詢 (新增西元查詢與對照表)
# ------------------------------------------
elif menu == "🎓 學年快速查詢":
    st.header("🎓 學年段快速查詢")
    
    tab_q1, tab_q2 = st.tabs(["📅 生日查詢 (計算)", "📊 年度對照總表"])

    with tab_q1:
        st.caption("輸入出生年月日，立即查看該生目前的學齡與未來入學規劃，無需建立資料。")
        
        c_mode = st.radio("選擇日期輸入方式", ["民國", "西元"], horizontal=True)
        dob = None
        
        if c_mode == "民國":
            dob = roc_date_input("請選擇幼兒生日", date(2023, 1, 1), key_suffix="quick_check")
        else:
            dob = st.date_input("請選擇幼兒生日 (西元)", value=date(2023, 1, 1))

        if dob:
            st.divider()
            roadmap = calculate_admission_roadmap(dob)
            
            st.subheader(f"👶 這位小朋友目前是：")
            current_status = roadmap[0] if roadmap else "年齡不符"
            grade_display = current_status.split(" - ")[-1] if " - " in current_status else current_status
            year_display = current_status.split(" - ")[0] if " - " in current_status else "目前"
            
            st.markdown(f"<div class='big-grade'>{grade_display}</div>", unsafe_allow_html=True)
            st.caption(f"學年度：{year_display} | 生日：{dob}")
            
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

    with tab_q2:
        st.subheader("📊 各年份出生兒童入學對照表")
        st.caption("依據 9/2 分界計算，僅供參考。")
        
        # 動態產生對照表 (未來 4 年)
        cur_roc_year = date.today().year - 1911
        check_years = [cur_roc_year, cur_roc_year+1, cur_roc_year+2, cur_roc_year+3]
        
        # 產生最近 8 年的出生年份
        birth_rows = []
        base_y = date.today().year
        for dy in range(0, 8):
            b_year_ad = base_y - dy
            b_year_roc = b_year_ad - 1911
            # 假設生日為 9/1 (學年間的大數)
            sample_date = date(b_year_ad, 9, 1)
            
            row_data = {
                "西元出生": b_year_ad,
                "民國出生": b_year_roc,
            }
            for y in check_years:
                row_data[f"{y}學年"] = get_grade_for_year(sample_date, y)
            birth_rows.append(row_data)
        
        df_ref = pd.DataFrame(birth_rows)
        # 讓學年欄位排在最後
        cols = ["西元出生", "民國出生"] + [f"{y}學年" for y in check_years]
        st.dataframe(df_ref[cols], use_container_width=True, hide_index=True)

# ------------------------------------------
# 頁面 4: 未來入學預覽 (排除確定不收)
# ------------------------------------------
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
                # 排除確定不收
                if "確定不收" in str(row['報名狀態']):
                    continue

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

                if grade in roster:
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
                            "報名狀態": st.column_config.SelectboxColumn(options=NEW_STATUS_OPTIONS, width="medium"),
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
        
# ------------------------------------------
# 頁面 5: 師資人力預估 (混班計算 + 現有比對)
# ------------------------------------------
elif menu == "👩‍🏫 師資人力預估":
    st.header("📊 師資人力預估")
    
    # 1. 設定預估學年
    c_y1, c_y2 = st.columns([1, 3])
    cal_y = c_y1.number_input("📅 預估學年", value=date.today().year - 1911 + 1)
    c_y2.info(f"正在計算 **{cal_y} 學年度** 的人力需求（系統自動依生日推算屆時年段）")

    # 2. 參數設定 (師生比 + 現有人力)
    with st.expander("⚙️ 參數設定：師生比與現有師資", expanded=True):
        st.caption("請輸入目前的「合格教保服務人員」數量，系統將自動計算缺額。")
        
        # 師生比法規參考
        default_ratio_k = 12 if cal_y >= 115 else 15
        
        col_set1, col_set2, col_set3 = st.columns(3)
        
        # --- 0-2歲 (托嬰) ---
        with col_set1:
            st.markdown("#### 🍼 0-2 歲 (托嬰)")
            r_d = st.number_input("師生比 1:", value=5, key="r_d")
            teacher_d = st.number_input("現有老師數", value=2, min_value=0, key="t_d")
            
        # --- 2-3歲 (幼幼) ---
        with col_set2:
            st.markdown("#### 🐥 2-3 歲 (幼幼)")
            r_t = st.number_input("師生比 1:", value=8, key="r_t")
            teacher_t = st.number_input("現有老師數", value=2, min_value=0, key="t_t")
            
        # --- 3-6歲 (混齡) ---
        with col_set3:
            st.markdown("#### 🐘 3-6 歲 (混齡)")
            st.caption("小/中/大班可混齡編班")
            r_k = st.number_input("師生比 1:", value=default_ratio_k, key="r_k")
            teacher_k = st.number_input("現有老師數", value=6, min_value=0, key="t_k")

    st.divider()

    # 3. 資料計算
    cats = {
        "0-2歲": {"conf": 0, "pend": 0, "status": "獨立班"},
        "2-3歲": {"conf": 0, "pend": 0, "status": "獨立班"},
        "3-6歲": {"conf": 0, "pend": 0, "status": "混齡編班"}
    }

    # 遍歷資料庫進行歸類
    for _, r in df.iterrows():
        try:
            # 排除確定不收
            if "確定不收" in str(r['報名狀態']): continue

            gr = None
            if f"{cal_y} 學年" in str(r['預計入學資訊']):
                gr = str(r['預計入學資訊']).split("-")[1].strip()
            if not gr:
                dob = date(int(str(r['幼兒生日']).split('/')[0])+1911, int(str(r['幼兒生日']).split('/')[1]), int(str(r['幼兒生日']).split('/')[2]))
                gr = get_grade_for_year(dob, cal_y)

            is_conf = "確認入學" in str(r['報名狀態'])
            count_key = "conf" if is_conf else "pend"

            if gr == "托嬰中心":
                cats["0-2歲"][count_key] += 1
            elif gr == "幼幼班":
                cats["2-3歲"][count_key] += 1
            elif gr in ["小班", "中班", "大班"]:
                cats["3-6歲"][count_key] += 1
                
        except: pass

    # 4. 顯示結果卡片
    st.subheader("📊 人力需求預估分析")
    
    def render_staff_card(title, group_key, ratio, current_teachers):
        data = cats[group_key]
        num_conf = data["conf"]
        num_pend = data["pend"]
        num_total = num_conf + num_pend
        
        # 核心計算：無條件進位
        req_conf = math.ceil(num_conf / ratio)       
        req_total = math.ceil(num_total / ratio)     
        
        # 缺額計算
        gap_conf = current_teachers - req_conf
        gap_total = current_teachers - req_total
        
        with st.container(border=True):
            st.markdown(f"### {title}")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("✅ 確認學生", f"{num_conf} 人")
            c2.metric("⏳ 含潛在學生", f"{num_total} 人")
            c3.metric("📏 計算師生比", f"1 : {ratio}")
            
            st.markdown("---")
            
            # 情境 A
            st.markdown("**情境 A：僅考慮「確認入學」**")
            k1, k2 = st.columns([2, 3])
            k1.write(f"需要老師： **{req_conf}** 位")
            if gap_conf < 0:
                k2.error(f"⚠️ 還缺 {abs(gap_conf)} 位")
            else:
                k2.success(f"👌 人力充裕 (餘 {gap_conf} 位)")
            
            # 情境 B
            st.markdown("**情境 B：若「潛在學生」全收**")
            k3, k4 = st.columns([2, 3])
            k3.write(f"需要老師： **{req_total}** 位")
            if gap_total < 0:
                k4.error(f"🚨 還缺 {abs(gap_total)} 位")
            else:
                k4.success(f"👌 人力充裕 (餘 {gap_total} 位)")

    col_g1, col_g2, col_g3 = st.columns(3)
    
    with col_g1:
        render_staff_card("🍼 0-2 歲 (托嬰)", "0-2歲", r_d, teacher_d)
    
    with col_g2:
        render_staff_card("🐥 2-3 歲 (幼幼)", "2-3歲", r_t, teacher_t)
        
    with col_g3:
        render_staff_card("🐘 3-6 歲 (混齡)", "3-6歲", r_k, teacher_k)
        
    st.info("💡 **計算說明**：此系統採「混齡計算」模擬 3-6 歲人力需求。若您實際上採「分班教學」，且各班人數未滿額，實際所需老師可能會比上述計算更多。")
