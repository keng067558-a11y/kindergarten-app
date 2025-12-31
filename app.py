import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import time

# ==========================================
# 0. 介面美化與設定 (蘋果極簡風)
# ==========================================
st.set_page_config(page_title="幼兒園報名管理", page_icon="📝", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700;900&display=swap');
    .main { background-color: #F2F2F7; }
    html, body, [class*="css"] { 
        font-family: -apple-system, "BlinkMacSystemFont", "PingFang TC", "Noto Sans TC", sans-serif !important; 
    }
    
    /* 統計方塊樣式 */
    .stMetric {
        background-color: white;
        padding: 24px;
        border-radius: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03);
        border: 1px solid rgba(0,0,0,0.05);
    }
    
    /* 按鈕樣式 */
    .stButton>button {
        border-radius: 12px;
        font-weight: 700;
        border: none;
        background-color: #007AFF;
        color: white;
        transition: all 0.2s;
    }
    
    /* 表格編輯器圓角 */
    div[data-testid="stDataEditor"] {
        border-radius: 20px !important;
        overflow: hidden;
    }

    [data-testid="stSidebar"] {
        background-color: white;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 雲端金鑰連線 (對接您的 Google Sheets)
# ==========================================

GSHEET_ID = "1ZofZnB8Btig_6XvsHGh7bbapnfJM-vDkXTFpaU7ngmE"

# 服務帳號金鑰 (已嵌入您的專屬授權)
GOOGLE_JSON_KEY = {
  "type": "service_account",
  "project_id": "gen-lang-client-0350949155",
  "private_key_id": "0bc65fcf31f2bc625d4283024181f980b94e2d61",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQC2d0a4Jmkhn/gS\nOmYM0zbKtBMteB/pnmSqD8S0khV+9Upr1KRx2sjQ+YqYuYxa6wCX6zNCSclYTs0x\nAHg3qvEQXZ59UgUz8BWKOE59oI3o5rEDWhvBFu7KsXsugFXbgYGa4zTFGKHL7vMB\n4mtI48NwFeqZ/Jx7pJfbZ74j0hj71DWGGoKXWi8gPiC5Cj1HWDByveniWIFK5FOd\nPvcJD0e0jNPPbe/dvlyWs9vwRj6aLSyEFxoTb+uLelAQj3Mq4I6RUyzYPv+j/+5w\nvKbqbF+nox77OGvvTFdpUiY5t5PDVpObAiSSn1jGlB1dMDfJQ8G+73CK+YlKvTKf\nOjCUgZeHAgMBAAECggEAGhfciSEVD7Xsp86qIVNjFoHB7FKtXZ9FDfzLSHdLk6hI\nSDtUeOOsrBXDeCuwop/Qqej8n5IltPcv6L4EcxGC/7AjphBApjjDG80JjHWVVaUH\n007jgS1iYKIY14GKxaUzf47WUQlAugUlwzM53GaV4EWCExtI1XWoMbwYOM8mu3xT\ne8BA9cvt1a8CJjWmKgChin3qi1YEinKNudO4rJOMPCq+kVSWVEphy7XndlNWLm7E\nY5BGr+pCGGoHHlqWMotQpBuL4KzTUKom/cDj16Hk3sr8lU5wP2dXa8/ftHfSzfYp\n4THbqi9ote5CFlymVPeS6c3uEtX20ALPlg5eXA4qYQKBgQDhrGo4v7VTED01mLBk\ng2FFSigYexlHqJZRNoBuccIGgTfbKmWIDI1FQAE3klml6ZAJudejIWf902+dX7sQ\n/NsnRLeNtc1Et/HnPuNVPUwMflphZ56o2BedBRZ1UXswlfKgCE0SrSjGp1cx7nsB\nS+ZoiFynEpL1PAd4tqvG+IrRewKBgQDO/HDls+Qh1i5gOLjI7pwGf3aKdVONGODa\LsNF0vPbRGeUjxgmBIZ6DdQZRUOOCw547w0IlgHBSSNLbZZOzz/9cMS0U0PXLh41\TkKaih14ZpV1kK1i/9XP1HbQlW2vLLVbD7Wzti2dOujJp1cCp9C7ZtgP7FOFlLrD\nY/fyqpc2ZQKBgQCSCIlAKcZDdwm06haTJHVIakFh/h6QwWZsLVGUpqaAoROtDlVf\YYf1XQKsnFbIx0g/EvSYiqCJn03lz7H0vzttwMjquc+X/VRbaNWhLiZNG2KPD4eb\nCSLWqBktV8nY2d+EcXq2cDknu9fv5rvQTfZOhJc4Qgu5B9xp4ANuoRzriwKBgQC7\nDDWZ3q7SRRMzsQ6LxdUJqjYdeVk/sLPBd3DPsIreIzrXbViNQpmjwstg6s7ZlfRG\nJQDKOYTsfoN+rlGednuFNFsN+hDca7iww0A9F4L6QvndfBiz1i4J2h5k8CRmoShi\nWhgBhyhBZfLoCGkA5VYjhBTMjuwLUxRTbgurJ63uYQKBgQC3NOVqMlBubI6D1/LM\nlD8HYsZxl1VsNa3wqalvqJLFgOzVSSn9UXdjNxq1Wz3VUKV5GdwVsuUWIDJ6jMyQ\nctis0id1NLpIvUNnY5VYbsX/WP/nRCUYNKfuE4LgpQoCbbmNs0bHXYUmASg4Fg/0\nUKv2TDsqoh5Yi6nl4kYEH5jSBw==\n-----END PRIVATE KEY-----\n",
  "client_email": "keng067558@gen-lang-client-0350949155.iam.gserviceaccount.com",
  "client_id": "114682091672664451195",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/keng067558%40gen-lang-client-0350949155.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}

# 欄位定義 (完全適配您的 Excel)
HEADERS = ["報名狀態", "聯繫狀態", "登記日期", "幼兒姓名", "家長稱呼", "電話", "幼兒生日", "預計入學資訊", "推薦人", "備註", "重要性"]

@st.cache_resource
def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_JSON_KEY, scope)
    return gspread.authorize(creds)

def load_all_data():
    try:
        client = get_client()
        sheet = client.open_by_key(GSHEET_ID).get_sheets()[0]
        data = sheet.get_all_records()
        
        # 若 Excel 是空的或標題不對，自動初始化
        if not data:
            sheet.clear()
            sheet.update(range_name='A1', values=[HEADERS])
            return pd.DataFrame(columns=HEADERS), sheet
            
        return pd.DataFrame(data), sheet
    except Exception as e:
        st.error(f"連線失敗，請檢查權限設定：{e}")
        return pd.DataFrame(), None

# ==========================================
# 2. 主頁面邏輯
# ==========================================
def main():
    # 讀取雲端最新資料
    df, sheet = load_all_data()
    
    # 頂部狀態列
    t1, t2 = st.columns([5, 1])
    with t1:
        st.title("📝 幼兒園招生自動化系統")
        st.caption("✅ 已連結 Google 試算表 (即時更新模式)")
    with t2:
        if st.button("🔄 刷新頁面", use_container_width=True): 
            st.cache_resource.clear()
            st.rerun()

    # A. 數據統計
    m1, m2, m3 = st.columns(3)
    count = len(df)
    m1.metric("總登記人數", count)
    m2.metric("待聯繫名單", len(df[df['聯繫狀態'] == '未聯繫']) if count > 0 else 0)
    m3.metric("資料同步", "雲端連線中")

    st.divider()

    # B. 搜尋篩選
    search_query = st.text_input("🔍 搜尋孩子姓名、電話或備註...", placeholder="請輸入搜尋內容")
    
    display_df = df.copy()
    if search_query:
        # 全欄位搜尋
        mask = display_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
        display_df = display_df[mask]

    # C. 名單列表與編輯區
    if not display_df.empty:
        st.subheader("📋 招生名單明細")
        st.caption("💡 提示：您可以直接在表格內修改報名狀態、電話或備註，修改後請按儲存。")
        
        # 配置表格編輯器
        updated_df = st.data_editor(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "報名狀態": st.column_config.SelectboxColumn("狀態", options=["排隊等待", "已入學", "取消報名", "候補中"]),
                "聯繫狀態": st.column_config.SelectboxColumn("聯絡進度", options=["未聯繫", "聯繫中", "已聯繫", "電話未接"]),
                "電話": st.column_config.TextColumn("聯絡電話"),
                "備註": st.column_config.TextColumn("詳細備註", width="large"),
                "重要性": st.column_config.SelectboxColumn("等級", options=["高", "中", "低"]),
                "登記日期": st.column_config.TextColumn("日期", disabled=True)
            }
        )
        
        # 儲存變更按鈕
        if st.button("💾 儲存所有修改至 Excel", type="primary"):
            try:
                with st.spinner("同步雲端 Excel 中..."):
                    sheet.clear()
                    # 按照 HEADERS 順序寫回
                    data_to_save = [updated_df.columns.values.tolist()] + updated_df.values.tolist()
                    sheet.update(range_name='A1', values=data_to_save, value_input_option='USER_ENTERED')
                    st.success("✅ Excel 已同步更新！")
                    time.sleep(1)
                    st.rerun()
            except Exception as e:
                st.error(f"同步失敗：{e}")
    else:
        st.info("👋 目前沒有任何登記資料。請在左側邊欄新增第一筆資料。")

    # D. 側邊欄：快速新增
    with st.sidebar:
        st.header("✨ 新增報名資訊")
        with st.form("add_form", clear_on_submit=True):
            n_name = st.text_input("孩子姓名*")
            n_parent = st.text_input("家長姓氏 (例：林先生)")
            n_phone = st.text_input("聯絡電話*")
            n_birth = st.text_input("生日 (例 112/05/20)")
            n_note = st.text_area("備註內容")
            
            if st.form_submit_button("立即新增至雲端", use_container_width=True):
                if n_name and n_phone:
                    # 準備這 11 個欄位的資料 (對齊您的 Excel 標題順序)
                    new_row = [
                        "排隊等待",                   # 報名狀態
                        "未聯繫",                    # 聯繫狀態
                        datetime.now().strftime("%Y/%m/%d"), # 登記日期
                        n_name,                      # 幼兒姓名
                        n_parent,                    # 家長稱呼
                        n_phone,                     # 電話
                        n_birth,                     # 幼兒生日
                        "",                          # 預計入學資訊 (暫留空)
                        "",                          # 推薦人 (暫留空)
                        n_note,                      # 備註
                        "中"                         # 重要性
                    ]
                    try:
                        with st.spinner("寫入中..."):
                            sheet.append_row(new_row, value_input_option='USER_ENTERED')
                            st.success(f"🎉 {n_name} 已成功存入您的 Excel！")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"寫入失敗：{e}")
                else:
                    st.error("姓名與電話為必填項")

        st.divider()
        st.caption("📍 所有資料均加密傳輸至您的私有 Google 試算表。")

if __name__ == "__main__":
    main()
