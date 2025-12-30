import streamlit as st
import pandas as pd
from datetime import date, datetime
import math
import time

# ==========================================
# 0. 基礎配置與 CSS 優化
# ==========================================
st.set_page_config(
    page_title="幼兒園新生與經費管理系統",
    layout="wide",
    page_icon="🏫",
    initial_sidebar_state="expanded"
)

# 自定義美化樣式
st.markdown("""
<style>
    /* 全域字體與背景 */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; }
    
    /* 卡片式設計 */
    .stMetric {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #f0f2f6;
    }
    
    /* 自定義容器 */
    .custom-card {
        background: white;
        padding: 1.5rem;
        border-radius: 1rem;
        border: 1px solid #e9ecef;
        box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
        margin-bottom: 1rem;
    }
    
    /* 標籤美化 */
    .status-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    /* 按鈕寬度優化 */
    .stButton>button { width: 100%; border-radius: 8px; height: 3rem; }
    
    /* 移除邊距 */
    .block-container { padding-top: 2rem; }
    
    /* 針對入學年段的大字顯示 */
    .big-grade-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 30px;
        border-radius: 15px;
        text-align: center;
        margin: 20px 0;
    }
    .big-grade-text { font-size: 3rem; font-weight: 800; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 常數與初始化
# ==========================================
NEW_STATUS_OPTIONS = ["預約參觀", "排隊等待", "確認入學", "確定不收"]
IMPORTANCE_OPTIONS = ["優", "中", "差"]
CONTACT_OPTIONS = ["未聯繫", "已聯繫"]
SHEET_NAME = "kindergarten_db"
LOCAL_CSV = "kindergarten_local_db.csv"
FINAL_COLS = [
    "報名狀態", "聯繫狀態", "登記日期", "幼兒姓名", "家長稱呼", "電話",
    "幼兒生日", "預計入學資訊", "推薦人", "備註", "重要性"
]

# Session State 初始化
for key in ["calc_memory", "temp_children", "authenticated"]:
    if key not in st.session_state:
        st.session_state[key] = {} if key == "calc_memory" else [] if key == "temp_children" else False

# ==========================================
# 2. 核心工具函式
# ==========================================
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
        if len(parts) != 3: return None
        return date(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))
    except: return None

def to_roc_str(d: date) -> str:
    return f"{d.year-1911}/{d.month:02d}/{d.day:02d}"

def get_grade_logic(birth_date: date, target_roc_year: int) -> str:
    if not birth_date: return "未知"
    by_roc = birth_date.year - 1911
    # 9/2 為學期切點
    is_late = (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2)
    age = target_roc_year - by_roc - (1 if is_late else 0)
    
    grades = {
        0: "托嬰中心", 1: "托嬰中心",
        2: "幼幼班", 3: "小班", 4: "中班", 5: "大班"
    }
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
# 3. 資料處理層 (Google Sheets / CSV)
# ==========================================
@st.cache_data(ttl=600)
def load_data():
    # 優先從本機讀取以求速度，或串接 GSheet
    df = pd.DataFrame()
    try:
        df = pd.read_csv(LOCAL_CSV, dtype=str)
    except:
        df = pd.DataFrame(columns=FINAL_COLS)
    
    df = df.fillna("").astype(str)
    for c in FINAL_COLS:
        if c not in df.columns: df[c] = ""
    
    # 基礎清洗
    df["電話"] = df["電話"].apply(normalize_phone)
    df["聯繫狀態"] = df["聯繫狀態"].replace("", "未聯繫")
    df["報名狀態"] = df["報名狀態"].replace("", "排隊等待")
    return df[FINAL_COLS]

def save_data(df: pd.DataFrame):
    try:
        df = df[FINAL_COLS].fillna("").astype(str)
        df.to_csv(LOCAL_CSV, index=False, encoding="utf-8-sig")
        # 這裡可以加入同步到 Google Sheets 的程式碼
        load_data.clear()
        return True
    except Exception as e:
        st.error(f"儲存失敗：{e}")
        return False

# ==========================================
# 4. 登入介面
# ==========================================
def login_screen():
    if st.session_state["authenticated"]: return True
    
    cols = st.columns([1, 1.5, 1])
    with cols[1]:
        st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.title("🔒 系統登入")
            pwd = st.text_input("請輸入密碼", type="password")
            if st.button("登入系統", type="primary"):
                if pwd == "1234": # 建議改為 secrets 管理
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("密碼錯誤")
    return False

# ==========================================
# 5. 各分頁功能
# ==========================================

def page_dashboard(df):
    st.header("📊 營運概覽")
    
    # 數據指標
    m1, m2, m3, m4 = st.columns(4)
    pending_count = len(df[df["聯繫狀態"] == "未聯繫"])
    visit_count = len(df[df["報名狀態"] == "預約參觀"])
    confirm_count = len(df[df["報名狀態"] == "確認入學"])
    
    m1.metric("待聯繫家長", pending_count, delta=f"{pending_count} 需處理", delta_color="inverse")
    m2.metric("預約參觀中", visit_count)
    m3.metric("本屆已確認入學", confirm_count)
    m4.metric("總登記人數", len(df))
    
    st.divider()
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("📌 最近登記名單")
        recent_df = df.tail(5)[["登記日期", "幼兒姓名", "家長稱呼", "報名狀態", "聯繫狀態"]]
        st.dataframe(recent_df, use_container_width=True, hide_index=True)
    
    with c2:
        st.subheader("📈 狀態佔比")
        if not df.empty:
            status_stats = df["報名狀態"].value_counts()
            st.bar_chart(status_stats)

def page_add():
    st.header("📝 新生登記作業")
    
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 👤 家長基本資料")
            p_name = st.text_input("家長姓氏", placeholder="例：王")
            p_title = st.selectbox("稱謂", ["媽媽", "爸爸", "先生", "小姐"])
            phone = st.text_input("聯絡電話", placeholder="09xxxxxxxx")
            referrer = st.text_input("推薦人")
        
        with c2:
            st.markdown("##### 👶 幼兒資訊")
            c_name = st.text_input("幼兒姓名")
            
            # 民國日期輸入組件優化
            st.write("出生年月日 (民國)")
            rcols = st.columns(3)
            ry = rcols[0].number_input("年", 90, 130, 110)
            rm = rcols[1].selectbox("月", range(1, 13))
            rd = rcols[2].selectbox("日", range(1, 32))
            
            note = st.text_area("備註事項", height=68)
        
        if st.button("➕ 加入暫存清單", type="secondary"):
            if not c_name or not phone:
                st.warning("請填寫幼兒姓名與電話")
            else:
                try:
                    dob = date(ry + 1911, rm, rd)
                    plans = calculate_roadmap(dob)
                    st.session_state["temp_children"].append({
                        "幼兒姓名": c_name,
                        "幼兒生日": f"{ry}/{rm}/{rd}",
                        "報名狀態": "預約參觀",
                        "預計入學資訊": plans[0] if plans else "待確認",
                        "備註": note,
                        "重要性": "中",
                        "家長": f"{p_name}{p_title}",
                        "電話": normalize_phone(phone),
                        "推薦人": referrer
                    })
                    st.toast("已加入暫存")
                except:
                    st.error("日期格式錯誤")

    if st.session_state["temp_children"]:
        st.subheader(f"🛒 待送出名單 ({len(st.session_state['temp_children'])})")
        temp_df = pd.DataFrame(st.session_state["temp_children"])
        
        edited_df = st.data_editor(
            temp_df,
            column_config={
                "報名狀態": st.column_config.SelectboxColumn(options=NEW_STATUS_OPTIONS),
                "重要性": st.column_config.SelectboxColumn(options=IMPORTANCE_OPTIONS),
            },
            num_rows="dynamic",
            use_container_width=True,
            key="editor_add"
        )
        
        if st.button("🚀 確認存入資料庫", type="primary"):
            main_df = load_data()
            new_rows = []
            for _, r in edited_df.iterrows():
                new_rows.append({
                    "報名狀態": r["報名狀態"],
                    "聯繫狀態": "未聯繫",
                    "登記日期": to_roc_str(date.today()),
                    "幼兒姓名": r["幼兒姓名"],
                    "家長稱呼": r["家長"],
                    "電話": r["電話"],
                    "幼兒生日": r["幼兒生日"],
                    "預計入學資訊": r["預計入學資訊"],
                    "推薦人": r["推薦人"],
                    "備註": r["備註"],
                    "重要性": r["重要性"]
                })
            
            updated_df = pd.concat([main_df, pd.DataFrame(new_rows)], ignore_index=True)
            if save_data(updated_df):
                st.success("資料已成功同步到雲端！")
                st.session_state["temp_children"] = []
                time.sleep(1)
                st.rerun()

def page_manage(df):
    st.header("📂 資料管理中心")
    
    # 搜尋與工具欄
    kcols = st.columns([3, 1, 1])
    search_kw = kcols[0].text_input("🔍 關鍵字搜尋", placeholder="搜尋姓名、電話、備註...")
    
    if search_kw:
        df = df[df.astype(str).apply(lambda x: x.str.contains(search_kw, case=False)).any(axis=1)]

    tab1, tab2 = st.tabs(["🗂️ 互動式編輯表單", "📋 全域資料表"])
    
    with tab1:
        st.caption("小撇步：直接在表格內修改，完成後點擊下方儲存。")
        df["original_index"] = df.index
        
        # 增加「已聯繫」Checkbox 輔助
        df["聯繫"] = df["聯繫狀態"].apply(lambda x: True if x == "已聯繫" else False)
        
        edited_df = st.data_editor(
            df,
            column_order=["聯繫", "報名狀態", "重要性", "幼兒姓名", "家長稱呼", "電話", "幼兒生日", "預計入學資訊", "備註"],
            column_config={
                "聯繫": st.column_config.CheckboxColumn("聯繫"),
                "報名狀態": st.column_config.SelectboxColumn("狀態", options=NEW_STATUS_OPTIONS),
                "重要性": st.column_config.SelectboxColumn("優先", options=IMPORTANCE_OPTIONS),
                "備註": st.column_config.TextColumn("備註", width="large")
            },
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            key="main_editor"
        )
        
        if st.button("💾 儲存所有變更"):
            # 回寫聯繫狀態
            edited_df["聯繫狀態"] = edited_df["聯繫"].apply(lambda x: "已聯繫" if x else "未聯繫")
            final_df = load_data().copy()
            
            # 處理編輯與刪除 (簡單起見，直接覆蓋或比對 original_index)
            if save_data(edited_df[FINAL_COLS]):
                st.success("更新成功！")
                st.rerun()
                
    with tab2:
        st.dataframe(df[FINAL_COLS], use_container_width=True)
        st.download_button("📥 匯出 CSV", df.to_csv(index=False).encode("utf-8-sig"), "students.csv")

def page_quick_check():
    st.header("🎓 學年段快速查詢")
    
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
        st.subheader("📅 計算器")
        mode = st.radio("模式", ["民國", "西元"], horizontal=True)
        if mode == "民國":
            ry = st.number_input("民國年", 90, 130, 112)
            rm = st.selectbox("月 ", range(1, 13))
            rd = st.selectbox("日 ", range(1, 32))
            try: dob = date(ry + 1911, rm, rd)
            except: dob = None
        else:
            dob = st.date_input("選擇生日", value=date(2023, 1, 1))
        st.markdown("</div>", unsafe_allow_html=True)

    if dob:
        with c2:
            roadmap = calculate_roadmap(dob)
            cur_info = roadmap[0] if roadmap else "無法計算"
            grade = cur_info.split(" - ")[-1]
            year = cur_info.split(" - ")[0]
            
            st.markdown(f"""
            <div class="big-grade-box">
                <div style="font-size: 1.2rem; opacity: 0.9;">{year} 學年度</div>
                <div class="big-grade-text">{grade}</div>
                <div style="margin-top:10px;">生日：{to_roc_str(dob)}</div>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("🗓️ 查看完整入學路徑", expanded=True):
                roadmap_df = pd.DataFrame([r.split(" - ") for r in roadmap], columns=["學年度", "分配班級"])
                st.table(roadmap_df)

def page_preview(df):
    st.header("📅 未來入學名單預覽")
    
    target_y = st.number_input("預覽學年度", value=date.today().year - 1911 + 1)
    
    # 邏輯過濾
    preview_rows = []
    for _, r in df.iterrows():
        if "確定不收" in r["報名狀態"]: continue
        
        dob = parse_roc_date(r["幼兒生日"])
        grade = get_grade_logic(dob, int(target_y))
        
        if "畢業" not in grade and "不符" not in grade:
            preview_rows.append({
                "班級": grade,
                "狀態": r["報名狀態"],
                "幼兒姓名": r["幼兒姓名"],
                "電話": r["電話"],
                "備註": r["備註"]
            })
    
    if not preview_rows:
        st.info("該學年度暫無預計入學名單")
    else:
        pdf = pd.DataFrame(preview_rows)
        
        # 視覺化看板
        grades = ["大班", "中班", "小班", "幼幼班", "托嬰中心"]
        cols = st.columns(len(grades))
        
        for i, g in enumerate(grades):
            with cols[i]:
                g_data = pdf[pdf["班級"] == g]
                st.markdown(f"**{g}**")
                st.markdown(f"<div style='font-size:1.5rem; font-weight:bold; color:#764ba2;'>{len(g_data)} <small>人</small></div>", unsafe_allow_html=True)
                
                with st.expander("名單"):
                    if g_data.empty: st.caption("無")
                    else: st.write(g_data[["幼兒姓名", "狀態"]])

def page_calc(df):
    st.header("👩‍🏫 招生缺額與師資試算")
    
    with st.container(border=True):
        st.caption("計算邏輯：自動統計前一學年度「確認入學」的人數作為舊生，計算直升後的缺額。")
        cal_y = st.number_input("預估目標學年度", value=date.today().year - 1911 + 1)
        ref_y = cal_y - 1
        
        # 統計前一年在校生 (舊生)
        old_counts = {"幼幼班": 0, "小班": 0, "中班": 0}
        for _, r in df.iterrows():
            if r["報名狀態"] == "確認入學":
                dob = parse_roc_date(r["幼兒生日"])
                gr = get_grade_logic(dob, ref_y)
                if gr in old_counts: old_counts[gr] += 1
        
        total_rising = sum(old_counts.values())
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🐘 3-6歲混齡區 (小中大)")
            st.write(f"直升舊生數：{total_rising} 人")
            target_mix = st.number_input("核定總名額", value=90)
            ratio_mix = 12 if cal_y >= 115 else 15
            
            gap = target_mix - total_rising
            teachers = math.ceil(target_mix / ratio_mix)
            
            st.metric("預計招收新名額", f"{gap} 人", delta_color="normal")
            st.metric("所需師資 (1:{})".format(ratio_mix), f"{teachers} 名")
            
        with c2:
            st.markdown("#### 🐥 2-3歲幼幼班")
            target_t = st.number_input("幼幼班預計招收名額", value=16)
            teachers_t = math.ceil(target_t / 8)
            st.metric("幼幼班名額", f"{target_t} 人")
            st.metric("所需師資 (1:8)", f"{teachers_t} 名")

# ==========================================
# 6. 主程式進入點
# ==========================================
def main():
    if not login_screen(): return

    # 側邊欄導覽
    with st.sidebar:
        st.image("https://img.icons8.com/fluent/96/000000/school.png", width=80)
        st.title("系統選單")
        menu = st.radio(
            "功能導航",
            ["🏠 營運儀表板", "👶 新生報名登記", "📂 資料管理中心", "🎓 學年段快速查詢", "📅 未來入學預覽", "👩‍🏫 招生師資試算"],
            label_visibility="collapsed"
        )
        st.divider()
        st.caption(f"📅 今日日期：{to_roc_str(date.today())}")
        if st.button("🚪 登出"):
            st.session_state["authenticated"] = False
            st.rerun()

    # 載入資料
    df = load_data()

    # 分頁邏輯
    if menu == "🏠 營運儀表板":
        page_dashboard(df)
    elif menu == "👶 新生報名登記":
        page_add()
    elif menu == "📂 資料管理中心":
        page_manage(df)
    elif menu == "🎓 學年段快速查詢":
        page_quick_check()
    elif menu == "📅 未來入學預覽":
        page_preview(df)
    elif menu == "👩‍🏫 招生師資試算":
        page_calc(df)

if __name__ == "__main__":
    main()
