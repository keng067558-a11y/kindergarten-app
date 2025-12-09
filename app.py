import streamlit as st
import pandas as pd
import os
from datetime import date, datetime

# --- 檔案設定 ---
REGISTRATION_FILE = 'registrations.csv'

# --- [工具 1] 民國日期選擇器 ---
def roc_date_input(label, default_date=None):
    st.markdown(f"**{label}**")
    c1, c2, c3 = st.columns([1, 1, 1])
    
    if default_date is None:
        default_date = date.today()
        
    current_roc_year = default_date.year - 1911
    
    with c1:
        # 預設給一個常見的幼兒出生年範圍，例如民國105年~114年
        roc_year = st.number_input("民國(年)", min_value=100, max_value=120, value=current_roc_year)
    with c2:
        month = st.selectbox("月", range(1, 13), index=default_date.month-1)
    with c3:
        day = st.selectbox("日", range(1, 32), index=default_date.day-1)

    # 防呆機制：處理像 2/30 這種錯誤日期
    try:
        return date(roc_year + 1911, month, day)
    except ValueError:
        return date.today() # 日期錯誤就回傳今天

# --- [工具 2] 民國日期轉字串 (存檔用) ---
def to_roc_str(d):
    return f"{d.year-1911}/{d.month:02d}/{d.day:02d}"

# --- [核心 3] 自動計算入學清單 ---
def calculate_admission_roadmap(dob):
    """
    輸入生日，回傳未來 3 年適合入學的清單
    """
    today = date.today()
    # 取得目前的民國學年度 (8月1日換學年)
    current_roc_school_year = today.year - 1911
    if today.month < 8:
        current_roc_school_year -= 1
        
    roadmap = []
    
    # 9月2日分界點邏輯
    # 如果是 9/2 (含) 以後出生，學齡要 -1 (算是下一屆)
    offset = 0
    if (dob.month > 9) or (dob.month == 9 and dob.day >= 2):
        offset = 1
        
    # 計算未來 4 年的落點
    for i in range(4):
        target_year = current_roc_school_year + i
        # 學齡 = 學年度 - 出生年 - 9/2修正
        age = target_year - (dob.year - 1911) - offset
        
        grade = ""
        if age == 2: grade = "幼幼班"
        elif age == 3: grade = "小班"
        elif age == 4: grade = "中班"
        elif age == 5: grade = "大班"
        elif age < 2: grade = "托嬰中心 (未足齡)"
        else: grade = "畢業/超齡"
        
        # 只顯示還能讀的班級
        if "畢業" not in grade:
            roadmap.append({
                "學年度": f"{target_year} 學年",
                "班級": grade,
                "預計入學時間": f"民國 {target_year} 年 8 月",
                "狀態": "✅ 招生中" if i==0 else "🗓️ 預約排程"
            })
            
    return pd.DataFrame(roadmap)

# --- 讀取/儲存 ---
def load_data():
    if os.path.exists(REGISTRATION_FILE):
        return pd.read_csv(REGISTRATION_FILE)
    return pd.DataFrame(columns=['登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊'])

def save_data(df):
    df.to_csv(REGISTRATION_FILE, index=False, encoding='utf-8-sig')

# ==========================================
# 介面開始
# ==========================================
st.set_page_config(page_title="新生入學試算", layout="wide")
st.title("👶 新生報名與入學試算")

# 1. 讀取舊資料
df_reg = load_data()

with st.container():
    st.subheader("第一步：輸入基本資料")
    
    # --- 幼兒資料 ---
    c1, c2 = st.columns(2)
    with c1:
        child_name = st.text_input("幼兒姓名")
    with c2:
        # 民國生日選擇器
        # 預設 2021 (民國110)
        dob = roc_date_input("幼兒出生年月日", default_date=date(2021, 9, 2))

    # --- 家長資料 (姓氏+稱謂) ---
    c3, c4, c5 = st.columns([1, 1, 2])
    with c3:
        parent_last_name = st.text_input("家長姓氏", placeholder="例如：陳")
    with c4:
        parent_title = st.selectbox("稱謂", ["先生", "小姐", "爸爸", "媽媽", "阿公", "阿嬤"])
    with c5:
        phone = st.text_input("聯絡電話 (主要聯繫方式)")

    st.divider()

    # --- 自動試算結果 ---
    st.subheader("第二步：系統判定入學時程")
    
    # 呼叫計算函式
    roadmap_df = calculate_admission_roadmap(dob)
    
    # 顯示表格給使用者看
    st.table(roadmap_df)
    
    # 製作下拉選單讓使用者「選」一個方案
    st.info("👇 請從上方清單中，選擇家長希望登記的入學時間：")
    
    # 把表格轉成選單文字，例如 "114 學年 - 小班 (民國 114 年 8 月)"
    options = roadmap_df.apply(
        lambda x: f"{x['學年度']} - {x['班級']} ({x['預計入學時間']})", axis=1
    )
    
    selected_plan = st.selectbox("確認登記項目", options)

    st.divider()

    # --- 送出按鈕 ---
    submit_btn = st.button("提交報名資料", type="primary", use_container_width=True)

    if submit_btn:
        if child_name and parent_last_name and phone:
            # 組合家長稱呼
            full_parent_name = f"{parent_last_name} {parent_title}"
            
            new_entry = pd.DataFrame([{
                '登記日期': to_roc_str(date.today()),
                '幼兒姓名': child_name,
                '家長稱呼': full_parent_name,
                '電話': phone,
                '幼兒生日': to_roc_str(dob),
                '預計入學資訊': selected_plan
            }])
            
            df_reg = pd.concat([df_reg, new_entry], ignore_index=True)
            save_data(df_reg)
            st.success(f"✅ 報名成功！已登記：{child_name} ({selected_plan})")
            st.rerun()
        else:
            st.error("❌ 請確認「幼兒姓名」、「家長姓氏」與「電話」皆已填寫")

# --- 顯示已登記清單 ---
st.divider()
st.subheader("📋 目前已登記候補名單")
st.dataframe(df_reg, use_container_width=True)
