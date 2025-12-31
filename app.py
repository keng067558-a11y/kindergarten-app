import streamlit as st
import pandas as pd
from datetime import datetime, date
import time

# ==========================================
# 0. 系統基本配置
# ==========================================
st.set_page_config(
    page_title="幼兒園招生管理系統",
    page_icon="🏫",
    layout="wide"
)

# 套用蘋果風格的極簡 CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&display=swap');
    
    .main { background-color: #F2F2F7; }
    
    /* 全域字體優化 */
    html, body, [class*="css"]  {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang TC", "Noto Sans TC", sans-serif !important;
    }

    /* 按鈕樣式 */
    .stButton>button {
        border-radius: 14px;
        font-weight: 700;
        transition: all 0.2s;
        border: none;
        padding: 0.5rem 1rem;
    }
    
    /* 統計卡片樣式 */
    [data-testid="stMetricValue"] {
        font-family: "SF Pro Text", "Tabular-nums" !important;
        font-weight: 900 !important;
        letter-spacing: -1px;
    }
    
    .stMetric {
        background-color: white;
        padding: 24px;
        border-radius: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
        border: 1px solid rgba(0,0,0,0.05);
    }
    
    /* 表格編輯器圓角 */
    div[data-testid="stDataEditor"] {
        border-radius: 24px !important;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    }
    
    /* 側邊欄設計 */
    .css-164782u {
        background-color: white;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 資料存取層 (目前使用記憶體模式)
# ==========================================

# 初始化模擬資料庫 (Session State)
if 'students_db' not in st.session_state:
    # 預設一些範例資料
    st.session_state.students_db = pd.DataFrame(columns=[
        "時間戳記", "幼兒姓名", "家長電話", "幼兒生日", "家長姓名", "處理狀態", "老師備註"
    ])

def fetch_data():
    """未來這裡會改為讀取 Google Sheets"""
    return st.session_state.students_db

def save_data(df):
    """未來這裡會將資料存回 Google Sheets"""
    st.session_state.students_db = df
    return True

# ==========================================
# 2. 核心邏輯：台灣學制班別推算
# ==========================================
def calculate_grade(birthday_str):
    if not birthday_str or "/" not in str(birthday_str):
        return "資料待補"
    try:
        parts = str(birthday_str).split('/')
        roc_year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        ce_year = roc_year + 1911
        
        today = date.today()
        # 目標學年度 (以 9/1 為準)
        target_year = today.year if today.month < 9 else today.year + 1
        
        # 計算基準日當天的足歲
        age = target_year - ce_year
        if month > 9 or (month == 9 and day >= 2):
            age -= 1
            
        if age < 2: return "未滿2歲"
        if age == 2: return "幼幼班"
        if age == 3: return "小班"
        if age == 4: return "中班"
        if age == 5: return "大班"
        return f"超齡({age}歲)"
    except:
        return "格式錯誤"

# ==========================================
# 3. 主介面 UI
# ==========================================
def main():
    # 頂部導覽列
    col_t, col_r = st.columns([4, 1])
    with col_t:
        st.title("🏫 招生管理中心")
        st.caption("目前運行模式：本地預覽 (資料重整後將重置)")
    with col_r:
        if st.button("🔄 刷新頁面", use_container_width=True):
            st.rerun()

    # 載入資料
    df = fetch_data()

    # A. 數據統計區 (Apple Style)
    m1, m2, m3, m4 = st.columns(4)
    total_count = len(df)
    m1.metric("總登記人數", total_count)
    m2.metric("待處理", len(df[df['處理狀態'] == '待處理']))
    m3.metric("確認入學", len(df[df['處理狀態'] == '確認入學']))
    m4.metric("系統狀態", "運行中", delta="良好")

    st.divider()

    # B. 搜尋與篩選
    col_q, col_s = st.columns([3, 1])
    with col_q:
        query_str = st.text_input("🔍 搜尋名單", placeholder="輸入幼兒姓名、電話或備註內容...")
    with col_s:
        status_options = ["全部"] + list(df['處理狀態'].unique()) if not df.empty else ["全部"]
        status_filter = st.selectbox("狀態篩選", status_options)

    # 執行過濾
    display_df = df.copy()
    if query_str:
        mask = display_df.astype(str).apply(lambda x: x.str.contains(query_str, case=False)).any(axis=1)
        display_df = display_df[mask]
    if status_filter != "全部":
        display_df = display_df[display_df['處理狀態'] == status_filter]

    # C. 名單列表區
    if df.empty:
        st.info("👋 歡迎使用！目前名單是空的，請從左側邊欄新增第一筆資料。")
    else:
        st.subheader("📋 招生名單明細")
        
        # 顯示時動態推算班別
        render_df = display_df.copy()
        render_df['預計分班'] = render_df['幼兒生日'].apply(calculate_grade)
        
        # 表格編輯器
        updated_df = st.data_editor(
            render_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "時間戳記": st.column_config.TextColumn("登記時間", disabled=True),
                "幼兒姓名": st.column_config.TextColumn("姓名", required=True),
                "預計分班": st.column_config.TextColumn("推算結果", disabled=True),
                "處理狀態": st.column_config.SelectboxColumn(
                    "目前進度", 
                    options=["待處理", "預約參觀", "候補中", "確認入學", "取消報名"],
                    required=True
                ),
                "老師備註": st.column_config.TextColumn("詳細備註", width="large")
            }
        )

        # 儲存按鈕
        if st.button("💾 儲存所有變更", type="primary"):
            # 移除僅顯示用的欄位
            final_df = updated_df.drop(columns=['預計分班'])
            save_data(final_df)
            st.success("✅ 資料已成功更新！")
            time.sleep(0.5)
            st.rerun()

    # D. 側邊欄：新增登記
    with st.sidebar:
        st.header("✨ 新增新生登記")
        with st.form("add_new_student", clear_on_submit=True):
            n_name = st.text_input("幼兒姓名*")
            n_phone = st.text_input("家長電話*")
            n_birth = st.text_input("民國生日", placeholder="110/05/20")
            n_parent = st.text_input("家長姓名")
            n_note = st.text_area("初始備註")
            
            submitted = st.form_submit_button("立即新增資料", type="primary", use_container_width=True)
            
            if submitted:
                if n_name and n_phone:
                    new_row = {
                        "時間戳記": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
                        "幼兒姓名": n_name,
                        "家長電話": n_phone,
                        "幼兒生日": n_birth,
                        "家長姓名": n_parent,
                        "處理狀態": "待處理",
                        "老師備註": n_note
                    }
                    # 更新至 Session State
                    st.session_state.students_db = pd.concat([st.session_state.students_db, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"🎉 {n_name} 已成功加入名單")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("姓名與電話不能空白")

        st.divider()
        st.caption("☁️ 未來連動 Google Sheets 後，此處資料將會永久保存於您的雲端硬碟中。")

if __name__ == "__main__":
    main()
