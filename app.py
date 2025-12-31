import streamlit as st
import pandas as pd
from datetime import date, datetime
import math

# ==========================================
# 0. 系統環境設定與初始化
# ==========================================
st.set_page_config(page_title="幼兒園新生管理系統", layout="wide", page_icon="🏫")

# 外部庫匯入處理
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# CSS 樣式美化
st.markdown("""
<style>
    .stApp { font-family: "Microsoft JhengHei", "PingFang TC", sans-serif; }
    .main-title { font-size: 2.2em; font-weight: bold; color: #1E3A8A; margin-bottom: 20px; }
    .status-online { color: #10B981; font-weight: bold; }
    .status-offline { color: #EF4444; font-weight: bold; }
    .metric-card { background: #F3F4F6; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #D1D5DB; }
</style>
""", unsafe_allow_html=True)

# 系統全域變數
SHEET_NAME = "kindergarten_db"  # 請確保 Google Drive 上的檔案名稱與此一致
LOCAL_CSV = "kindergarten_local_db.csv"
STATUS_OPTIONS = ["預約參觀", "排隊等待", "確認入學", "確定不收"]
IMPORTANCE_OPTIONS = ["優", "中", "差"]
# 系統核心欄位 (需與 Google Sheet 標題列一致)
FINAL_COLS = ["報名狀態", "聯繫狀態", "登記日期", "幼兒姓名", "家長稱呼", "電話",
              "幼兒生日", "預計入學資訊", "推薦人", "備註", "重要性"]

# 初始化工作階段狀態
if "auth" not in st.session_state: st.session_state.auth = False
if "temp_list" not in st.session_state: st.session_state.temp_list = []

# ==========================================
# 1. 核心邏輯函式
# ==========================================

def _safe_str(val) -> str:
    if pd.isna(val) or val is None: return ""
    return str(val).strip()

def to_roc_date(d: date) -> str:
    return f"{d.year-1911}/{d.month:02d}/{d.day:02d}"

def get_grade_by_age(birth_date: date, target_roc_year: int) -> str:
    if not birth_date: return "未知"
    by_roc = birth_date.year - 1911
    is_late = (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2)
    age = target_roc_year - by_roc - (1 if is_late else 0)
    if age < 2: return "托嬰中心"
    mapping = {2: "幼幼班", 3: "小班", 4: "中班", 5: "大班"}
    return mapping.get(age, "畢業/超齡")

# ==========================================
# 2. Google Sheets 連線核心
# ==========================================

@st.cache_resource
def get_gspread_client():
    if not HAS_GSPREAD: return None
    try:
        # 從 st.secrets 讀取憑證
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
    except Exception as e:
        st.sidebar.error(f"憑證解析錯誤: {e}")
    return None

def load_data():
    """優先嘗試從 Google Sheets 讀取現有資料"""
    client = get_gspread_client()
    df = pd.DataFrame()
    
    if client:
        try:
            # 嘗試開啟檔案
            sh = client.open(SHEET_NAME).sheet1
            data = sh.get_all_values()
            if len(data) > 0:
                # 讀取第一列作為標題
                df = pd.DataFrame(data[1:], columns=data[0])
                st.session_state["sync_status"] = "已連線至 Google Sheets"
            else:
                st.session_state["sync_status"] = "連線成功但檔案為空"
        except Exception as e:
            st.session_state["sync_status"] = f"無法開啟雲端檔案: {e}"
    else:
        st.session_state["sync_status"] = "未設定雲端憑證 (使用本機模式)"

    # 如果雲端失敗，嘗試本機
    if df.empty:
        try:
            df = pd.read_csv(LOCAL_CSV, dtype=str)
        except:
            df = pd.DataFrame(columns=FINAL_COLS)
            
    # 清洗資料，確保欄位正確
    df = df.fillna("").astype(str)
    for c in FINAL_COLS:
        if c not in df.columns: df[c] = ""
    return df[FINAL_COLS]

def save_data(df: pd.DataFrame):
    """將資料寫回 Google Sheets 與本機備份"""
    # 1. 儲存至本機
    df.to_csv(LOCAL_CSV, index=False, encoding="utf-8-sig")
    
    # 2. 嘗試更新雲端
    client = get_gspread_client()
    if client:
        try:
            sh = client.open(SHEET_NAME).sheet1
            # 準備寫入內容 (包含標題列)
            content = [FINAL_COLS] + df.values.tolist()
            sh.clear()
            sh.update("A1", content)
            return True
        except Exception as e:
            st.error(f"雲端寫入失敗: {e}")
    return False

# ==========================================
# 3. 介面與功能頁面
# ==========================================

def login_ui():
    st.markdown('<p class="main-title">🔐 幼兒園管理系統登入</p>', unsafe_allow_html=True)
    pwd = st.text_input("輸入管理密碼", type="password")
    if st.button("登入", type="primary"):
        if pwd == st.secrets.get("password", "1234"):
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("密碼錯誤")

def page_add():
    st.markdown('<p class="main-title">👶 新生報名登記</p>', unsafe_allow_html=True)
    with st.form("entry_form"):
        c1, c2 = st.columns(2)
        with c1:
            p_name = st.text_input("家長姓名")
            phone = st.text_input("聯絡電話")
            p_title = st.selectbox("稱呼", ["爸爸", "媽媽", "家長"])
        with c2:
            c_name = st.text_input("幼兒姓名")
            # 簡單日期輸入
            dob_date = st.date_input("幼兒生日", value=date(2022,1,1))
            note = st.text_area("備註")
            
        if st.form_submit_button("➕ 加入暫存"):
            if p_name and c_name and phone:
                dob_roc = to_roc_date(dob_date)
                # 自動推算入學年份 (以當前為例)
                cur_y = date.today().year - 1911
                grade = get_grade_by_age(dob_date, cur_y + 1)
                
                entry = {
                    "報名狀態": "預約參觀", "聯繫狀態": "未聯繫", "登記日期": to_roc_date(date.today()),
                    "幼兒姓名": c_name, "家長稱呼": f"{p_name}{p_title}", "電話": phone,
                    "幼兒生日": dob_roc, "預計入學資訊": f"{cur_y+1} 學年 - {grade}",
                    "推薦人": "", "備註": note, "重要性": "中"
                }
                st.session_state.temp_list.append(entry)
                st.success(f"已暫存 {c_name} 的資料")
            else:
                st.error("請填寫姓名與電話")

    if st.session_state.temp_list:
        st.divider()
        st.subheader("待提交列表")
        temp_df = pd.DataFrame(st.session_state.temp_list)
        st.dataframe(temp_df, use_container_width=True)
        if st.button("🚀 確認送出並更新至 Google Drive", type="primary"):
            full_df = pd.concat([load_data(), temp_df], ignore_index=True)
            if save_data(full_df):
                st.session_state.temp_list = []
                st.success("成功同步至 Google Drive！")
                st.rerun()

def page_manage():
    st.markdown('<p class="main-title">📂 資料管理中心</p>', unsafe_allow_html=True)
    df = load_data()
    
    st.write(f"📊 目前共有 {len(df)} 筆資料")
    
    # 搜尋功能
    search = st.text_input("🔍 關鍵字搜尋 (姓名、電話、備註)")
    if search:
        df = df[df.apply(lambda row: search in row.values.astype(str).join(" "), axis=1)]

    # 編輯功能
    edited_df = st.data_editor(
        df,
        column_config={
            "報名狀態": st.column_config.SelectboxColumn(options=STATUS_OPTIONS),
            "聯繫狀態": st.column_config.SelectboxColumn(options=["未聯繫", "已聯繫"]),
            "重要性": st.column_config.SelectboxColumn(options=IMPORTANCE_OPTIONS),
        },
        use_container_width=True,
        num_rows="dynamic"
    )
    
    if st.button("💾 儲存所有變更至雲端"):
        if save_data(edited_df):
            st.success("雲端資料已更新！")
            st.rerun()

# ==========================================
# 4. 主程式執行
# ==========================================

if not st.session_state.auth:
    login_ui()
else:
    # 側邊欄狀態顯示
    with st.sidebar:
        st.title("系統狀態")
        status = st.session_state.get("sync_status", "檢查中...")
        st.markdown(f"**連線狀態：**\n{status}")
        
        st.divider()
        menu = st.radio("功能選單", ["👶 新增報名", "📂 資料管理中心", "👩‍🏫 招生試算"])
        
        if st.button("🚪 登出"):
            st.session_state.auth = False
            st.rerun()

    if menu == "👶 新增報名":
        page_add()
    elif menu == "📂 資料管理中心":
        page_manage()
    elif menu == "👩‍🏫 招生試算":
        # 簡易佔位
        st.write("師資試算功能開發中...")
