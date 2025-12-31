import streamlit as st
import pandas as pd
from datetime import date, datetime
import math
import time
import os
import requests
from io import StringIO
import re

# ==========================================
# 0. 基礎配置與專業 UI 樣式
# ==========================================
st.set_page_config(
    page_title="新生與園務管理系統 - 穩定修復版",
    layout="wide",
    page_icon="🏫",
    initial_sidebar_state="expanded"
)

# 自定義專業美化樣式
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&display=swap');
    
    :root {
        --primary-color: #1E293B;
        --accent-color: #3B82F6;
        --bg-color: #F8FAFC;
        --border-color: #E2E8F0;
    }

    html, body, [class*="css"] {
        font-family: 'Noto Sans TC', sans-serif;
        background-color: var(--bg-color);
    }

    .main-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: var(--primary-color);
        padding-bottom: 0.5rem;
        border-bottom: 3px solid var(--accent-color);
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
# 1. 常數與核心轉換邏輯
# ==========================================
FINAL_COLS = [
    "報名狀態", "聯繫狀態", "登記日期", "幼兒姓名", "家長稱呼", "電話",
    "幼兒生日", "預計入學資訊", "推薦人", "備註", "重要性"
]
NEW_STATUS_OPTIONS = ["預約參觀", "排隊等待", "確認入學", "確定不收"]
IMPORTANCE_OPTIONS = ["優", "中", "差"]
GRADE_ORDER = {"大班": 1, "中班": 2, "小班": 3, "幼幼班": 4, "托嬰中心": 5, "未知": 6, "畢業/超齡": 7, "年齡不符": 8}
LOCAL_CSV = "kindergarten_db_backup.csv"

def convert_google_sheet_url(url):
    """將 Google Sheet 網址自動轉換為匯出 CSV 網址"""
    if not url or "docs.google.com" not in url:
        return url
    try:
        # 提取 File ID
        file_id_match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
        if not file_id_match: return url
        file_id = file_id_match.group(1)
        # 提取 gid (工作表 ID)
        gid = "0"
        gid_match = re.search(r'gid=([0-9]+)', url)
        if gid_match:
            gid = gid_match.group(1)
        return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid={gid}"
    except:
        return url

def parse_roc_date(s):
    """解析民國日期字串"""
    try:
        s = str(s).strip()
        if not s or s.lower() == 'nan': return None
        parts = s.replace("-", "/").replace(".", "/").split("/")
        return date(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))
    except:
        return None

def get_grade_logic(birth_date, target_roc_year):
    """計算指定學年的年段"""
    if not birth_date: return "未知"
    by_roc = birth_date.year - 1911
    # 9/2 分界
    is_late = (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2)
    age = target_roc_year - by_roc - (1 if is_late else 0)
    grades = {0: "托嬰中心", 1: "托嬰中心", 2: "幼幼班", 3: "小班", 4: "中班", 5: "大班"}
    return grades.get(age, "畢業/超齡" if age > 5 else "年齡不符")

# ==========================================
# 2. 穩定資料存取層
# ==========================================
@st.cache_data(ttl=30)
def load_data(gs_url):
    df = pd.DataFrame(columns=FINAL_COLS)
    logs = []

    # 1. 嘗試雲端抓取
    if gs_url:
        csv_url = convert_google_sheet_url(gs_url)
        try:
            resp = requests.get(csv_url, timeout=10)
            if resp.status_code == 200:
                df = pd.read_csv(StringIO(resp.text), dtype=str)
                logs.append("✅ 雲端連線成功")
                # 雲端成功後，同時更新本地備份
                df.to_csv(LOCAL_CSV, index=False, encoding="utf-8-sig")
            else:
                logs.append(f"❌ 雲端連線失敗 (HTTP {resp.status_code})")
        except Exception as e:
            logs.append(f"❌ 雲端讀取錯誤: {str(e)}")

    # 2. 雲端失敗或未設定，則讀取本地備份
    if df.empty and os.path.exists(LOCAL_CSV):
        try:
            df = pd.read_csv(LOCAL_CSV, dtype=str)
            logs.append("🏠 正在使用本地備份資料")
        except:
            logs.append("⚠️ 本地檔案損壞或無法讀取")

    # 3. 資料欄位對齊與標準化
    df = df.fillna("").astype(str)
    for col in FINAL_COLS:
        if col not in df.columns: df[col] = ""
    
    return df[FINAL_COLS], " | ".join(logs)

def save_data(df):
    """將資料存入本地資料庫"""
    try:
        df[FINAL_COLS].to_csv(LOCAL_CSV, index=False, encoding="utf-8-sig")
        load_data.clear()
        return True
    except:
        return False

# ==========================================
# 3. 功能頁面模組
# ==========================================

def page_dashboard(df):
    st.markdown("<div class='main-title'>營運概覽 Dashboard</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("總登記人數", len(df))
    c2.metric("預約參觀", len(df[df["報名狀態"]=="預約參觀"]))
    c3.metric("確認入學", len(df[df["報名狀態"]=="確認入學"]))
    c4.metric("待聯繫", len(df[df["聯繫狀態"]!="已聯繫"]))
    
    st.divider()
    st.markdown("##### 📌 最近登記名單")
    st.dataframe(df.tail(10).iloc[::-1][["登記日期", "幼兒姓名", "家長稱呼", "報名狀態"]], use_container_width=True, hide_index=True)

def page_manage(df):
    st.markdown("<div class='main-title'>📂 數據管理中心 (全員瀏覽)</div>", unsafe_allow_html=True)
    
    search = st.text_input("🔍 搜尋名單 (請輸入姓名或電話)", placeholder="快速找人...")
    
    # 這裡的邏輯：顯示過濾後的資料，但儲存時會合併回原始資料庫
    display_df = df.copy()
    if search:
        display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
    
    st.info(f"📊 目前共有 {len(display_df)} 筆資料正在顯示")

    # 編輯表格
    edited = st.data_editor(
        display_df,
        column_order=["登記日期", "報名狀態", "重要性", "幼兒姓名", "家長稱呼", "電話", "幼兒生日", "備註"],
        column_config={
            "報名狀態": st.column_config.SelectboxColumn("狀態", options=NEW_STATUS_OPTIONS),
            "重要性": st.column_config.SelectboxColumn("優先級", options=IMPORTANCE_OPTIONS),
            "備註": st.column_config.TextColumn("備註", width="large")
        },
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        key="main_mgmt_editor"
    )
    
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    if st.button("💾 儲存修改內容", type="primary", use_container_width=True):
        # 智慧更新：如果是有搜尋的情況，只更新改動行，其餘保留
        if search:
            df.update(edited)
            save_target = df
        else:
            save_target = edited
            
        if save_data(save_target):
            st.success("✅ 資料已同步儲存至本地備份庫")
            time.sleep(0.5)
            st.rerun()

def page_add():
    st.markdown("<div class='main-title'>手動報名登記</div>", unsafe_allow_html=True)
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("幼兒姓名")
            parent = st.text_input("家長稱呼")
            phone = st.text_input("電話")
        with c2:
            ry = st.number_input("生日(民國年)", 90, 130, 112)
            rm = st.selectbox("月", range(1, 13))
            rd = st.selectbox("日", range(1, 32))
            note = st.text_area("備註事項")
            
        if st.button("🚀 確認登記存檔", type="primary", use_container_width=True):
            if not name or not phone: st.error("姓名與電話不可空白")
            else:
                main_df, _ = load_data(st.session_state.get("gs_url", ""))
                new_row = pd.DataFrame([{
                    "報名狀態": "預約參觀", "聯繫狀態": "未聯繫",
                    "登記日期": f"{date.today().year-1911}/{date.today().month:02d}/{date.today().day:02d}",
                    "幼兒姓名": name, "家長稱呼": parent, "電話": phone,
                    "幼兒生日": f"{ry}/{rm}/{rd}", "備註": note, "重要性": "中"
                }])
                if save_data(pd.concat([main_df, new_row], ignore_index=True)):
                    st.success("登記完成！")
                    time.sleep(0.5)
                    st.rerun()

def page_calc(df):
    st.markdown("<div class='main-title'>師資與缺額試算</div>", unsafe_allow_html=True)
    target_y = st.number_input("試算學年度", value=date.today().year-1911+1)
    ref_y = target_y - 1
    
    # 計算舊生人數
    rising_counts = {"幼幼班": 0, "小班": 0, "中班": 0}
    for _, r in df.iterrows():
        if r["報名狀態"] == "確認入學":
            dob = parse_roc_date(r["幼兒生日"])
            grade = get_grade_logic(dob, ref_y)
            if grade in rising_counts: rising_counts[grade] += 1
            
    total_rising = sum(rising_counts.values())
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 🐘 3-6歲混齡班")
        st.caption(f"由 {ref_y} 年直升之舊生：{total_rising} 人")
        max_mix = st.number_input("核定混齡總額", value=90)
        ratio = 12 if target_y >= 115 else 15
        st.metric("預計對外招收缺額", f"{max(0, max_mix - total_rising)} 人")
        st.metric(f"師資需求 (1:{ratio})", f"{math.ceil(max_mix / ratio)} 名")
    with c2:
        st.markdown("##### 🐥 2-3歲幼幼班")
        max_t = st.number_input("幼幼班核定額", value=16)
        st.metric("幼幼班預計招收", f"{max_t} 人")
        st.metric("師資需求 (1:8)", f"{math.ceil(max_t / 8)} 名")

# ==========================================
# 4. 主程式流程
# ==========================================
def main():
    if "gs_url" not in st.session_state: st.session_state["gs_url"] = ""
    if "auth" not in st.session_state: st.session_state["auth"] = False

    # 登入邏輯
    if not st.session_state["auth"]:
        _, mid, _ = st.columns([1, 1.5, 1])
        with mid:
            st.markdown("<div style='height:20vh'></div>", unsafe_allow_html=True)
            with st.container(border=True):
                st.subheader("🏫 系統安全登入")
                pwd = st.text_input("請輸入密碼", type="password")
                if st.button("進入系統", use_container_width=True, type="primary") or (pwd=="1234" and pwd):
                    if pwd == "1234":
                        st.session_state["auth"] = True
                        st.rerun()
                    else: st.error("密碼錯誤")
        return

    # 側邊欄設定
    with st.sidebar:
        st.markdown("### ⚙️ 系統設定與連結")
        gs_url_input = st.text_input("Google 試算表網址", 
                                     value=st.session_state["gs_url"], 
                                     placeholder="請直接貼上編輯網址...")
        if gs_url_input != st.session_state["gs_url"]:
            st.session_state["gs_url"] = gs_url_input
            st.cache_data.clear()
            st.rerun()
            
        st.divider()
        menu = st.radio("功能選單", ["🏠 營運儀表板", "📂 數據管理中心", "👶 手動報名登記", "👩‍🏫 師資缺額試算"])
        
        st.divider()
        if st.button("🚪 安全登出", use_container_width=True):
            st.session_state["auth"] = False
            st.rerun()

    # 載入資料
    df, log_msg = load_data(st.session_state["gs_url"])
    st.caption(f"數據連線狀態：{log_msg}")

    # 分頁導覽
    if menu == "🏠 營運儀表板": page_dashboard(df)
    elif menu == "📂 數據管理中心": page_manage(df)
    elif menu == "👶 手動報名登記": page_add()
    elif menu == "👩‍🏫 師資缺額試算": page_calc(df)

if __name__ == "__main__":
    main()
