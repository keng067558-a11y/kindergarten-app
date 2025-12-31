import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, datetime

# ==========================================
# 0. 系統環境設定
# ==========================================
st.set_page_config(page_title="幼兒園雲端管理系統", layout="wide", page_icon="🏫")

# 自定義 CSS 美化
st.markdown("""
<style>
    .main-title { font-size: 2.5rem; font-weight: 800; color: #1E3A8A; margin-bottom: 1rem; }
    .stMetric { background-color: #F0F9FF; padding: 15px; border-radius: 10px; border: 1px solid #BAE6FD; }
    .save-button { background-color: #059669 !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 核心邏輯函式 (學號與年齡推算)
# ==========================================

def get_grade_calculation(birth_date_str):
    """根據生日推算 9/1 入學後的班別"""
    try:
        if not birth_date_str: return "未知"
        # 處理多種日期格式
        dob = pd.to_datetime(birth_date_str)
        today = date.today()
        # 設定目標學年度 (若現在是 5月，目標就是當年度 9月；若已過 9月，目標是明年 9月)
        target_year = today.year if today.month < 9 else today.year + 1
        
        # 計算到該年 9/1 的足歲
        ref_date = datetime(target_year, 9, 1)
        age = ref_date.year - dob.year - ((ref_date.month, ref_date.day) < (dob.month, dob.day))
        
        if age < 2: return "未足齡"
        elif age == 2: return "幼幼班"
        elif age == 3: return "小班"
        elif age == 4: return "中班"
        elif age == 5: return "大班"
        else: return "國小以上"
    except:
        return "格式錯誤"

# ==========================================
# 2. Google Sheets 連線與資料處理
# ==========================================

# 初始化 Google Sheets 連線
# 注意：需在 .streamlit/secrets.toml 中設定憑證
conn = st.connection("gsheets", type=GSheetsConnection)

def fetch_data():
    """從雲端讀取資料"""
    # ttl=0 確保每次重新整理都是抓最新的
    df = conn.read(ttl="0")
    
    # 確保必要管理欄位存在 (如果 Sheet 裡沒有，系統自動補齊)
    admin_cols = ["處理狀態", "老師備註", "重要性"]
    for col in admin_cols:
        if col not in df.columns:
            df[col] = "待處理" if col == "處理狀態" else ""
            if col == "重要性": df[col] = "普通"
            
    return df

# ==========================================
# 3. 系統 UI 介面
# ==========================================

def main():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # 簡易登入介面
    if not st.session_state.authenticated:
        st.markdown('<p class="main-title">🔐 幼兒園後台管理</p>', unsafe_allow_html=True)
        pwd = st.text_input("請輸入管理員密碼", type="password")
        if st.button("登入"):
            if pwd == st.secrets.get("password", "admin123"):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("密碼錯誤")
        return

    # --- 進入系統主介面 ---
    st.sidebar.markdown("### 🏫 系統控制台")
    if st.sidebar.button("🔄 重新整理雲端資料"):
        st.cache_data.clear()
        st.rerun()

    st.markdown('<p class="main-title">🏫 雲端招生管理看板</p>', unsafe_allow_html=True)
    
    # 1. 讀取資料
    try:
        raw_df = fetch_data()
    except Exception as e:
        st.error(f"無法連線至 Google Sheets: {e}")
        st.info("請檢查 secrets.toml 中的 Google Service Account 憑證與試算表網址是否正確。")
        return

    # 2. 數據統計摘要 (Dashboard)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("總報名數", len(raw_df))
    with col2:
        new_leads = len(raw_df[raw_df["處理狀態"] == "待處理"])
        st.metric("待處理名單", new_leads, delta=f"{new_leads} 筆", delta_color="inverse")
    with col3:
        confirmed = len(raw_df[raw_df["處理狀態"] == "確認入學"])
        st.metric("已確認人數", confirmed)
    with col4:
        # 自動計算本學期預計入學班別
        st.caption("自動推算班別")
        if "幼兒生日" in raw_df.columns:
            raw_df["預計班別"] = raw_df["幼兒生日"].apply(get_grade_calculation)
        st.write("計算中...")

    st.divider()

    # 3. 進階搜尋與過濾
    with st.expander("🔍 搜尋與篩選條件"):
        s_col1, s_col2 = st.columns(2)
        with s_col1:
            search_name = st.text_input("搜尋幼兒或家長姓名")
        with s_col2:
            filter_status = st.multiselect("過濾處理狀態", options=raw_df["處理狀態"].unique().tolist())
    
    # 應用篩選
    display_df = raw_df.copy()
    if search_name:
        # 假設欄位名稱為 "幼兒姓名" 或 "家長姓名"
        search_mask = display_df.astype(str).apply(lambda x: x.str.contains(search_name)).any(axis=1)
        display_df = display_df[search_mask]
    if filter_status:
        display_df = display_df[display_df["處理狀態"].isin(filter_status)]

    # 4. 核心管理編輯器 (Data Editor)
    st.subheader("📋 報名名單管理")
    st.info("💡 提示：您可以直接在下方表格修改「處理狀態」或「老師備註」，修改後請點擊下方儲存按鈕。")

    # 使用 data_editor 進行雙向同步
    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "時間戳記": st.column_config.DatetimeColumn("報名時間", disabled=True),
            "處理狀態": st.column_config.SelectboxColumn(
                "處理狀態",
                options=["待處理", "聯繫中", "預約參觀", "候補中", "確認入學", "取消報名"],
                required=True
            ),
            "重要性": st.column_config.SelectboxColumn(
                options=["⭐⭐⭐", "⭐⭐", "⭐", "普通"],
            ),
            "幼兒生日": st.column_config.DateColumn("幼兒生日"),
            "預計班別": st.column_config.TextColumn("系統推算班別", disabled=True),
            "老師備註": st.column_config.TextColumn("老師備註", width="large")
        }
    )

    # 5. 儲存按鈕
    if st.button("💾 將變更同步至 Google Sheets", type="primary", use_container_width=True):
        with st.spinner("正在同步雲端資料..."):
            try:
                # 更新回雲端
                conn.update(data=edited_df)
                st.success("🎉 同步成功！雲端試算表已更新。")
                st.balloons()
            except Exception as e:
                st.error(f"同步失敗: {e}")

    # 6. 下載備份
    st.sidebar.divider()
    csv = edited_df.to_csv(index=False).encode('utf_8_sig')
    st.sidebar.download_button("📥 下載目前名單(Excel格式)", csv, "kindergarten_export.csv", "text/csv")

if __name__ == "__main__":
    main()
