import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import json
import time

# ==========================================
# 0. 系統環境與蘋果風格介面
# ==========================================
st.set_page_config(page_title="幼兒園招生雲端管理", page_icon="🏫", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700;900&display=swap');
    .main { background-color: #F2F2F7; }
    html, body, [class*="css"] { 
        font-family: -apple-system, "BlinkMacSystemFont", "PingFang TC", "Noto Sans TC", sans-serif !important; 
    }
    
    /* 蘋果風格統計卡片 */
    .stMetric {
        background-color: white;
        padding: 24px;
        border-radius: 24px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
        border: 1px solid rgba(0,0,0,0.05);
    }
    
    /* 表格編輯器優化 */
    div[data-testid="stDataEditor"] {
        border-radius: 24px !important;
        overflow: hidden;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 雲端連線設定 (已嵌入您的專屬金鑰)
# ==========================================

GSHEET_ID = "1ZofZnB8Btig_6XvsHGh7bbapnfJM-vDkXTFpaU7ngmE"

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

# 定義欄位名稱 (必須與雲端 Excel 第一列完全相同)
COL_REG_STATUS = "報名狀態"
COL_CON_STATUS = "聯繫狀態"
COL_REG_DATE   = "登記日期"
COL_NAME       = "幼兒姓名"
COL_PARENT     = "家長稱呼"
COL_PHONE      = "電話"
COL_BIRTH      = "幼兒生日"
COL_ENTRY_INFO = "預計入學資訊"
COL_REF        = "推薦人"
COL_NOTE       = "備註"
COL_PRIORITY   = "重要性"

@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_JSON_KEY, scope)
    return gspread.authorize(creds)

def fetch_data():
    """診斷型抓取資料函數"""
    try:
        client = get_gspread_client()
        sheet_obj = client.open_by_key(GSHEET_ID).get_sheets()[0]
        data = sheet_obj.get_all_records()
        if not data:
            return pd.DataFrame(), sheet_obj, "⚠️ 成功連線，但 Excel 內沒有任何資料數據。"
        return pd.DataFrame(data), sheet_obj, "✅ 連線成功"
    except gspread.exceptions.SpreadsheetNotFound:
        return pd.DataFrame(), None, "❌ 找不到試算表，請檢查 ID 是否正確。"
    except gspread.exceptions.APIError as e:
        if "permission" in str(e).lower():
            return pd.DataFrame(), None, f"❌ 權限不足！請將試算表「共用」給：{GOOGLE_JSON_KEY['client_email']}"
        return pd.DataFrame(), None, f"❌ Google API 錯誤：{str(e)}"
    except Exception as e:
        return pd.DataFrame(), None, f"❌ 未知錯誤：{str(e)}"

# ==========================================
# 2. 班別計算邏輯
# ==========================================
def calculate_grade_info(birthday_str):
    if not birthday_str or "/" not in str(birthday_str): return ""
    try:
        parts = str(birthday_str).split('/')
        roc_year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        ce_year = roc_year + 1911
        today = date.today()
        target_year = today.year if today.month < 9 else today.year + 1
        age = target_year - ce_year
        if month > 9 or (month == 9 and day >= 2): age -= 1
        
        grade_map = {2: "幼幼班", 3: "小班", 4: "中班", 5: "大班"}
        grade_name = grade_map.get(age, "未滿2歲" if age < 2 else f"{age}歲")
        return f"{target_year - 1911} 學年 - {grade_name}"
    except: return ""

# ==========================================
# 3. 主介面 UI
# ==========================================
def main():
    df, sheet, status_msg = fetch_data()
    
    # 頂部狀態列
    t1, t2 = st.columns([5, 1])
    with t1:
        st.title("🏫 幼兒園招生雲端管理系統")
        if "✅" in status_msg:
            st.success(status_msg)
        else:
            st.error(status_msg)
    with t2:
        if st.button("🔄 強制刷新", use_container_width=True): 
            st.cache_resource.clear()
            st.rerun()

    if df.empty:
        st.info("💡 提示：如果雲端 Excel 有資料但這裡沒顯示，請檢查 Excel 第一列標題是否完全正確。")
        with st.expander("查看系統要求的 Excel 標題順序"):
            st.write(", ".join([COL_REG_STATUS, COL_CON_STATUS, COL_REG_DATE, COL_NAME, COL_PARENT, COL_PHONE, COL_BIRTH, COL_ENTRY_INFO, COL_REF, COL_NOTE, COL_PRIORITY]))
        return

    # A. 數據統計看板
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("總人數", len(df))
    m2.metric("抓取列數", f"{len(df)} Rows")
    m3.metric("待聯繫", len(df[df[COL_CON_STATUS] == '未聯繫']) if COL_CON_STATUS in df.columns else 0)
    m4.metric("重要性(高)", len(df[df[COL_PRIORITY] == '高']) if COL_PRIORITY in df.columns else 0)

    st.divider()

    # B. 搜尋與篩選
    search = st.text_input("🔍 搜尋姓名、電話、家長或備註...", placeholder="請輸入關鍵字")
    
    display_df = df.copy()
    if search:
        mask = display_df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        display_df = display_df[mask]

    # C. 名單編輯區
    st.subheader("📋 招生名單明細")
    st.caption("直接在下方表格修改資料，修改完請記得按儲存按鈕。")
    
    column_config = {
        COL_REG_STATUS: st.column_config.SelectboxColumn("報名狀態", options=["排隊等待", "已入學", "取消報名", "候補中"]),
        COL_CON_STATUS: st.column_config.SelectboxColumn("聯繫狀態", options=["未聯繫", "聯繫中", "已聯繫", "電話未接"]),
        COL_PRIORITY: st.column_config.SelectboxColumn("重要性", options=["高", "中", "低"]),
        COL_NOTE: st.column_config.TextColumn("備註內容", width="large"),
        COL_REG_DATE: st.column_config.TextColumn("登記日期", disabled=True)
    }

    updated_df = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config
    )
    
    if st.button("💾 將變更同步至雲端 Excel", type="primary"):
        try:
            with st.spinner("同步中..."):
                sheet.clear()
                sheet.update('A1', [updated_df.columns.values.tolist()] + updated_df.values.tolist())
                st.success("✅ 同步成功！")
                time.sleep(1)
                st.rerun()
        except Exception as e:
            st.error(f"同步失敗：{e}")

    # D. 側邊欄：新增
    with st.sidebar:
        st.header("✨ 錄入新名單")
        with st.form("add_form", clear_on_submit=True):
            n_name = st.text_input("幼兒姓名")
            n_phone = st.text_input("電話*")
            n_birth = st.text_input("幼兒生日 (112/10/06)")
            n_parent = st.text_input("家長稱呼")
            n_ref = st.text_input("推薦人")
            n_prio = st.selectbox("重要性", ["中", "高", "低"])
            n_note = st.text_area("初始備註")
            
            if st.form_submit_button("立即寫入雲端", type="primary", use_container_width=True):
                if n_phone:
                    entry_info = calculate_grade_info(n_birth)
                    new_row = [
                        "排隊等待", "未聯繫", 
                        date.today().strftime("%Y/%m/%d"), 
                        n_name, n_parent, n_phone, n_birth, entry_info, n_ref, n_note, n_prio
                    ]
                    sheet.append_row(new_row)
                    st.success(f"🎉 {n_name} 已成功錄入 Excel！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("電話為必填")

if __name__ == "__main__":
    main()
