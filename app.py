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
    page_title="新生管理系統 - 雲端同步增強版",
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
    .clean-card {
        background: white;
        padding: 1.2rem;
        border-radius: 12px;
        border: 1px solid var(--border-color);
        margin-bottom: 1rem;
    }
    .result-box {
        background: #ffffff;
        border-left: 5px solid var(--accent-color);
        padding: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        text-align: center;
    }
    .result-grade {
        font-size: 2.2rem;
        font-weight: 700;
        color: var(--accent-color);
        margin: 0.5rem 0;
    }
    /* 側邊欄輸入框標題優化 */
    .sidebar-label {
        font-size: 0.85rem;
        color: #64748B;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 常數與核心邏輯
# ==========================================
NEW_STATUS_OPTIONS = ["預約參觀", "排隊等待", "確認入學", "確定不收"]
IMPORTANCE_OPTIONS = ["優", "中", "差"]
GRADE_ORDER = {"大班": 1, "中班": 2, "小班": 3, "幼幼班": 4, "托嬰中心": 5, "未知": 6, "畢業/超齡": 7, "年齡不符": 8}
PRIORITY_ORDER = {"優": 1, "中": 2, "差": 3}

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

def calculate_roadmap(dob: date):
    if not dob: return []
    today = date.today()
    cur_roc = today.year - 1911 - (1 if today.month < 8 else 0)
    roadmap = []
    for i in range(6):
        target = cur_roc + i
        grade = get_grade_logic(dob, target)
        if "畢業" not in grade and "不符" not in grade:
            roadmap.append(f"{target} 學年 - {grade}")
    return roadmap or ["年齡不符"]

# ==========================================
# 2. 資料存取層 (支援雲端讀取)
# ==========================================
@st.cache_data(ttl=60)
def load_data(gs_url=None):
    df = pd.DataFrame(columns=FINAL_COLS)
    
    # 優先嘗試從 Google Sheets 載入
    if gs_url and "docs.google.com" in gs_url:
        try:
            response = requests.get(gs_url, timeout=10)
            if response.status_code == 200:
                cloud_df = pd.read_csv(StringIO(response.text), dtype=str)
                df = cloud_df
                st.toast("✅ 已成功同步雲端數據")
        except Exception as e:
            st.warning(f"雲端同步失敗。錯誤：{e}")

    # 本地備份讀取（若雲端沒抓到或沒設定）
    if df.empty and os.path.exists(LOCAL_CSV):
        try:
            df = pd.read_csv(LOCAL_CSV, dtype=str)
        except: pass
    
    df = df.fillna("").astype(str)
    for c in FINAL_COLS:
        if c not in df.columns: df[c] = ""
    df["電話"] = df["電話"].apply(normalize_phone)
    df["聯繫狀態"] = df["聯繫狀態"].replace("", "未聯繫")
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
            pwd = st.text_input("請輸入管理密碼", type="password")
            if st.button("進入系統", use_container_width=True, type="primary"):
                if pwd == "1234":
                    st.session_state["authenticated"] = True
                    st.rerun()
                else: st.error("密碼錯誤")
    return False

def page_dashboard(df):
    st.markdown("<div class='main-title'>營運概覽 Dashboard</div>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("待聯繫名單", len(df[df["聯繫狀態"] == "未聯繫"]))
    m2.metric("預約參觀數", len(df[df["報名狀態"] == "預約參觀"]))
    m3.metric("本屆入學確認", len(df[df["報名狀態"] == "確認入學"]))
    m4.metric("總登記人數", len(df))
    
    st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("##### 📌 最近登記 (前 10 筆)")
        if not df.empty:
            st.dataframe(df.tail(10).iloc[::-1][["登記日期", "幼兒姓名", "家長稱呼", "報名狀態"]], use_container_width=True, hide_index=True)
        else:
            st.info("目前尚無名單資料")
    with c2:
        st.markdown("##### 📈 狀態比例")
        if not df.empty:
            st.bar_chart(df["報名狀態"].value_counts(), horizontal=True)

def page_add():
    st.markdown("<div class='main-title'>新生登記作業</div>", unsafe_allow_html=True)
    st.info("💡 建議直接讓家長填寫 Google 表單。若需手動補錄，請填寫下方欄位：")
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("👤 **家長聯絡資訊**")
            p_name = st.text_input("家長姓氏", placeholder="例如：張")
            p_title = st.selectbox("稱謂", ["媽媽", "爸爸", "先生", "小姐"])
            phone = st.text_input("聯絡電話")
            referrer = st.text_input("推薦人 (選填)")
        with c2:
            st.markdown("👶 **幼兒基本資訊**")
            c_name = st.text_input("幼兒姓名")
            st.write("出生日期 (民國)")
            rcols = st.columns(3)
            ry = rcols[0].number_input("年", 90, 130, 112)
            rm = rcols[1].selectbox("月", range(1, 13))
            rd = rcols[2].selectbox("日", range(1, 32))
            note = st.text_area("備註事項", height=68)
        
        if st.button("➕ 儲存至系統", type="primary", use_container_width=True):
            if not c_name or not phone: st.warning("請填寫姓名與電話")
            else:
                try:
                    dob = date(ry + 1911, rm, rd)
                    plans = calculate_roadmap(dob)
                    main_df = load_data(st.session_state.get("gs_url"))
                    new_row = pd.DataFrame([{
                        "報名狀態": "預約參觀", "聯繫狀態": "未聯繫", "登記日期": to_roc_str(date.today()),
                        "幼兒姓名": c_name, "家長稱呼": f"{p_name}{p_title}", "電話": normalize_phone(phone),
                        "幼兒生日": f"{ry}/{rm}/{rd}", "預計入學資訊": plans[0] if plans else "待確認",
                        "推薦人": referrer, "備註": note, "重要性": "中"
                    }])
                    if save_data(pd.concat([main_df, new_row], ignore_index=True)):
                        st.success("✅ 手動登記成功")
                        time.sleep(0.5)
                        st.rerun()
                except: st.error("日期格式錯誤")

def page_manage(df):
    st.markdown("<div class='main-title'>📂 數據管理中心</div>", unsafe_allow_html=True)
    
    search_kw = st.text_input("🔍 搜尋名單 (姓名或電話)", placeholder="快速過濾目前顯示的資料...")

    # 表格顯示與編輯
    display_df = df.copy()
    if search_kw:
        display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search_kw, case=False)).any(axis=1)]
    
    st.info(f"📊 目前共有 {len(display_df)} 筆資料")

    # 輔助計算分配班級（僅顯示用）
    today = date.today()
    cur_y = today.year - 1911 - (1 if today.month < 8 else 0)
    display_df["預計班級"] = display_df["幼兒生日"].apply(lambda x: get_grade_logic(parse_roc_date(x), cur_y + 1))
    display_df["已聯繫"] = display_df["聯繫狀態"] == "已聯繫"

    edited_df = st.data_editor(
        display_df,
        column_order=["登記日期", "已聯繫", "報名狀態", "重要性", "幼兒姓名", "家長稱呼", "電話", "預計班級", "備註"],
        column_config={
            "登記日期": st.column_config.TextColumn("登記日期", disabled=True),
            "預計班級": st.column_config.TextColumn("明年入學班級", disabled=True),
            "已聯繫": st.column_config.CheckboxColumn("📞 已聯繫"),
            "報名狀態": st.column_config.SelectboxColumn("錄取狀態", options=NEW_STATUS_OPTIONS),
            "重要性": st.column_config.SelectboxColumn("優先級", options=IMPORTANCE_OPTIONS),
            "備註": st.column_config.TextColumn("備註", width="large"),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key="data_mgmt_editor"
    )

    if st.button("💾 儲存所有修改", type="primary", use_container_width=True):
        full_df = load_data(st.session_state.get("gs_url"))
        edited_df["聯繫狀態"] = edited_df["已聯繫"].apply(lambda x: "已聯繫" if x else "未聯繫")
        
        if search_kw:
            # 使用 update 需要確保索引對齊，此處為簡化邏輯直接合併
            # 若數據量極大建議優化此處
            full_df.update(edited_df)
            save_target = full_df
        else:
            save_target = edited_df
        
        if save_data(save_target):
            st.success("✅ 變更已成功同步至本地資料庫")
            time.sleep(0.5)
            st.rerun()

def page_quick_check():
    st.markdown("<div class='main-title'>學年快速查詢</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.markdown("<div class='clean-card'>", unsafe_allow_html=True)
        mode = st.radio("日期模式", ["民國", "西元"], horizontal=True)
        if mode == "民國":
            ry = st.number_input("年", 90, 130, 112)
            rm = st.selectbox("月", range(1, 13))
            rd = st.selectbox("日", range(1, 32))
            try: dob = date(ry + 1911, rm, rd)
            except: dob = None
        else: dob = st.date_input("選擇日期", value=date(2023, 1, 1))
        st.markdown("</div>", unsafe_allow_html=True)

    if dob:
        with c2:
            roadmap = calculate_roadmap(dob)
            cur_info = roadmap[0] if roadmap else "無法計算"
            grade = cur_info.split(" - ")[-1]
            year = cur_info.split(" - ")[0]
            st.markdown(f"""
            <div class='result-box'>
                <div style='color: #64748B;'>{year} 學年度</div>
                <div class='result-grade'>{grade}</div>
                <div style='font-size: 0.9rem; color: #94A3B8;'>生日：{to_roc_str(dob)}</div>
            </div>
            """, unsafe_allow_html=True)
            with st.expander("未來五年升學路徑預測"):
                st.table(pd.DataFrame([r.split(" - ") for r in roadmap], columns=["學年度", "預計年段"]))

def page_preview(df):
    st.markdown("<div class='main-title'>未來入學預覽</div>", unsafe_allow_html=True)
    target_y = st.number_input("檢視目標學年度", value=date.today().year - 1911 + 1)
    
    preview_rows = []
    for _, r in df.iterrows():
        if "確定不收" in r["報名狀態"]: continue
        dob = parse_roc_date(r["幼兒生日"])
        grade = get_grade_logic(dob, int(target_y))
        if "畢業" not in grade and "不符" not in grade:
            preview_rows.append({"班級": grade, "狀態": r["報名狀態"], "幼兒姓名": r["幼兒姓名"], "電話": r["電話"]})
    
    if not preview_rows: st.info("目前名單中尚無適齡人員")
    else:
        pdf = pd.DataFrame(preview_rows)
        grades = ["大班", "中班", "小班", "幼幼班", "托嬰中心"]
        cols = st.columns(len(grades))
        for i, g in enumerate(grades):
            with cols[i]:
                g_count = len(pdf[pdf["級別" if "級別" in pdf.columns else "班級"] == g])
                st.markdown(f"**{g}**")
                st.markdown(f"<div style='font-size:1.8rem; font-weight:700;'>{g_count}</div>", unsafe_allow_html=True)
                with st.expander("名單"):
                    st.write(pdf[pdf["班級"] == g][["幼兒姓名", "狀態"]])

def page_calc(df):
    st.markdown("<div class='main-title'>師資與缺額試算</div>", unsafe_allow_html=True)
    with st.container(border=True):
        cal_y = st.number_input("試算學年度", value=date.today().year - 1911 + 1)
        ref_y = cal_y - 1
        old_counts = {"幼幼班": 0, "小班": 0, "中班": 0}
        for _, r in df.iterrows():
            if r["報名狀態"] == "確認入學":
                dob = parse_roc_date(r["幼兒生日"])
                gr = get_grade_logic(dob, ref_y)
                if gr in old_counts: old_counts[gr] += 1
        
        total_rising = sum(old_counts.values())
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 🐘 3-6歲混齡班區")
            st.caption(f"由 {ref_y} 學年直升舊生：{total_rising} 人")
            target_mix = st.number_input("混齡班核定總額", value=90)
            ratio = 12 if cal_y >= 115 else 15
            st.metric("可對外招生缺額", f"{max(0, target_mix - total_rising)} 人")
            st.metric(f"應配師資 (1:{ratio})", f"{math.ceil(target_mix / ratio)} 名")
        with c2:
            st.markdown("##### 🐥 2-3歲幼幼班")
            target_t = st.number_input("幼幼班預計名額", value=16)
            st.metric("幼幼班總收托", f"{target_t} 人")
            st.metric("應配師資 (1:8)", f"{math.ceil(target_t / 8)} 名")

# ==========================================
# 4. 主程式控管
# ==========================================
def main():
    if not login_screen(): return
    
    # 初始化 session_state
    if "gs_url" not in st.session_state:
        st.session_state["gs_url"] = ""

    with st.sidebar:
        st.markdown("<div style='text-align:center; padding: 1rem;'><h2 style='margin:0;'>🏫</h2><h4 style='margin:0;'>園所管理系統</h4></div>", unsafe_allow_html=True)
        
        st.divider()
        # --- 雲端同步設定 (移至側邊欄，使其隨時可見) ---
        st.markdown("### ☁️ 雲端同步設定")
        st.markdown("<div class='sidebar-label'>請輸入 Google 試算表 CSV 網址：</div>", unsafe_allow_html=True)
        gs_url_input = st.text_input("CSV URL", 
                                     value=st.session_state["gs_url"],
                                     placeholder="貼上網址...",
                                     label_visibility="collapsed")
        
        if gs_url_input != st.session_state["gs_url"]:
            st.session_state["gs_url"] = gs_url_input
            st.cache_data.clear()
            st.rerun()
            
        if st.button("🔄 手動刷新雲端數據", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
            
        st.divider()
        menu = st.radio("主要功能選單", ["🏠 營運儀表板", "👶 新生報名登記", "📂 數據管理中心", "🎓 學年快速查詢", "📅 未來入學預覽", "👩‍🏫 招生師資試算"])
        
        st.divider()
        st.caption(f"📅 今日：{to_roc_str(date.today())}")
        if st.button("🚪 安全登出", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

    # 載入數據 (優先讀取側邊欄設定的 URL)
    df = load_data(st.session_state["gs_url"])

    if menu == "🏠 營運儀表板": page_dashboard(df)
    elif menu == "👶 新生報名登記": page_add()
    elif menu == "📂 數據管理中心": page_manage(df)
    elif menu == "🎓 學年快速查詢": page_quick_check()
    elif menu == "📅 未來入學預覽": page_preview(df)
    elif menu == "👩‍🏫 招生師資試算": page_calc(df)

if __name__ == "__main__":
    main()
