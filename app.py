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
    .status-box { padding: 10px; border-radius: 5px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 核心邏輯函式 (學號與年齡推算)
# ==========================================

def get_grade_calculation(birth_date_str):
    """根據生日推算 9/1 入學後的班別"""
    try:
        if pd.isna(birth_date_str) or not birth_date_str: return "資料遺失"
        # 轉換為日期格式
        dob = pd.to_datetime(birth_date_str)
        today = date.today()
        
        # 判斷目標學年度：現在若是 1-8 月，目標是今年 9 月入學；若是 9-12 月，目標是明年 9 月
        target_year = today.year if today.month < 9 else today.year + 1
        ref_date = datetime(target_year, 9, 1)
        
        # 足歲計算
        age = ref_date.year - dob.year - ((ref_date.month, ref_date.day) < (dob.month, dob.day))
        
        if age < 2: return "未足齡"
        elif age == 2: return "幼幼班"
        elif age == 3: return "小班"
        elif age == 4: return "中班"
        elif age == 5: return "大班"
        else: return f"超齡({age}歲)"
    except Exception:
        return "格式錯誤"

# ==========================================
# 2. Google Sheets 連線與資料處理
# ==========================================

# 建立連線物件
conn = st.connection("gsheets", type=GSheetsConnection)

def fetch_data():
    """從雲端讀取資料並確保管理欄位存在"""
    # ttl="0" 確保資料即時性
    df = conn.read(ttl="0")
    
    # 確保原始資料不為空
    if df.empty:
        return pd.DataFrame()

    # 清洗欄位：去除前後空白
    df.columns = [c.strip() for c in df.columns]

    # 自動補齊管理用的必要欄位
    admin_fields = {
        "處理狀態": "待處理",
        "老師備註": "",
        "重要性": "普通"
    }
    
    for col, default_val in admin_fields.items():
        if col not in df.columns:
            df[col] = default_val
            
    # 移除全空的列
    df = df.dropna(how='all')
    return df

# ==========================================
# 3. 系統 UI 介面
# ==========================================

def main():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # --- 登入介面 ---
    if not st.session_state.authenticated:
        st.markdown('<p class="main-title">🔐 幼兒園雲端後台登入</p>', unsafe_allow_html=True)
        col_l, col_r = st.columns([1, 2])
        with col_l:
            pwd = st.text_input("管理員密碼", type="password")
            if st.button("確認進入", use_container_width=True):
                if pwd == st.secrets.get("password", "admin123"):
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("密碼錯誤，請重新輸入")
        return

    # --- 側邊欄設定 ---
    with st.sidebar:
        st.header("⚙️ 系統設定")
        if st.button("🔄 刷新雲端資料"):
            st.cache_data.clear()
            st.rerun()
        
        st.divider()
        st.markdown("### 🔑 連線檢索")
        try:
            # 顯示服務帳號供使用者去 Google Sheet 共用
            s_account = st.secrets["connections"]["gsheets"]["client_email"]
            st.caption("請確保已將試算表共用給：")
            st.code(s_account, language="text")
        except:
            st.warning("尚未設定 secrets.toml 憑證")

    st.markdown('<p class="main-title">🏫 新生入學管理看板</p>', unsafe_allow_html=True)
    
    # --- 1. 讀取與處理資料 ---
    try:
        raw_df = fetch_data()
        if raw_df.empty:
            st.warning("目前試算表中尚無資料。請檢查 Google 表單是否有回覆。")
            return
    except Exception as e:
        st.error(f"❌ 連線失敗：{e}")
        st.info("常見原因：1. 試算表網址錯誤 2. 憑證權限不足 3. 欄位名稱衝突")
        return

    # --- 2. 數據統計 Dashboard ---
    # 預先計算班別
    if "幼兒生日" in raw_df.columns:
        raw_df["系統推算班別"] = raw_df["幼兒生日"].apply(get_grade_calculation)
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("總登記人數", len(raw_df))
    with c2: 
        pending = len(raw_df[raw_df["處理狀態"] == "待處理"])
        st.metric("待處理名單", pending, delta=f"{pending} 筆", delta_color="inverse")
    with c3:
        confirmed = len(raw_df[raw_df["處理狀態"] == "確認入學"])
        st.metric("已確認入學", confirmed)
    with c4:
        st.metric("今日新增", len(raw_df[raw_df.iloc[:, 0].astype(str).str.contains(date.today().strftime('%Y/%m/%d'), na=False)]))

    st.divider()

    # --- 3. 管理工具與搜尋 ---
    with st.expander("🔍 進階搜尋與過濾選項"):
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            q = st.text_input("搜尋關鍵字 (姓名/電話/備註)")
        with sc2:
            st_filter = st.multiselect("處理狀態過濾", options=raw_df["處理狀態"].unique().tolist())
        with sc3:
            # 假設有班別欄位
            grade_options = raw_df["系統推算班別"].unique().tolist() if "系統推算班別" in raw_df.columns else []
            gr_filter = st.multiselect("班別過濾", options=grade_options)

    # 執行篩選邏輯
    filtered_df = raw_df.copy()
    if q:
        filtered_df = filtered_df[filtered_df.astype(str).apply(lambda x: x.str.contains(q)).any(axis=1)]
    if st_filter:
        filtered_df = filtered_df[filtered_df["處理狀態"].isin(st_filter)]
    if gr_filter:
        filtered_df = filtered_df[filtered_df["系統推算班別"].isin(gr_filter)]

    # --- 4. 資料編輯器 ---
    st.subheader("📋 資料明細編修")
    st.caption("可以直接在表格內修改，完成後請點擊下方「同步至雲端」按鈕")
    
    # 動態欄位設定
    col_config = {
        "處理狀態": st.column_config.SelectboxColumn(
            options=["待處理", "聯繫中", "預約參觀", "候補中", "確認入學", "取消報名"],
            required=True
        ),
        "重要性": st.column_config.SelectboxColumn(
            options=["⭐⭐⭐ (急)", "⭐⭐ (高)", "⭐ (中)", "普通"],
        ),
        "老師備註": st.column_config.TextColumn(width="large"),
        "系統推算班別": st.column_config.TextColumn(disabled=True)
    }
    
    # 如果有時間戳記欄位則禁用修改
    if "時間戳記" in filtered_df.columns:
        col_config["時間戳記"] = st.column_config.DatetimeColumn(disabled=True)

    edited_df = st.data_editor(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config=col_config
    )

    # --- 5. 同步與備份 ---
    col_save, col_empty = st.columns([1, 3])
    with col_save:
        if st.button("💾 同步變更至 Google Sheets", type="primary", use_container_width=True):
            with st.spinner("正在上傳資料..."):
                try:
                    # 這裡必須更新回原始 dataframe 的結構
                    conn.update(data=edited_df)
                    st.success("✅ 同步成功！")
                    st.balloons()
                except Exception as e:
                    st.error(f"儲存發生錯誤：{e}")

    # 下載功能放置於側邊欄底部
    csv = edited_df.to_csv(index=False).encode('utf_8_sig')
    st.sidebar.download_button("📥 匯出目前名單 (CSV)", csv, f"leads_{date.today()}.csv", "text/csv")

if __name__ == "__main__":
    main()
