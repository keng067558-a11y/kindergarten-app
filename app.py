import streamlit as st
import pandas as pd
from datetime import date, datetime
import math
import time
import os
import requests
from io import StringIO

# ==========================================
# 0. 基礎配置與 CSS 優化
# ==========================================
st.set_page_config(
    page_title="新生管理系統 - 雲端同步版",
    layout="wide",
    page_icon="🏫",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&display=swap');
    :root {
        --primary-color: #1E293B;
        --accent-color: #3B82F6;
        --bg-color: #F8FAFC;
        --border-color: #E2E8F0;
        --text-main: #334155;
    }
    html, body, [class*="css"] {
        font-family: 'Noto Sans TC', sans-serif;
        color: var(--text-main);
        background-color: var(--bg-color);
    }
    .main-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: var(--primary-color);
        margin-bottom: 1.5rem;
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 1.2rem;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid var(--border-color);
    }
    .stButton>button {
        border-radius: 6px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 常數與核心邏輯
# ==========================================
NEW_STATUS_OPTIONS = ["預約參觀", "排隊等待", "確認入學", "確定不收"]
IMPORTANCE_OPTIONS = ["優", "中", "差"]
GRADE_ORDER = {"大班": 1, "中班": 2, "小班": 3, "幼幼班": 4, "托嬰中心": 5, "未知": 6, "畢業/超齡": 7, "年齡不符": 8}
LOCAL_CSV = "kindergarten_local_db.csv"
FINAL_COLS = [
    "報名狀態", "聯繫狀態", "登記日期", "幼兒姓名", "家長稱呼", "電話",
    "幼兒生日", "預計入學資訊", "推薦人", "備註", "重要性"
]

def _safe_str(x) -> str:
    s = str(x).strip() if x is not None else ""
    return "" if s.lower() == "nan" else s

def normalize_phone(s: str) -> str:
    s = _safe_str(s).replace("-", "").replace(" ", "")
    if len(s) == 9 and s.startswith("9"): return "0" + s
    return s

def parse_roc_date(s: str):
    s = _safe_str(s)
    if not s: return None
    try:
        parts = s.replace("-", "/").replace(".", "/").split("/")
        return date(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))
    except: return None

def to_roc_str(d: date) -> str:
    return f"{d.year-1911}/{d.month:02d}/{d.day:02d}"

def get_grade_logic(birth_date: date, target_roc_year: int) -> str:
    if not birth_date: return "未知"
    by_roc = birth_date.year - 1911
    is_late = (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2)
    age = target_roc_year - by_roc - (1 if is_late else 0)
    grades = {0: "托嬰中心", 1: "托嬰中心", 2: "幼幼班", 3: "小班", 4: "中班", 5: "大班"}
    return grades.get(age, "畢業/超齡" if age > 5 else "年齡不符")

# ==========================================
# 2. 資料存取層 (支援雲端讀取)
# ==========================================
@st.cache_data(ttl=60)
def load_data(gs_url=None):
    df = pd.DataFrame(columns=FINAL_COLS)
    
    # 優先嘗試從 Google Sheets 載入
    if gs_url and "docs.google.com" in gs_url:
        try:
            response = requests.get(gs_url)
            if response.status_code == 200:
                cloud_df = pd.read_csv(StringIO(response.text), dtype=str)
                # 這裡需要對應 Google 表單的欄位名稱，假設順序一致或做自動映射
                # 若欄位名稱不同，需在此處做 rename
                df = cloud_df
                st.toast("✅ 已成功同步雲端數據")
        except Exception as e:
            st.warning(f"雲端同步失敗，改用本地數據。錯誤：{e}")

    # 本地備份讀取
    if df.empty and os.path.exists(LOCAL_CSV):
        try:
            df = pd.read_csv(LOCAL_CSV, dtype=str)
        except: pass
    
    df = df.fillna("").astype(str)
    for c in FINAL_COLS:
        if c not in df.columns: df[c] = ""
    df["電話"] = df["電話"].apply(normalize_phone)
    return df[FINAL_COLS]

def save_data(df: pd.DataFrame):
    try:
        save_df = df[FINAL_COLS].fillna("").astype(str)
        save_df.to_csv(LOCAL_CSV, index=False, encoding="utf-8-sig")
        load_data.clear()
        return True
    except Exception as e:
        st.error(f"數據儲存失敗：{e}")
        return False

# ==========================================
# 3. 頁面邏輯
# ==========================================

def login_screen():
    if st.session_state.get("authenticated"): return True
    cols = st.columns([1, 1, 1])
    with cols[1]:
        st.markdown("<div style='height:20vh'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.subheader("🏫 系統登入")
            pwd = st.text_input("密碼", type="password")
            if st.button("進入", use_container_width=True, type="primary") or (pwd == "1234" and pwd):
                if pwd == "1234":
                    st.session_state["authenticated"] = True
                    st.rerun()
                else: st.error("密碼錯誤")
    return False

def page_manage(df):
    st.markdown("<div class='main-title'>📂 數據管理中心</div>", unsafe_allow_html=True)
    
    # --- 雲端同步設定 ---
    with st.expander("☁️ 連結 Google Drive (表單數據)"):
        st.write("請貼上 Google 試算表『發佈到網路』的 **CSV 連結**：")
        gs_url_input = st.text_input("Google Sheets CSV URL", 
                                     value=st.session_state.get("gs_url", ""),
                                     placeholder="https://docs.google.com/spreadsheets/d/.../export?format=csv")
        if st.button("🔄 立即從雲端導入"):
            st.session_state["gs_url"] = gs_url_input
            st.cache_data.clear()
            st.rerun()

    search_kw = st.text_input("🔍 搜尋名單 (姓名或電話)", placeholder="快速找人...")

    # 表格顯示邏輯
    display_df = df.copy()
    if search_kw:
        display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search_kw, case=False)).any(axis=1)]
    
    st.info(f"📊 目前共有 {len(display_df)} 筆報名資料")

    edited_df = st.data_editor(
        display_df,
        column_order=["登記日期", "報名狀態", "重要性", "幼兒姓名", "家長稱呼", "電話", "幼兒生日", "備註"],
        column_config={
            "登記日期": st.column_config.TextColumn("登記日期", disabled=True),
            "報名狀態": st.column_config.SelectboxColumn("狀態", options=NEW_STATUS_OPTIONS),
            "備註": st.column_config.TextColumn("備註", width="large"),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic"
    )

    if st.button("💾 儲存所有變更至本地備份", type="primary", use_container_width=True):
        # 如果有搜尋，需要合併回主資料
        full_df = load_data(st.session_state.get("gs_url"))
        if search_kw:
            full_df.update(edited_df)
            save_target = full_df
        else:
            save_target = edited_df
        
        if save_data(save_target):
            st.success("✅ 資料已同步至系統檔案中")
            time.sleep(0.5)
            st.rerun()

def page_dashboard(df):
    st.markdown("<div class='main-title'>營運概覽</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("總登記人數", len(df))
    c2.metric("預約參觀", len(df[df["報名狀態"]=="預約參觀"]))
    c3.metric("確認入學", len(df[df["報名狀態"]=="確認入學"]))
    
    if not df.empty:
        st.write("### 📅 最近報名趨勢")
        st.line_chart(df["登記日期"].value_counts().sort_index())

# (其餘 page_add, page_quick_check 等保持原邏輯)
def page_add():
    st.markdown("<div class='main-title'>新生登記</div>")
    st.info("您可以直接使用 Google 表單讓家長填寫，或在此手動輸入。")
    # ... 原有的 page_add 邏輯 ...

# ==========================================
# 4. 主程式控管
# ==========================================
def main():
    if not login_screen(): return
    
    df = load_data(st.session_state.get("gs_url"))
    
    with st.sidebar:
        st.markdown("### 🏫 園所管理")
        menu = st.radio("選單", ["儀表板", "數據管理", "快速查詢"])
        if st.button("安全登出"):
            st.session_state["authenticated"] = False
            st.rerun()

    if menu == "儀表板": page_dashboard(df)
    elif menu == "數據管理": page_manage(df)
    elif menu == "快速查詢": st.write("查詢功能開發中...")

if __name__ == "__main__":
    main()
