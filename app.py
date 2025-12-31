import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, datetime
import os

# ==========================================
# 0. 系統核心設定
# ==========================================
st.set_page_config(page_title="幼兒園管理系統 2.0", layout="wide", page_icon="📝")

# 系統樣式
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E40AF; margin-bottom: 20px; }
    .status-card { padding: 20px; border-radius: 12px; background-color: #F8FAFC; border: 1px solid #E2E8F0; }
    .stButton>button { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

LOCAL_FILE = "local_backup.csv"

# ==========================================
# 1. 核心邏輯：班別推算
# ==========================================
def calculate_grade(birth_date):
    """根據生日推算 9/1 入學班別 (台灣學制)"""
    if pd.isna(birth_date) or not birth_date:
        return "資料不全"
    try:
        dob = pd.to_datetime(birth_date)
        today = date.today()
        # 計算基準年 (今年 8月以前入學看今年，9月以後入學看明年)
        ref_year = today.year if today.month < 9 else today.year + 1
        ref_date = datetime(ref_year, 9, 1)
        
        # 足歲計算
        age = ref_year - dob.year - ((ref_date.month, ref_date.day) < (dob.month, dob.day))
        
        mapping = {2: "幼幼班", 3: "小班", 4: "中班", 5: "大班"}
        if age < 2: return "未足齡"
        return mapping.get(age, f"超齡({age}歲)")
    except:
        return "日期錯誤"

# ==========================================
# 2. 資料存取層 (Google Sheets + Local Backup)
# ==========================================
def get_data():
    """獲取資料：嘗試雲端，失敗則抓取本機 CSV"""
    df = pd.DataFrame()
    mode = "Cloud"
    
    # 1. 嘗試雲端連線
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl="0")
        st.session_state["mode"] = "☁️ 雲端同步模式"
    except Exception as e:
        mode = "Local"
        st.session_state["mode"] = "💾 本機作業模式 (雲端未連線)"
        if os.path.exists(LOCAL_FILE):
            df = pd.read_csv(LOCAL_FILE)
        else:
            # 建立空資料表
            df = pd.DataFrame(columns=["時間戳記", "幼兒姓名", "家長電話", "幼兒生日", "處理狀態", "老師備註"])

    # 2. 確保必要欄位
    required = ["處理狀態", "老師備註", "重要性"]
    for col in required:
        if col not in df.columns:
            df[col] = "待處理" if col == "處理狀態" else ("普通" if col == "重要性" else "")
            
    return df.fillna("")

def save_data(df):
    """存檔：同時儲存至本機並嘗試同步雲端"""
    # 儲存本機備份
    df.to_csv(LOCAL_FILE, index=False, encoding="utf-8-sig")
    
    # 嘗試同步雲端
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        conn.update(data=df)
        return True, "同步成功"
    except Exception as e:
        return False, str(e)

# ==========================================
# 3. 主介面
# ==========================================
def main():
    st.markdown('<div class="main-header">🏫 幼兒園管理系統 2.0</div>', unsafe_allow_html=True)

    # --- 登入檢查 ---
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        col1, _ = st.columns([1, 2])
        with col1:
            pw = st.text_input("請輸入系統密碼", type="password")
            if st.button("進入系統"):
                if pw == st.secrets.get("password", "admin"):
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("密碼錯誤")
        return

    # --- 側邊欄：診斷與設定 ---
    with st.sidebar:
        st.header("🛠️ 系統狀態")
        df = get_data()
        st.success(st.session_state.get("mode", "初始化中"))
        
        if st.button("🔄 重新載入雲端資料"):
            st.cache_data.clear()
            st.rerun()
            
        st.divider()
        st.info("💡 操作說明：直接在下方表格修改資料，改完後點擊最下方的『儲存』按鈕即可更新雲端試算表。")

    # --- 資料摘要 ---
    c1, c2, c3 = st.columns(3)
    c1.metric("總登記人數", len(df))
    c2.metric("待處理", len(df[df["處理狀態"] == "待處理"]))
    c3.metric("本週新增", 0) # 暫留功能

    # --- 搜尋功能 ---
    search = st.text_input("🔍 搜尋姓名或電話", "")
    if search:
        df_display = df[df.astype(str).apply(lambda x: x.str.contains(search)).any(axis=1)]
    else:
        df_display = df

    # --- 自動班別推算 ---
    if "幼兒生日" in df_display.columns:
        df_display["系統推算班別"] = df_display["幼兒生日"].apply(calculate_grade)

    # --- 核心編輯器 ---
    st.subheader("📋 報名清單編修")
    
    # 配置欄位樣式
    config = {
        "處理狀態": st.column_config.SelectboxColumn(
            options=["待處理", "聯繫中", "預約參觀", "候補中", "確認入學", "取消報名"],
            required=True
        ),
        "重要性": st.column_config.SelectboxColumn(options=["⭐⭐⭐", "⭐⭐", "⭐", "普通"]),
        "老師備註": st.column_config.TextColumn(width="large"),
        "系統推算班別": st.column_config.TextColumn(disabled=True),
        "時間戳記": st.column_config.TextColumn(disabled=True)
    }

    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config=config
    )

    # --- 儲存功能 ---
    st.divider()
    save_col, _ = st.columns([1, 4])
    with save_col:
        if st.button("💾 儲存並同步至雲端", type="primary", use_container_width=True):
            with st.spinner("同步中..."):
                # 將編輯過的資料合併回主資料表 (此處簡化處理，直接儲存編輯後的內容)
                success, msg = save_data(edited_df)
                if success:
                    st.success("存檔成功！")
                    st.balloons()
                else:
                    st.warning(f"本機已存檔，但雲端同步失敗 (原因: {msg})")

if __name__ == "__main__":
    main()
