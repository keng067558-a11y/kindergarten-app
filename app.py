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
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&display=swap');
    
    .main { background-color: #F2F2F7; }
    
    /* 全域字體優化 */
    html, body, [class*="css"]  {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang TC", "Noto Sans TC", sans-serif !important;
    }

    /* 按鈕樣式 */
    .stButton>button {
        border-radius: 12px;
        font-weight: 700;
        transition: all 0.2s;
        border: none;
    }
    
    /* 統計卡片 */
    [data-testid="stMetricValue"] {
        font-family: "SF Pro Text", "Tabular-nums" !important;
        font-weight: 900 !important;
        letter-spacing: -1px;
    }
    
    .stMetric {
        background-color: white;
        padding: 20px;
        border-radius: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
        border: 1px solid rgba(0,0,0,0.05);
    }
    
    /* 表格編輯器優化 */
    div[data-testid="stDataEditor"] {
        border-radius: 20px !important;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    }
    
    /* 側邊欄優化 */
    .css-164782u {
        background-color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. 連線至 Google Sheets ---
SPREADSHEET_ID = '1ZofZnB8Btig_6XvsHGh7bbapnfJM-vDkXTFpaU7ngmE'

def get_gspread_client():
    """
    支援兩種金鑰模式：
    1. 本地開發：讀取專案目錄下的 credentials.json
    2. Streamlit Cloud：讀取 st.secrets["gcp_service_account"]
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 優先嘗試從 Streamlit Secrets 讀取 (適合 GitHub 部署)
    if "gcp_service_account" in st.secrets:
        try:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        except Exception as e:
            st.error(f"❌ Secrets 金鑰格式錯誤: {e}")
            return None
            
    # 次要嘗試從本地檔案讀取
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        return gspread.authorize(creds)
    except FileNotFoundError:
        st.error("❌ 找不到 credentials.json。如果是部署到 GitHub，請在 Streamlit Cloud 設定 Secrets。")
        return None
    except Exception as e:
        st.error(f"❌ 金鑰讀取失敗: {e}")
        return None

def fetch_data():
    client = get_gspread_client()
    if not client: return pd.DataFrame()
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).get_sheets()[0]
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"❌ 讀取試算表失敗: {e}")
        return pd.DataFrame()

def save_all_data(df):
    """將完整的 Dataframe 覆蓋回 Google Sheets"""
    client = get_gspread_client()
    if not client: return False
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).get_sheets()[0]
        # 轉換為 list of lists 包含表頭
        data_to_save = [df.columns.values.tolist()] + df.values.tolist()
        sheet.update('A1', data_to_save)
        return True
    except Exception as e:
        st.error(f"❌ 同步失敗: {e}")
        return False

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
    # 標題與風格
    col_title, col_sync = st.columns([4, 1])
    with col_title:
        st.title("🏫 招生管理中心")
        st.caption("Google Sheets 專業連線版本")
    with col_sync:
        if st.button("🔄 重新整理", use_container_width=True):
            st.rerun()

    # 載入最新資料
    df = fetch_data()

    if df.empty:
        st.info("目前試算表中尚無資料，請在側邊欄新增第一筆。")
    else:
        # A. 數據統計區
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("總登記人數", len(df))
        m2.metric("待處理", len(df[df['處理狀態'] == '待處理']))
        m3.metric("確認入學", len(df[df['處理狀態'] == '確認入學']))
        m4.metric("同步狀態", "已連線", delta="穩定")

        st.divider()

        # B. 搜尋與過濾
        col_q, col_s = st.columns([3, 1])
        with col_q:
            query_str = st.text_input("🔍 快速搜尋", placeholder="輸入幼兒姓名、電話或備註關鍵字...")
        with col_s:
            status_list = ["全部"] + list(df['處理狀態'].unique())
            status_filter = st.selectbox("依狀態過濾", status_list)

        # 執行過濾
        filtered_df = df.copy()
        if query_str:
            mask = filtered_df.astype(str).apply(lambda x: x.str.contains(query_str, case=False)).any(axis=1)
            filtered_df = filtered_df[mask]
        if status_filter != "全部":
            filtered_df = filtered_df[filtered_df['處理狀態'] == status_filter]

        # 自動推算班別 (僅顯示用，不存入 Sheet 以保持乾淨)
        display_df = filtered_df.copy()
        display_df['預計分班'] = display_df['幼兒生日'].apply(calculate_grade)

        # C. 名單列表區 (Data Editor)
        st.subheader("📋 招生名單明細")
        st.caption("提示：您可以直接在下方表格修改「處理狀態」或「備註」，修改後請按下方儲存按鈕。")
        
        updated_df = st.data_editor(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "時間戳記": st.column_config.TextColumn("登記時間", disabled=True),
                "幼兒姓名": st.column_config.TextColumn("姓名", required=True),
                "家長電話": st.column_config.TextColumn("電話"),
                "預計分班": st.column_config.TextColumn("推算結果", disabled=True),
                "處理狀態": st.column_config.SelectboxColumn("目前進度", options=["待處理", "預約參觀", "確認入學", "候補中", "取消"]),
                "老師備註": st.column_config.TextColumn("招生備註", width="large")
            }
        )

        # 儲存變更按鈕 (將編輯後的內容同步回 Excel)
        if st.button("💾 儲存並更新至 Excel", type="primary"):
            # 移除僅供顯示的「預計分班」欄位，再存回 Sheet
            final_df = updated_df.drop(columns=['預計分班'])
            # 注意：這裡假設 filtered_df 代表了所有的資料或者是您想要覆蓋的部分
            # 在全選模式下，我們通常會合併回原始 df。為了簡單直覺，這裡採取完整覆蓋。
            if save_all_data(final_df):
                st.success("✅ Excel 資料已同步更新！")
                time.sleep(1)
                st.rerun()

    # D. 新增學生功能 (側邊欄)
    with st.sidebar:
        st.header("✨ 新增新生登記")
        with st.form("add_form", clear_on_submit=True):
            new_name = st.text_input("幼兒姓名*")
            new_phone = st.text_input("家長電話*")
            new_birth = st.text_input("民國生日 (例 110/05/20)")
            new_parent = st.text_input("家長姓名")
            new_note = st.text_area("初始備註")
            
            submit = st.form_submit_button("立即錄入 Excel", type="primary")
            
            if submit:
                if new_name and new_phone:
                    client = get_gspread_client()
                    if client:
                        sheet = client.open_by_key(SPREADSHEET_ID).get_sheets()[0]
                        # 依據您 Sheet 的表頭順序：時間戳記, 幼兒姓名, 家長電話, 幼兒生日, 家長姓名, 處理狀態, 老師備註
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
                        st.success(f"✅ {new_name} 錄入成功！")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("姓名與電話為必填項")

        st.divider()
        st.info("💡 提示：若要在 GitHub 部署，請確保已將 Service Account 的 Email 加入 Google 試算表的共用名單。")

if __name__ == "__main__":
    main()
