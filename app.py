import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
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
    .main { background-color: #F2F2F7; }
    .stButton>button {
        border-radius: 12px;
        font-weight: 700;
        transition: all 0.2s;
    }
    .stMetric {
        background-color: white;
        padding: 20px;
        border-radius: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    div[data-testid="stExpander"] {
        border-radius: 20px !important;
        background-color: white;
        border: none !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
</style>
""", unsafe_allow_html=True)

# --- 1. 連線至 Google Sheets ---
SPREADSHEET_ID = '1ZofZnB8Btig_6XvsHGh7bbapnfJM-vDkXTFpaU7ngmE'

def get_gspread_client():
    # 這裡建議使用 Streamlit Secrets 或是讀取本地 json
    # 為了方便您測試，這裡假設您有名為 credentials.json 的金鑰檔案
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        return gspread.authorize(creds)
    except:
        st.error("❌ 找不到 credentials.json 金鑰檔案，請確認檔案已上傳至專案目錄。")
        return None

def fetch_data():
    client = get_gspread_client()
    if not client: return pd.DataFrame()
    sheet = client.open_by_key(SPREADSHEET_ID).get_sheets()[0]
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# --- 2. 班別計算邏輯 (台灣學制 9/1 分界) ---
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

# --- 3. 主介面邏輯 ---
def main():
    st.title("🏫 招生管理中心")
    st.caption("連動 Google Sheets 直接儲存模式")

    # 載入資料
    df = fetch_data()

    if df.empty:
        st.info("目前試算表中尚無資料，請先新增第一筆。")
    else:
        # A. 數據統計區
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("總登記人數", len(df))
        m2.metric("待處理", len(df[df['處理狀態'] == '待處理']))
        m3.metric("已確認入學", len(df[df['處理狀態'] == '確認入學']))
        m4.metric("今日進度", "同步中", delta="穩定")

        st.divider()

        # B. 搜尋與過濾
        col_q, col_s = st.columns([3, 1])
        with col_q:
            query = st.text_input("🔍 搜尋姓名、電話或備註...", placeholder="輸入關鍵字")
        with col_s:
            status_filter = st.selectbox("狀態過濾", ["全部"] + list(df['處理狀態'].unique()))

        # 執行過濾
        filtered_df = df.copy()
        if query:
            mask = filtered_df.astype(str).apply(lambda x: x.str.contains(query)).any(axis=1)
            filtered_df = filtered_df[mask]
        if status_filter != "全部":
            filtered_df = filtered_df[filtered_df['處理狀態'] == status_filter]

        # 計算班別 (顯示用)
        filtered_df['預計分班'] = filtered_df['幼兒生日'].apply(calculate_grade)

        # C. 名單列表區
        st.subheader("📋 招生名單明細")
        
        # 使用 Streamlit Data Editor 讓使用者可以點擊修改
        edited_df = st.data_editor(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "幼兒姓名": st.column_config.TextColumn("姓名", required=True),
                "家長電話": st.column_config.TextColumn("電話"),
                "處理狀態": st.column_config.SelectboxColumn("狀態", options=["待處理", "預約參觀", "確認入學", "候補中", "取消"]),
                "老師備註": st.column_config.TextColumn("招生備註", width="large")
            },
            disabled=["預計分班", "時間戳記"]
        )

    # D. 新增學生功能 (側邊欄)
    with st.sidebar:
        st.header("✨ 新增新生登記")
        with st.form("add_form", clear_on_submit=True):
            new_name = st.text_input("幼兒姓名*")
            new_phone = st.text_input("家長電話*")
            new_birth = st.text_input("民國生日 (例 110/05/20)")
            new_parent = st.text_input("家長稱呼")
            new_note = st.text_area("初始備註")
            
            submit = st.form_submit_button("立即寫入 Google Sheets", type="primary")
            
            if submit:
                if new_name and new_phone:
                    client = get_gspread_client()
                    sheet = client.open_by_key(SPREADSHEET_ID).get_sheets()[0]
                    
                    # 準備一列資料 (需對應您的 Excel 表頭順序)
                    # 假設表頭是: 時間戳記, 幼兒姓名, 家長電話, 幼兒生日, 家長姓名, 處理狀態, 老師備註
                    new_row = [
                        datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
                        new_name,
                        new_phone,
                        new_birth,
                        new_parent,
                        "待處理",
                        new_note
                    ]
                    
                    sheet.append_row(new_row)
                    st.success(f"✅ {new_name} 的資料已成功存入 Excel！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("姓名與電話為必填")

        st.divider()
        if st.button("🔄 重新整理資料"):
            st.rerun()

if __name__ == "__main__":
    main()
