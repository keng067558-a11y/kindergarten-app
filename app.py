import streamlit as st
import pandas as pd
from datetime import date, datetime
import math
import time

# ==========================================
# 0. 基礎配置與 CSS 優化 (專業簡潔版)
# ==========================================
st.set_page_config(
    page_title="新生與經費管理系統",
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

    /* 頂部導航與標題優化 */
    .main-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: var(--primary-color);
        margin-bottom: 1.5rem;
    }

    /* 指標方塊 (Metric) 優化 */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid var(--border-color);
    }
    
    /* 卡片容器 (Card) */
    .clean-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid var(--border-color);
        margin-bottom: 1rem;
    }

    /* 按鈕優化 */
    .stButton>button {
        border-radius: 6px;
        font-weight: 500;
        height: 2.8rem;
        transition: all 0.2s ease;
    }
    
    /* 側邊欄優化 */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid var(--border-color);
    }

    /* 資料編輯器表格美化 */
    div[data-testid="stDataFrame"] {
        border-radius: 8px;
        overflow: hidden;
    }

    /* 快速查詢結果方塊 */
    .result-box {
        background: #ffffff;
        border-left: 5px solid var(--accent-color);
        padding: 2rem;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        text-align: center;
    }
    .result-grade {
        font-size: 2.5rem;
        font-weight: 700;
        color: var(--accent-color);
        margin: 0.5rem 0;
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
# 2. 資料存取層
# ==========================================
@st.cache_data(ttl=600)
def load_data():
    try:
        df = pd.read_csv(LOCAL_CSV, dtype=str)
    except:
        df = pd.DataFrame(columns=FINAL_COLS)
    
    df = df.fillna("").astype(str)
    for c in FINAL_COLS:
        if c not in df.columns: df[c] = ""
    df["電話"] = df["電話"].apply(normalize_phone)
    df["聯繫狀態"] = df["聯繫狀態"].replace("", "未聯繫")
    return df[FINAL_COLS]

def save_data(df: pd.DataFrame):
    try:
        # 移除輔助欄位再儲存
        save_df = df.copy()
        for col in ["建議班級", "已聯繫", "排序權重"]:
            if col in save_df.columns:
                save_df = save_df.drop(columns=[col])
        
        save_df = save_df[FINAL_COLS].fillna("").astype(str)
        save_df.to_csv(LOCAL_CSV, index=False, encoding="utf-8-sig")
        load_data.clear()
        return True
    except Exception as e:
        st.error(f"數據儲存失敗：{e}")
        return False

# ==========================================
# 3. 介面渲染
# ==========================================

def login_screen():
    if st.session_state.get("authenticated"): return True
    cols = st.columns([1, 1, 1])
    with cols[1]:
        st.markdown("<div style='height:15vh'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.subheader("🔑 系統登入")
            pwd = st.text_input("輸入管理密碼", type="password")
            if st.button("進入系統", use_container_width=True, type="primary"):
                if pwd == "1234":
                    st.session_state["authenticated"] = True
                    st.rerun()
                else: st.error("密碼不正確")
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
        st.markdown("##### 📌 最近登記")
        st.dataframe(df.tail(8)[["登記日期", "幼兒姓名", "家長稱呼", "報名狀態"]], use_container_width=True, hide_index=True)
    with c2:
        st.markdown("##### 📈 狀態比例")
        if not df.empty:
            st.bar_chart(df["報名狀態"].value_counts(), horizontal=True)

def page_add():
    st.markdown("<div class='main-title'>新生登記作業</div>", unsafe_allow_html=True)
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
        
        if st.button("➕ 加入暫存", type="secondary", use_container_width=True):
            if not c_name or not phone: st.warning("請填寫姓名與電話")
            else:
                try:
                    dob = date(ry + 1911, rm, rd)
                    plans = calculate_roadmap(dob)
                    if "temp_children" not in st.session_state: st.session_state["temp_children"] = []
                    st.session_state["temp_children"].append({
                        "幼兒姓名": c_name, "幼兒生日": f"{ry}/{rm}/{rd}", "報名狀態": "預約參觀",
                        "預計入學資訊": plans[0] if plans else "待確認", "備註": note,
                        "重要性": "中", "家長": f"{p_name}{p_title}", "電話": normalize_phone(phone), "推薦人": referrer
                    })
                    st.toast("已加入暫存清單")
                except: st.error("日期無效")

    if st.session_state.get("temp_children"):
        st.markdown("---")
        st.markdown("##### 🛒 待送出清單")
        edited = st.data_editor(pd.DataFrame(st.session_state["temp_children"]), use_container_width=True, num_rows="dynamic")
        if st.button("🚀 確認存入系統", type="primary", use_container_width=True):
            main_df = load_data()
            new_rows = []
            for _, r in edited.iterrows():
                new_rows.append({
                    "報名狀態": r["報名狀態"], "聯繫狀態": "未聯繫", "登記日期": to_roc_str(date.today()),
                    "幼兒姓名": r["幼兒姓名"], "家長稱呼": r["家長"], "電話": r["電話"],
                    "幼兒生日": r["幼兒生日"], "預計入學資訊": r["預計入學資訊"], "推薦人": r["推薦人"],
                    "備註": r["備註"], "重要性": r["重要性"]
                })
            if save_data(pd.concat([main_df, pd.DataFrame(new_rows)], ignore_index=True)):
                st.success("資料已成功入庫")
                st.session_state["temp_children"] = []
                time.sleep(1)
                st.rerun()

def page_manage(df):
    st.markdown("<div class='main-title'>數據管理中心</div>", unsafe_allow_html=True)
    
    # 計算當前建議班級 (用於排序與顯示)
    today = date.today()
    cur_roc_y = today.year - 1911 - (1 if today.month < 8 else 0)
    
    def get_row_grade(b_str):
        dob = parse_roc_date(b_str)
        return get_grade_logic(dob, cur_roc_y)

    df["建議班級"] = df["幼兒生日"].apply(get_row_grade)
    df["排序權重"] = df["建議班級"].map(GRADE_ORDER).fillna(9)
    df["優先權重"] = df["重要性"].map(PRIORITY_ORDER).fillna(9)
    
    # 執行排序：先比班級(大到小)，再比優先權(優到差)
    df = df.sort_values(by=["排序權重", "優先權重", "登記日期"], ascending=[True, True, False])

    # 搜尋與篩選
    c_s1, c_s2 = st.columns([3, 1])
    search_kw = c_s1.text_input("🔍 搜尋姓名、電話或備註", placeholder="輸入關鍵字...")
    filter_grade = c_s2.selectbox("📂 班級快速篩選", ["全部"] + list(GRADE_ORDER.keys()))

    if search_kw:
        df = df[df.astype(str).apply(lambda x: x.str.contains(search_kw, case=False)).any(axis=1)]
    if filter_grade != "全部":
        df = df[df["建議班級"] == filter_grade]

    st.markdown(f"目前顯示：**{len(df)}** 筆資料")

    df["已聯繫"] = df["聯繫狀態"].apply(lambda x: True if x == "已聯繫" else False)
    
    # 優化後的表格編輯器
    edited_df = st.data_editor(
        df,
        column_order=["建議班級", "已聯繫", "報名狀態", "重要性", "幼兒姓名", "家長稱呼", "電話", "幼兒生日", "備註"],
        column_config={
            "建議班級": st.column_config.TextColumn("目前學年班級", width="small", disabled=True),
            "已聯繫": st.column_config.CheckboxColumn("已聯繫"),
            "報名狀態": st.column_config.SelectboxColumn("狀態", options=NEW_STATUS_OPTIONS, width="medium"),
            "重要性": st.column_config.SelectboxColumn("優先級", options=IMPORTANCE_OPTIONS, width="small"),
            "幼兒姓名": st.column_config.TextColumn("幼兒姓名", width="medium"),
            "家長稱呼": st.column_config.TextColumn("家長", width="medium"),
            "電話": st.column_config.TextColumn("聯絡電話", width="medium"),
            "備註": st.column_config.TextColumn("備註", width="large"),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic"
    )
    
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    c_btn1, c_btn2, c_btn3 = st.columns([2, 2, 1])
    if c_btn1.button("💾 儲存所有修改內容", type="primary", use_container_width=True):
        edited_df["聯繫狀態"] = edited_df["已聯繫"].apply(lambda x: "已聯繫" if x else "未聯繫")
        if save_data(edited_df):
            st.success("🎉 資料庫已成功更新並重新排序！")
            time.sleep(1)
            st.rerun()
            
    if c_btn2.download_button("📥 匯出當前名單 CSV", df.to_csv(index=False).encode("utf-8-sig"), "data_export.csv", use_container_width=True):
        st.toast("匯出成功")
        
    if c_btn3.button("🔄 重新載入", use_container_width=True):
        st.rerun()

def page_quick_check():
    st.markdown("<div class='main-title'>學年快速查詢</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.markdown("<div class='clean-card'>", unsafe_allow_html=True)
        mode = st.radio("輸入模式", ["民國", "西元"], horizontal=True)
        if mode == "民國":
            ry = st.number_input("年", 90, 130, 112)
            rm = st.selectbox("月", range(1, 13))
            rd = st.selectbox("日", range(1, 32))
            try: dob = date(ry + 1911, rm, rd)
            except: dob = None
        else: dob = st.date_input("出生日期", value=date(2023, 1, 1))
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
            with st.expander("完整升學路徑預測"):
                st.table(pd.DataFrame([r.split(" - ") for r in roadmap], columns=["學年度", "預計年段"]))

def page_preview(df):
    st.markdown("<div class='main-title'>未來入學預覽</div>", unsafe_allow_html=True)
    target_y = st.number_input("目標學年度", value=date.today().year - 1911 + 1)
    
    preview_rows = []
    for _, r in df.iterrows():
        if "確定不收" in r["報名狀態"]: continue
        dob = parse_roc_date(r["幼兒生日"])
        grade = get_grade_logic(dob, int(target_y))
        if "畢業" not in grade and "不符" not in grade:
            preview_rows.append({"班級": grade, "狀態": r["報名狀態"], "幼兒姓名": r["幼兒姓名"], "電話": r["電話"]})
    
    if not preview_rows: st.info("尚無符合該學年的名單")
    else:
        pdf = pd.DataFrame(preview_rows)
        grades = ["大班", "中班", "小班", "幼幼班", "托嬰中心"]
        cols = st.columns(len(grades))
        for i, g in enumerate(grades):
            with cols[i]:
                g_count = len(pdf[pdf["班級"] == g])
                st.markdown(f"**{g}**")
                st.markdown(f"<div style='font-size:1.8rem; font-weight:700;'>{g_count}</div>", unsafe_allow_html=True)
                with st.expander("名單"):
                    st.write(pdf[pdf["班級"] == g][["幼兒姓名", "狀態"]])

def page_calc(df):
    st.markdown("<div class='main-title'>招生缺額與師資試算</div>", unsafe_allow_html=True)
    with st.container(border=True):
        cal_y = st.number_input("目標試算學年", value=date.today().year - 1911 + 1)
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
            st.markdown("##### 🐘 3-6歲混齡區")
            st.caption(f"由 {ref_y} 學年升上之舊生：{total_rising} 人")
            target_mix = st.number_input("核定總額", value=90)
            ratio = 12 if cal_y >= 115 else 15
            st.metric("預計對外招生缺額", f"{target_mix - total_rising} 人")
            st.metric(f"所需師資 (1:{ratio})", f"{math.ceil(target_mix / ratio)} 名")
        with c2:
            st.markdown("##### 🐥 2-3歲幼幼班")
            target_t = st.number_input("預計招收名額 ", value=16)
            st.metric("幼幼班總額", f"{target_t} 人")
            st.metric("所需師資 (1:8)", f"{math.ceil(target_t / 8)} 名")

# ==========================================
# 4. 主程式控管
# ==========================================
def main():
    if not login_screen(): return
    with st.sidebar:
        st.markdown("<div style='text-align:center; padding: 1rem;'><h2 style='margin:0;'>🏫</h2><h4 style='margin:0;'>管理系統</h4></div>", unsafe_allow_html=True)
        menu = st.radio("功能選單", ["🏠 營運儀表板", "👶 新生報名登記", "📂 數據管理中心", "🎓 學年快速查詢", "📅 未來入學預覽", "👩‍🏫 招生師資試算"])
        st.divider()
        st.caption(f"系統狀態：已連線")
        st.caption(f"今日：{to_roc_str(date.today())}")
        if st.button("🚪 安全登出", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

    df = load_data()
    pages = {
        "🏠 營運儀表板": lambda: page_dashboard(df),
        "👶 新生報名登記": page_add,
        "📂 數據管理中心": lambda: page_manage(df),
        "🎓 學年快速查詢": page_quick_check,
        "📅 未來入學預覽": lambda: page_preview(df),
        "👩‍🏫 招生師資試算": lambda: page_calc(df)
    }
    pages[menu]()

if __name__ == "__main__":
    main()
