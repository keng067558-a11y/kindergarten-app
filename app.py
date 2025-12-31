import streamlit as st
import pandas as pd
from datetime import date, datetime
import math

# ==========================================
# 0. 基礎設定與系統核心
# ==========================================
st.set_page_config(page_title="新生與經費管理系統", layout="wide", page_icon="🏫")

# 嘗試匯入必要的外部庫
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

# 自定義 CSS 樣式
st.markdown("""
<style>
    .stApp { font-family: "Microsoft JhengHei", "PingFang TC", sans-serif; }
    .streamlit-expanderHeader { background-color: #f8f9fa; border: 1px solid #eee; font-weight: bold; color: #333; }
    .big-grade { font-size: 2.5em; font-weight: bold; color: #ff4b4b; margin: 10px 0; }
    .metric-box {
        background-color: #f0f2f6;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #ddd;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# 常數設定
NEW_STATUS_OPTIONS = ["預約參觀", "排隊等待", "確認入學", "確定不收"]
SHEET_NAME = "kindergarten_db"
LOCAL_CSV = "kindergarten_local_db.csv"
FINAL_COLS = ["報名狀態", "聯繫狀態", "登記日期", "幼兒姓名", "家長稱呼", "電話",
              "幼兒生日", "預計入學資訊", "推薦人", "備註", "重要性"]

# 初始化 Session State
state_defaults = {
    "calc_memory": {},
    "temp_children": [],
    "msg_error": None,
    "msg_ok": None,
    "password_correct": False
}
for key, val in state_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ==========================================
# 1. 輔助函式 (工具類)
# ==========================================
def _safe_str(x) -> str:
    if x is None or pd.isna(x): return ""
    return str(x).strip()

def normalize_phone(s: str) -> str:
    s = _safe_str(s)
    if len(s) == 9 and s.startswith("9"):
        return "0" + s
    return s

def parse_roc_date_str(s: str):
    s = _safe_str(s)
    if not s: return None
    try:
        # 支援多種分隔符號
        parts = s.replace("-", "/").replace(".", "/").split("/")
        if len(parts) != 3: return None
        y = int(parts[0]) + 1911
        m = int(parts[1])
        d = int(parts[2])
        return date(y, m, d)
    except Exception:
        return None

def to_roc_str(d: date) -> str:
    if not d: return ""
    return f"{d.year-1911}/{d.month:02d}/{d.day:02d}"

# ==========================================
# 2. 安全與權限
# ==========================================
def check_password():
    if st.session_state.password_correct:
        return True

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🔒 系統登入")
        with st.form("login_form"):
            pwd = st.text_input("請輸入通關密碼", type="password")
            if st.form_submit_button("登入", type="primary", use_container_width=True):
                if pwd == "1234":
                    st.session_state.password_correct = True
                    st.rerun()
                else:
                    st.error("密碼錯誤")
    return False

if not check_password():
    st.stop()

# ==========================================
# 3. 資料存取邏輯 (Google Sheets & Local)
# ==========================================
@st.cache_resource
def get_gsheet_client():
    if not HAS_GSPREAD or "gcp_service_account" not in st.secrets:
        return None
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        return gspread.authorize(creds)
    except Exception:
        return None

def get_sheet():
    client = get_gsheet_client()
    if not client: return None
    try:
        return client.open(SHEET_NAME).sheet1
    except Exception:
        return None

@st.cache_data(ttl=300)
def load_registered_data():
    df = pd.DataFrame()
    sheet = get_sheet()
    
    if sheet:
        try:
            data = sheet.get_all_values()
            if len(data) > 0:
                df = pd.DataFrame(data[1:], columns=data[0])
        except Exception:
            pass

    if df.empty:
        try:
            df = pd.read_csv(LOCAL_CSV, dtype=str)
        except Exception:
            df = pd.DataFrame(columns=FINAL_COLS)

    df = df.fillna("").astype(str)
    for c in FINAL_COLS:
        if c not in df.columns: df[c] = ""
    
    df["電話"] = df["電話"].apply(normalize_phone)
    df = df[FINAL_COLS]
    return df

def sync_data(new_df: pd.DataFrame):
    try:
        save_df = new_df[FINAL_COLS].copy().fillna("").astype(str)
        # 本機備份
        save_df.to_csv(LOCAL_CSV, index=False, encoding="utf-8-sig")
        # 雲端同步
        sheet = get_sheet()
        if sheet:
            values = [FINAL_COLS] + save_df.values.tolist()
            sheet.clear()
            sheet.update("A1", values)
        load_registered_data.clear()
        return True
    except Exception as e:
        st.error(f"儲存失敗: {e}")
        return False

# ==========================================
# 4. 業務邏輯與 UI 元件
# ==========================================
def roc_date_input(label, default_date=None, key_suffix=""):
    st.write(f"**{label}**")
    if default_date is None: default_date = date.today()
    c1, c2, c3 = st.columns(3)
    
    y_list = list(range(90, 131))
    cur_y = default_date.year - 1911
    y = c1.selectbox("年 (民國)", y_list, index=y_list.index(cur_y) if cur_y in y_list else 22, key=f"y_{key_suffix}")
    m = c2.selectbox("月", list(range(1, 13)), index=default_date.month - 1, key=f"m_{key_suffix}")
    d = c3.selectbox("日", list(range(1, 32)), index=min(default_date.day - 1, 30), key=f"d_{key_suffix}")
    
    try:
        return date(y + 1911, m, d)
    except ValueError:
        return date(y + 1911, m, 28) # 簡易處理閏月月底

def get_grade_for_year(birth_date: date, target_roc_year: int) -> str:
    if not birth_date: return "未知"
    by_roc = birth_date.year - 1911
    # 9/2 為學年度切分點
    offset = 1 if (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2) else 0
    age = target_roc_year - by_roc - offset
    
    mapping = {2: "幼幼班", 3: "小班", 4: "中班", 5: "大班"}
    if age < 2: return "托嬰中心"
    return mapping.get(age, "畢業/超齡")

def calculate_admission_roadmap(dob: date):
    cur_roc = date.today().year - 1911
    if date.today().month < 8: cur_roc -= 1
    
    roadmap = []
    for i in range(6):
        target = cur_roc + i
        grade = get_grade_for_year(dob, target)
        if "畢業" not in grade:
            roadmap.append(f"{target} 學年 - {grade}")
    return roadmap if roadmap else ["年齡不符"]

# ==========================================
# 5. 回呼函式 (Callbacks)
# ==========================================
def add_child_cb():
    # 這裡從關鍵字取得輸入
    dob = roc_date_input_silent("add")
    name = _safe_str(st.session_state.get("input_c_name"))
    if not name:
        st.session_state.msg_error = "⚠️ 請填寫幼兒姓名"
        return
    
    plans = calculate_admission_roadmap(dob)
    st.session_state.temp_children.append({
        "幼兒姓名": name,
        "幼兒生日": to_roc_str(dob),
        "報名狀態": "預約參觀",
        "預計入學資訊": plans[0] if plans else "待確認",
        "備註": _safe_str(st.session_state.get("input_note")),
        "重要性": "中"
    })
    st.session_state.input_c_name = ""
    st.session_state.input_note = ""

def roc_date_input_silent(suffix):
    y = st.session_state.get(f"y_{suffix}", 112)
    m = st.session_state.get(f"m_{suffix}", 1)
    d = st.session_state.get(f"d_{suffix}", 1)
    return date(y + 1911, m, d)

# ==========================================
# 6. 主程式頁面渲染
# ==========================================
st.title("🏫 幼兒園新生管理系統")

# 訊息顯示
if st.session_state.msg_error:
    st.error(st.session_state.msg_error)
    st.session_state.msg_error = None
if st.session_state.msg_ok:
    st.success(st.session_state.msg_ok)
    st.session_state.msg_ok = None

df = load_registered_data()

menu = st.sidebar.radio("功能導航", ["👶 新增報名", "📂 資料管理中心", "🎓 學年查詢", "📅 未來入學預覽", "👩‍🏫 招生試算"])

# --- 頁面：新增報名 ---
if menu == "👶 新增報名":
    st.header("📝 新生報名登記")
    c1, c2 = st.columns(2)
    with c1:
        st.info("👤 家長資訊")
        st.text_input("家長姓氏", key="input_p_name")
        st.selectbox("稱謂", ["爸爸", "媽媽", "先生", "小姐"], key="input_p_title")
        st.text_input("電話", key="input_phone")
        st.text_input("推薦人", key="input_referrer")
    with c2:
        st.success("👶 幼兒資訊")
        st.text_input("幼兒姓名", key="input_c_name")
        roc_date_input("出生日 (民國)", date(2022, 1, 1), key_suffix="add")
        st.text_area("備註", key="input_note", height=100)
        st.button("⬇️ 加入暫存列表", type="primary", on_click=add_child_cb, use_container_width=True)

    if st.session_state.temp_children:
        st.divider()
        st.subheader(f"🛒 待送出名單 ({len(st.session_state.temp_children)})")
        temp_df = pd.DataFrame(st.session_state.temp_children)
        
        edited_df = st.data_editor(
            temp_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "報名狀態": st.column_config.SelectboxColumn(options=NEW_STATUS_OPTIONS),
                "重要性": st.column_config.SelectboxColumn(options=["優", "中", "差"]),
            },
            key="editor_temp"
        )
        
        if st.button("🚀 確認提交至資料庫", type="primary"):
            p_name = _safe_str(st.session_state.get("input_p_name"))
            phone = normalize_phone(st.session_state.get("input_phone"))
            if not p_name or not phone:
                st.error("❌ 家長姓名與電話為必填欄位")
            else:
                new_rows = edited_df.copy()
                new_rows["家長稱呼"] = f"{p_name} {st.session_state.input_p_title}"
                new_rows["電話"] = phone
                new_rows["推薦人"] = st.session_state.input_referrer
                new_rows["登記日期"] = to_roc_str(date.today())
                new_rows["聯繫狀態"] = "未聯繫"
                
                final_df = pd.concat([df, new_rows], ignore_index=True)
                if sync_data(final_df):
                    st.session_state.msg_ok = "✅ 資料已成功儲存"
                    st.session_state.temp_children = []
                    st.rerun()

# --- 頁面：資料管理中心 ---
elif menu == "📂 資料管理中心":
    st.header("📂 資料管理中心")
    kw = st_keyup("🔍 搜尋姓名或電話", placeholder="輸入關鍵字...")
    
    if not df.empty:
        filtered = df.copy()
        if kw:
            mask = filtered.apply(lambda x: x.str.contains(kw, case=False)).any(axis=1)
            filtered = filtered[mask]
        
        t1, t2 = st.tabs(["📋 表格編輯模式", "🗂️ 狀態分組模式"])
        
        with t1:
            edited_master = st.data_editor(
                filtered,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "報名狀態": st.column_config.SelectboxColumn(options=NEW_STATUS_OPTIONS),
                    "聯繫狀態": st.column_config.SelectboxColumn(options=["未聯繫", "已聯繫"]),
                    "重要性": st.column_config.SelectboxColumn(options=["優", "中", "差"]),
                },
                key="master_editor"
            )
            if st.button("💾 儲存所有表格變更"):
                # 合併回原始 DF (根據電話與姓名匹配，簡易處理)
                if sync_data(edited_master):
                    st.success("更新成功！")
        
        with t2:
            for status in NEW_STATUS_OPTIONS:
                sub = filtered[filtered["報名狀態"] == status]
                if not sub.empty:
                    with st.expander(f"{status} ({len(sub)} 筆)"):
                        st.table(sub[["幼兒姓名", "家長稱呼", "電話", "聯繫狀態", "重要性"]])

# --- 頁面：招生試算 ---
elif menu == "👩‍🏫 招生試算":
    st.header("👩‍🏫 師資與招生缺額計算")
    cal_y = st.number_input("目標學年度", value=date.today().year - 1911 + 1)
    
    # 115學年度起 3-6 歲師生比調整為 1:12
    ratio_36 = 12 if cal_y >= 115 else 15
    st.info(f"💡 {cal_y} 學年度適用師生比： 3-6歲 **1:{ratio_36}** | 2-3歲 **1:8**")
    
    c1, c2, c3 = st.columns(3)
    target_36 = c1.number_input("3-6歲 核定總人數", value=90)
    target_23 = c2.number_input("2-3歲 核定總人數", value=16)
    
    # 從資料庫抓取確認入學的人數
    conf_df = df[df["報名狀態"] == "確認入學"]
    # 簡易過濾該學年的學生
    current_conf = conf_df[conf_df["預計入學資訊"].str.contains(f"{cal_y} 學年")]
    
    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"""<div class="metric-box">
            <h3>3-6 歲混齡</h3>
            <p>已確認：{len(current_conf[~current_conf['預計入學資訊'].str.contains('幼幼班')])} 人</p>
            <p>剩餘缺額：<span style="color:blue">{target_36 - len(current_conf[~current_conf['預計入學資訊'].str.contains('幼幼班')])}</span></p>
            <p>需聘師資：{math.ceil(target_36/ratio_36)} 位</p>
        </div>""", unsafe_allow_html=True)
        
    with col_b:
        st.markdown(f"""<div class="metric-box">
            <h3>2-3 歲幼幼</h3>
            <p>已確認：{len(current_conf[current_conf['預計入學資訊'].str.contains('幼幼班')])} 人</p>
            <p>剩餘缺額：<span style="color:blue">{target_23 - len(current_conf[current_conf['預計入學資訊'].str.contains('幼幼班')])}</span></p>
            <p>需聘師資：{math.ceil(target_23/8)} 位</p>
        </div>""", unsafe_allow_html=True)

# 底部導航或其他頁面...
elif menu == "🎓 學年查詢":
    st.header("🎓 學年段快速查詢")
    dob = roc_date_input("選擇幼兒生日", date(2023, 1, 1), "query")
    roadmap = calculate_admission_roadmap(dob)
    st.markdown(f"### 🎯 該生入學路徑：")
    for r in roadmap:
        st.write(f"✅ {r}")

elif menu == "📅 未來入學預覽":
    st.header("📅 未來各班級名單預覽")
    view_y = st.selectbox("選擇預覽學年", [113, 114, 115, 116])
    
    # 篩選邏輯
    view_df = df[df["預計入學資訊"].str.contains(f"{view_y} 學年")].copy()
    if view_df.empty:
        st.warning("該學年度尚無已預計入學之名單。")
    else:
        for grade in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]:
            g_sub = view_df[view_df["預計入學資訊"].str.contains(grade)]
            if not g_sub.empty:
                st.subheader(f"{grade} (共 {len(g_sub)} 人)")
                st.table(g_sub[["幼兒姓名", "報名狀態", "電話", "重要性"]])
