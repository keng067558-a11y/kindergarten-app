import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, datetime
import os

# ==========================================
# 0. 系統環境配置與樣式
# ==========================================
st.set_page_config(
    page_title="幼兒園雲端招生管理系統",
    layout="wide",
    page_icon="🏫"
)

# 套用現代化 CSS 樣式
st.markdown("""
<style>
    /* 主標題樣式 */
    .main-header { font-size: 2.5rem; font-weight: 800; color: #1E3A8A; margin-bottom: 0.5rem; }
    .sub-text { color: #64748b; margin-bottom: 2rem; }
    
    /* 統計卡片樣式 */
    .metric-container { background-color: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; }
    
    /* 按鈕樣式優化 */
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; }
    
    /* 表格編輯器標籤色彩 (示意) */
    [data-testid="stDataEditor"] { border-radius: 10px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
</style>
""", unsafe_allow_html=True)

LOCAL_FILE = "kindergarten_local_data.csv"

# ==========================================
# 1. 核心邏輯：台灣學制班別推算
# ==========================================
def calculate_taiwan_grade(birth_date):
    """
    根據幼兒生日推算該學年度 9/1 入學時的班別
    2足歲：幼幼班 | 3足歲：小班 | 4足歲：中班 | 5足歲：大班
    """
    if pd.isna(birth_date) or not birth_date:
        return "資料不全"
    
    try:
        # 統一轉換為日期物件
        dob = pd.to_datetime(birth_date)
        today = date.today()
        
        # 決定目標基準年 (台灣開學為 9月)
        # 如果現在是 1~8月，目標是今年 9/1；如果是 9~12月，目標是明年 9/1
        ref_year = today.year if today.month < 9 else today.year + 1
        ref_date = datetime(ref_year, 9, 1)
        
        # 計算基準日當天的足歲 (邏輯：若生日還沒過，年份減一)
        age = ref_year - dob.year - ((ref_date.month, ref_date.day) < (dob.month, dob.day))
        
        if age < 2: return "未滿 2 歲"
        elif age == 2: return "幼幼班"
        elif age == 3: return "小班"
        elif age == 4: return "中班"
        elif age == 5: return "大班"
        else: return f"超齡({age}歲)"
    except:
        return "日期格式錯誤"

# ==========================================
# 2. 資料存取層 (Google Sheets 串接與備份)
# ==========================================
def load_system_data():
    """
    獲取資料邏輯：
    1. 嘗試連結 Google Sheets (透過 st.connection)
    2. 若失敗，則讀取本機 CSV 備份
    3. 自動校對管理欄位 (處理狀態、備註等)
    """
    df = pd.DataFrame()
    source_status = "Unknown"
    
    # 嘗試雲端同步
    try:
        # 需在 .streamlit/secrets.toml 中設定 [connections.gsheets]
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl="0") 
        source_status = "☁️ 雲端同步模式 (Google Sheets)"
    except Exception as e:
        source_status = "💾 本機作業模式 (無法連線雲端)"
        if os.path.exists(LOCAL_FILE):
            df = pd.read_csv(LOCAL_FILE)
        else:
            # 初始化全新結構
            df = pd.DataFrame(columns=["時間戳記", "幼兒姓名", "家長電話", "幼兒生日"])

    # 確保管理欄位存在 (這是我們在管理系統中手動擴展的欄位)
    admin_fields = {
        "處理狀態": "待處理",
        "重要性": "普通",
        "老師備註": ""
    }
    for col, default in admin_fields.items():
        if col not in df.columns:
            df[col] = default
            
    return df.fillna(""), source_status

def sync_data(df):
    """同時儲存至本機 CSV 並嘗試推送到雲端"""
    # 1. 存入本機確保資料不遺失
    df.to_csv(LOCAL_FILE, index=False, encoding="utf-8-sig")
    
    # 2. 嘗試推送至 Google Sheets
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        conn.update(data=df)
        return True, "雲端同步成功"
    except Exception as e:
        return False, f"已存入本機，但雲端失敗: {str(e)}"

# ==========================================
# 3. 主介面邏輯
# ==========================================
def main():
    # --- 權限驗證 ---
    if "auth" not in st.session_state:
        st.session_state.auth = False

    if not st.session_state.auth:
        st.markdown('<p class="main-header">🔐 幼兒園後台管理登入</p>', unsafe_allow_html=True)
        login_col, _ = st.columns([1, 2])
        with login_col:
            password = st.text_input("輸入管理密碼", type="password")
            if st.button("確認進入"):
                if password == st.secrets.get("password", "admin123"):
                    st.session_state.auth = True
                    st.rerun()
                else:
                    st.error("密碼錯誤，請重新輸入")
        return

    # --- 載入資料 ---
    df, status_msg = load_system_data()

    # --- 側邊欄 ---
    with st.sidebar:
        st.header("⚙️ 系統設定")
        st.info(f"當前狀態：\n{status_msg}")
        
        if st.button("🔄 刷新雲端資料"):
            st.cache_data.clear()
            st.rerun()
            
        st.divider()
        st.write("📊 快速工具")
        # 匯出 CSV 按鈕
        csv_data = df.to_csv(index=False).encode('utf_8_sig')
        st.download_button("📥 下載完整資料表 (CSV)", csv_data, f"kinder_export_{date.today()}.csv")
        
        if st.button("🚪 安全登出"):
            st.session_state.auth = False
            st.rerun()

    # --- 主內容區域 ---
    st.markdown('<div class="main-header">🏫 幼兒園雲端招生管理系統</div>', unsafe_allow_html=True)
    st.markdown('<p class="sub-text">本系統直接連動 Google 表單，您可以即時追蹤並管理所有新生登記狀況。</p>', unsafe_allow_html=True)

    # 1. 摘要統計看板
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("總登記人數", len(df))
    with m2:
        new_leads = len(df[df["處理狀態"] == "待處理"])
        st.metric("待處理名單", new_leads, delta=f"{new_leads} 筆", delta_color="inverse")
    with m3:
        confirmed = len(df[df["處理狀態"] == "確認入學"])
        st.metric("已確認入學", confirmed)
    with m4:
        # 簡單計算今日新增
        today_str = date.today().strftime("%Y-%m-%d")
        new_today = len(df[df.iloc[:, 0].astype(str).str.contains(today_str, na=False)])
        st.metric("今日新增", new_today)

    st.divider()

    # 2. 進階搜尋與過濾
    col_search, col_filter = st.columns([2, 1])
    with col_search:
        search_q = st.text_input("🔍 關鍵字搜尋 (幼兒姓名、家長電話、備註)", placeholder="輸入關鍵字...")
    with col_filter:
        status_filter = st.multiselect("處理狀態過濾", options=df["處理狀態"].unique().tolist())

    # 執行過濾邏輯
    display_df = df.copy()
    if search_q:
        search_mask = display_df.astype(str).apply(lambda x: x.str.contains(search_q)).any(axis=1)
        display_df = display_df[search_mask]
    if status_filter:
        display_df = display_df[display_df["處理狀態"].isin(status_filter)]

    # 自動推算班別 (用於顯示)
    if "幼兒生日" in display_df.columns:
        display_df["系統推算班別"] = display_df["幼兒生日"].apply(calculate_taiwan_grade)

    # 3. 核心資料編輯區 (Data Editor)
    st.subheader("📋 報名資料編修中心")
    st.caption("您可以直接修改「處理狀態」、「重要性」或「備註」，系統將自動同步。")

    # 配置欄位屬性
    column_config = {
        "時間戳記": st.column_config.TextColumn("報名時間", disabled=True),
        "幼兒姓名": st.column_config.TextColumn("幼兒姓名", width="medium"),
        "幼兒生日": st.column_config.DateColumn("幼兒生日"),
        "系統推算班別": st.column_config.TextColumn("預計入學班別", disabled=True),
        "處理狀態": st.column_config.SelectboxColumn(
            "處理狀態",
            options=["待處理", "聯繫中", "預約參觀", "已面談", "候補中", "確認入學", "取消報名"],
            required=True
        ),
        "重要性": st.column_config.SelectboxColumn(
            "重要性",
            options=["⭐⭐⭐ (高)", "⭐⭐ (中)", "⭐ (低)", "普通"]
        ),
        "老師備註": st.column_config.TextColumn("老師專用備註", width="large")
    }

    # 渲染編輯器
    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config=column_config
    )

    # 4. 同步按鈕
    st.divider()
    col_save, _ = st.columns([1, 4])
    with col_save:
        if st.button("💾 儲存並同步至雲端", type="primary", use_container_width=True):
            with st.spinner("同步至 Google Sheets 中..."):
                # 注意：在大型系統中，應將編輯後的資料合併回原始 DF 再存檔
                success, msg = sync_data(edited_df)
                if success:
                    st.success("✅ 資料已成功更新回雲端！")
                    st.balloons()
                else:
                    st.warning(msg)

if __name__ == "__main__":
    main()
