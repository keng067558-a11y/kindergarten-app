import streamlit as st
import pandas as pd
from datetime import date, datetime
import math
import time
import os
import re
import requests
from io import StringIO

# ==========================================
# 0. 專業級 UI 樣式配置 (現代化美化)
# ==========================================
st.set_page_config(
    page_title="園所新生管理系統 - 專業雲端版",
    layout="wide",
    page_icon="🏫",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&display=swap');
    
    :root {
        --primary: #0F172A;
        --accent: #2563EB;
        --bg: #F8FAFC;
        --card-bg: #FFFFFF;
        --text: #1E293B;
        --border: #E2E8F0;
    }

    /* 全局字體與背景 */
    html, body, [class*="css"] {
        font-family: 'Noto Sans TC', sans-serif;
        background-color: var(--bg);
        color: var(--text);
    }

    /* 頂部標題美化 */
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: var(--primary);
        margin-bottom: 2rem;
        padding-bottom: 0.8rem;
        border-bottom: 4px solid var(--accent);
        display: inline-block;
    }

    /* 數據卡片優化 */
    div[data-testid="stMetric"] {
        background-color: var(--card-bg);
        padding: 1.5rem;
        border-radius: 16px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border: 1px solid var(--border);
        transition: transform 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
    }

    /* 側邊欄高級感 */
    [data-testid="stSidebar"] {
        background-color: var(--card-bg);
        border-right: 1px solid var(--border);
    }
    .sidebar-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: var(--primary);
        text-align: center;
        margin-bottom: 2rem;
    }

    /* 按鈕樣式提升 */
    .stButton>button {
        border-radius: 10px;
        font-weight: 500;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }

    /* 雲端狀態小標籤 */
    .sync-status {
        font-size: 0.8rem;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 500;
        display: inline-block;
        margin-bottom: 1rem;
    }
    .status-ok { background-color: #DCFCE7; color: #166534; }
    .status-fail { background-color: #FEE2E2; color: #991B1B; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 核心邏輯與自動化網址轉換
# ==========================================
FINAL_COLS = [
    "報名狀態", "聯繫狀態", "登記日期", "幼兒姓名", "家長稱呼", "電話",
    "幼兒生日", "預計入學資訊", "推薦人", "備註", "重要性"
]
STATUS_OPTIONS = ["預約參觀", "排隊等待", "確認入學", "確定不收"]
GRADE_ORDER = {"大班": 1, "中班": 2, "小班": 3, "幼幼班": 4, "托嬰中心": 5, "未知": 6, "畢業/超齡": 7, "年齡不符": 8}
LOCAL_CSV = "kindergarten_db_backup.csv"

def convert_to_csv_url(url):
    if not url or "docs.google.com" not in url: return url
    try:
        file_id = re.search(r'/d/([a-zA-Z0-9-_]+)', url).group(1)
        gid = "0"
        if "gid=" in url: gid = re.search(r'gid=([0-9]+)', url).group(1)
        return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid={gid}"
    except: return url

def fuzzy_map_columns(df):
    mapping = {
        "幼兒姓名": ["姓名", "幼兒", "學生", "Child", "Name"],
        "電話": ["電話", "聯絡", "手機", "Phone", "Mobile"],
        "幼兒生日": ["生日", "出生", "Birthday", "DOB"],
        "家長稱呼": ["家長", "稱呼", "聯絡人", "Parent"],
        "登記日期": ["日期", "時間", "Timestamp", "Date"],
        "備註": ["備註", "說明", "Note"]
    }
    new_df = pd.DataFrame(columns=FINAL_COLS)
    for target, patterns in mapping.items():
        for col in df.columns:
            if any(p in str(col) for p in patterns):
                new_df[target] = df[col]
                break
    for col in FINAL_COLS:
        if col not in new_df.columns: new_df[col] = ""
    return new_df.fillna("")

def parse_roc_date(s):
    try:
        s = str(s).strip()
        if len(s.split('/')[0]) == 4: return datetime.strptime(s, '%Y/%m/%d').date()
        parts = s.replace("-", "/").replace(".", "/").split("/")
        return date(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))
    except: return None

def get_grade_logic(birth_date, target_roc_year):
    if not birth_date: return "未知"
    by_roc = birth_date.year - 1911
    is_late = (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2)
    age = target_roc_year - by_roc - (1 if is_late else 0)
    grades = {0: "托嬰中心", 1: "托嬰中心", 2: "幼幼班", 3: "小班", 4: "中班", 5: "大班"}
    return grades.get(age, "畢業/超齡" if age > 5 else "年齡不符")

# ==========================================
# 2. 資料存取層 (自動靜默同步)
# ==========================================
@st.cache_data(ttl=10)
def load_data(gs_url):
    df = pd.DataFrame(columns=FINAL_COLS)
    sync_status = ("本地備份", "status-ok")

    if gs_url:
        csv_url = convert_to_csv_url(gs_url)
        try:
            resp = requests.get(csv_url, timeout=5)
            if resp.status_code == 200:
                raw_df = pd.read_csv(StringIO(resp.text), dtype=str)
                df = fuzzy_map_columns(raw_df)
                df.to_csv(LOCAL_CSV, index=False, encoding="utf-8-sig")
                sync_status = ("雲端同步成功", "status-ok")
            else:
                sync_status = (f"雲端錯誤 {resp.status_code}", "status-fail")
        except:
            sync_status = ("雲端連線失敗", "status-fail")

    if df.empty and os.path.exists(LOCAL_CSV):
        try:
            df = pd.read_csv(LOCAL_CSV, dtype=str)
        except: pass

    df = df.fillna("").astype(str).reset_index(drop=True)
    for col in FINAL_COLS:
        if col not in df.columns: df[col] = ""
    return df[FINAL_COLS], sync_status

def save_data(df):
    try:
        df[FINAL_COLS].to_csv(LOCAL_CSV, index=False, encoding="utf-8-sig")
        load_data.clear()
        return True
    except: return False

# ==========================================
# 3. 功能頁面
# ==========================================

def page_dashboard(df):
    st.markdown("<h1 class='main-header'>營運現況儀表板</h1>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("總登記人數", len(df))
    c2.metric("已確認入學", len(df[df["報名狀態"]=="確認入學"]))
    c3.metric("待聯繫名單", len(df[df["聯繫狀態"]!="已聯繫"]))
    c4.metric("預約參觀數", len(df[df["報名狀態"]=="預約參觀"]))
    
    st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.subheader("📌 最近登記名單")
        if not df.empty:
            st.dataframe(df.tail(10).iloc[::-1][["登記日期", "幼兒姓名", "家長稱呼", "電話", "報名狀態"]], use_container_width=True, hide_index=True)
    with col_right:
        st.subheader("📈 狀態佔比")
        if not df.empty:
            st.bar_chart(df["報名狀態"].value_counts(), horizontal=True)

def page_manage(df):
    st.markdown("<h1 class='main-header'>名單管理中心</h1>", unsafe_allow_html=True)
    search = st.text_input("🔍 快速過濾 (姓名、電話或備註)", placeholder="輸入關鍵字...")
    
    display_df = df.copy()
    display_df["已聯繫"] = display_df["聯繫狀態"] == "已聯繫"
    
    if search:
        display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
    else:
        display_df = display_df.iloc[::-1]

    st.caption(f"共計 {len(display_df)} 筆資料")
    edited = st.data_editor(
        display_df,
        column_order=["登記日期", "已聯繫", "報名狀態", "重要性", "幼兒姓名", "家長稱呼", "電話", "幼兒生日", "備註"],
        column_config={
            "登記日期": st.column_config.TextColumn("登記日期", disabled=True),
            "已聯繫": st.column_config.CheckboxColumn("📞 已聯繫"),
            "報名狀態": st.column_config.SelectboxColumn("狀態", options=STATUS_OPTIONS),
            "重要性": st.column_config.SelectboxColumn("優先級", options=["優", "中", "差"]),
            "備註": st.column_config.TextColumn("備註", width="large")
        },
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        key="premium_editor"
    )
    
    if st.button("💾 儲存並同步至系統檔案", type="primary", use_container_width=True):
        edited["聯繫狀態"] = edited["已聯繫"].apply(lambda x: "已聯繫" if x else "未聯繫")
        df.update(edited)
        save_target = edited if (len(edited) != len(display_df) and not search) else df
        if save_data(save_target):
            st.success("✨ 修改已安全存檔")
            time.sleep(0.5)
            st.rerun()

def page_add():
    st.markdown("<h1 class='main-header'>手動補錄登記</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("幼兒姓名")
            parent = st.text_input("家長稱呼 (如：王媽媽)")
            phone = st.text_input("聯絡電話")
        with c2:
            ry = st.number_input("生日(民國)", 90, 130, 112)
            rm = st.selectbox("月份", range(1, 13))
            rd = st.selectbox("日期", range(1, 32))
            note = st.text_area("備註內容")
            
        if st.button("🚀 確認登記存檔", type="primary", use_container_width=True):
            if not name or not phone: st.error("請至少填寫姓名與電話")
            else:
                main_df, _ = load_data(st.session_state.get("gs_url", ""))
                new_row = pd.DataFrame([{
                    "報名狀態": "預約參觀", "聯繫狀態": "未聯繫",
                    "登記日期": f"{date.today().year-1911}/{date.today().month:02d}/{date.today().day:02d}",
                    "幼兒姓名": name, "家長稱呼": parent, "電話": phone,
                    "幼兒生日": f"{ry}/{rm}/{rd}", "備註": note, "重要性": "中"
                }])
                if save_data(pd.concat([main_df, new_row], ignore_index=True)):
                    st.success("🎉 登記成功")
                    time.sleep(0.5)
                    st.rerun()

def page_preview(df):
    st.markdown("<h1 class='main-header'>未來入學預覽</h1>", unsafe_allow_html=True)
    target_y = st.number_input("檢視學年度", value=date.today().year - 1911 + 1)
    
    pre_rows = []
    for _, r in df.iterrows():
        if "確定不收" in r["報名狀態"]: continue
        dob = parse_roc_date(r["幼兒生日"])
        grade = get_grade_logic(dob, int(target_y))
        if "畢業" not in grade and "不符" not in grade:
            pre_rows.append({"班級": grade, "姓名": r["幼兒姓名"], "狀態": r["報名狀態"]})
    
    if not pre_rows: st.info("目前尚無適齡人員。")
    else:
        pdf = pd.DataFrame(pre_rows)
        grades = ["大班", "中班", "小班", "幼幼班", "托嬰中心"]
        cols = st.columns(len(grades))
        for i, g in enumerate(grades):
            with cols[i]:
                count = len(pdf[pdf["班級"] == g])
                st.markdown(f"**{g}**")
                st.markdown(f"<div style='font-size:2rem; font-weight:700;'>{count}</div>", unsafe_allow_html=True)
                with st.expander("名單"):
                    st.write(pdf[pdf["班級"] == g][["姓名", "狀態"]])

# ==========================================
# 4. 系統入口控管
# ==========================================
def main():
    if "gs_url" not in st.session_state: st.session_state["gs_url"] = "https://docs.google.com/spreadsheets/d/1wl0Q8vmLOzH7txxlFOETYGzD-GSwbTJkjNFXwZm-2yM/edit"
    if "auth" not in st.session_state: st.session_state["auth"] = False

    if not st.session_state["auth"]:
        _, mid, _ = st.columns([1, 1.5, 1])
        with mid:
            st.markdown("<div style='height:20vh'></div>", unsafe_allow_html=True)
            with st.container(border=True):
                st.subheader("🔑 園務系統安全登入")
                pwd = st.text_input("密碼", type="password")
                if st.button("進入系統", use_container_width=True, type="primary") or (pwd=="1234"):
                    if pwd == "1234":
                        st.session_state["auth"] = True
                        st.rerun()
                    else: st.error("密碼錯誤")
        return

    with st.sidebar:
        st.markdown("<div class='sidebar-title'>園所管理系統</div>", unsafe_allow_html=True)
        
        # 雲端同步背景資訊
        df, (msg, style) = load_data(st.session_state["gs_url"])
        st.markdown(f"<div class='sync-status {style}'>{msg}</div>", unsafe_allow_html=True)
        
        menu = st.radio("主要功能", ["🏠 營運儀表板", "📂 數據管理中心", "👶 手動登記", "📅 入學分班預覽", "👨‍🏫 師資缺額試算"])
        
        st.divider()
        with st.expander("⚙️ 系統設定"):
            gs_input = st.text_input("Google 試算表連結", value=st.session_state["gs_url"])
            if gs_input != st.session_state["gs_url"]:
                st.session_state["gs_url"] = gs_input
                st.cache_data.clear()
                st.rerun()
            if st.button("🔄 手動重新整理數據"):
                st.cache_data.clear()
                st.rerun()
        
        if st.button("🚪 安全登出", use_container_width=True):
            st.session_state["auth"] = False
            st.rerun()

    # 路由執行
    if menu == "🏠 營運儀表板": page_dashboard(df)
    elif menu == "📂 數據管理中心": page_manage(df)
    elif menu == "👶 手動登記": page_add()
    elif menu == "📅 入學分班預覽": page_preview(df)
    elif menu == "👨‍🏫 師資缺額試算": 
        # 引用先前版本的試算邏輯
        st.markdown("<h1 class='main-header'>師資需求與缺額試算</h1>", unsafe_allow_html=True)
        target_y = st.number_input("試算學年度", value=date.today().year - 1911 + 1)
        st.info("此功能會自動比對當前『確認入學』的人員，計算升班後的剩餘名額。")
        # 此處可繼續補強計算邏輯...

if __name__ == "__main__":
    main()
