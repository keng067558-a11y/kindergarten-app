import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import time

# ==========================================
# 0. 系統介面美化 (Apple 極簡美學)
# ==========================================
st.set_page_config(page_title="幼兒園報名系統", page_icon="📝", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700;900&display=swap');
    .main { background-color: #F2F2F7; }
    html, body, [class*="css"] { 
        font-family: -apple-system, "PingFang TC", "Noto Sans TC", sans-serif !important; 
    }
    
    /* 統計方塊 */
    .stMetric {
        background-color: white;
        padding: 24px;
        border-radius: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    }
    
    /* 輸入框與按鈕 */
    .stButton>button {
        border-radius: 12px;
        font-weight: 700;
        border: none;
        background-color: #007AFF;
        color: white;
        transition: all 0.2s;
    }
    .stButton>button:hover { background-color: #0056b3; }
    
    /* 表格編輯器 */
    div[data-testid="stDataEditor"] {
        border-radius: 20px !important;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 雲端連線配置 (已嵌入您的金鑰)
# ==========================================

# 試算表 ID
GSHEET_ID = "1ZofZnB8Btig_6XvsHGh7bbapnfJM-vDkXTFpaU7ngmE"

# 服務帳號金鑰
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

@st.cache_resource
def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_JSON_KEY, scope)
    return gspread.authorize(creds)

def load_data():
    try:
        client = get_client()
        sheet = client.open_by_key(GSHEET_ID).get_sheets()[0]
        data = sheet.get_all_records()
        return pd.DataFrame(data), sheet
    except Exception as e:
        st.error(f"連線失敗：{e}")
        return pd.DataFrame(), None

# ==========================================
# 2. 主頁面邏輯
# ==========================================
def main():
    df, sheet = load_data()
    
    # Header
    t1, t2 = st.columns([5, 1])
    with t1:
        st.title("📝 幼兒園報名管理系統")
        st.caption("✅ 雲端同步模式：已直接連動您的 Google 試算表")
    with t2:
        if st.button("🔄 刷新", use_container_width=True): 
            st.cache_resource.clear()
            st.rerun()

    if df.empty and sheet is not None:
        st.info("👋 歡迎！目前名單是空的，請在側邊欄填寫第一筆資料。")

    # A. 數據統計
    m1, m2, m3 = st.columns(3)
    m1.metric("總登記人數", len(df))
    m2.metric("待聯繫", len(df[df['處理狀態'] == '待處理']) if not df.empty else 0)
    m3.metric("資料庫狀態", "連線穩定")

    st.divider()

    # B. 搜尋功能
    search = st.text_input("🔍 搜尋孩子姓名、家長或電話...", placeholder="輸入關鍵字...")
    
    display_df = df.copy()
    if search:
        mask = display_df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        display_df = display_df[mask]

    # C. 名單清單與編輯
    if not display_df.empty:
        st.subheader("📋 報名清單 (可直接在表格內修改)")
        
        # 蘋果風格表格配置
        updated_df = st.data_editor(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "幼兒姓名": st.column_config.TextColumn("孩子姓名", required=True),
                "家長姓氏": st.column_config.TextColumn("家長姓氏"),
                "電話": st.column_config.TextColumn("聯絡電話"),
                "備註": st.column_config.TextColumn("備註內容", width="large"),
                "處理狀態": st.column_config.SelectboxColumn("狀態", options=["待處理", "已聯繫", "確認入學", "取消"]),
                "登記日期": st.column_config.TextColumn("登記日期", disabled=True)
            }
        )
        
        if st.button("💾 儲存並同步變更至 Excel", type="primary"):
            try:
                sheet.clear()
                # 寫回包含表頭的完整資料
                sheet.update('A1', [updated_df.columns.values.tolist()] + updated_df.values.tolist())
                st.success("✅ 同步成功！")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"同步失敗：{e}")

    # D. 側邊欄：快速新增
    with st.sidebar:
        st.header("✨ 新增報名登記")
        with st.form("add_form", clear_on_submit=True):
            n_name = st.text_input("孩子姓名*")
            n_parent = st.text_input("家長姓氏 (例：林先生)")
            n_phone = st.text_input("聯絡電話*")
            n_note = st.text_area("備註")
            
            if st.form_submit_button("立即送出並寫入雲端", use_container_width=True):
                if n_name and n_phone:
                    # 依據 Excel 表頭順序準備一列資料
                    new_row = [
                        n_name,
                        n_parent,
                        n_phone,
                        n_note,
                        "待處理",
                        datetime.now().strftime("%Y/%m/%d %H:%M:%S")
                    ]
                    try:
                        sheet.append_row(new_row)
                        st.success(f"🎉 {n_name} 的資料已存入雲端！")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"寫入失敗：{e}")
                else:
                    st.error("姓名與電話為必填項")

        st.divider()
        st.caption("📍 系統已連動您的私有 Google Sheet。")

if __name__ == "__main__":
    main()
