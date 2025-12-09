import streamlit as st
import pandas as pd
import math
import os
from datetime import date, datetime

# --- 設定資料庫檔案名稱 ---
STUDENT_FILE = 'students.csv'
REGISTRATION_FILE = 'registrations.csv'

# --- 讀取資料函式 ---
def load_data(filename, columns):
    if os.path.exists(filename):
        return pd.read_csv(filename)
    else:
        return pd.DataFrame(columns=columns)

# --- 儲存資料函式 ---
def save_data(df, filename):
    df.to_csv(filename, index=False, encoding='utf-8-sig')

# --- 核心邏輯：根據生日自動計算班級 (台灣學制：9/2分界) ---
def get_class_by_dob(dob):
    today = date.today()
    
    # 取得目前的「學年度」
    # 如果今天是 8月1日之後，學年度就是今年 (例如 2024/8/1 是 113學年)
    # 如果今天是 8月1日之前，學年度是去年
    current_school_year = today.year - 1911
    if today.month < 8:
        current_school_year -= 1
        
    # 計算孩子的入學年齡 (實歲)
    # 邏輯：學年度 - (出生年 - 1911)
    # 舉例：113學年 - (2019出生 = 108年) = 5歲 -> 大班
    birth_year_roc = dob.year - 1911
    
    # 修正 9/2 生日分界
    # 如果是 9/2 之後出生，算是下一屆，學齡要 -1
    if (dob.month > 9) or (dob.month == 9 and dob.day >= 2):
        age_in_school = current_school_year - birth_year_roc - 1
    else:
        age_in_school = current_school_year - birth_year_roc

    if age_in_school >= 5:
        return "大班"
    elif age_in_school == 4:
        return "中班"
    elif age_in_school == 3:
        return "小班"
    elif age_in_school == 2:
        return "幼幼班"
    else:
        return "未足齡 (托嬰)"

# --- 網頁設定 ---
st.set_page_config(page_title="幼兒園新生管理系統", layout="wide")
st.title("🏫 幼兒園新生管理系統")

# --- 側邊欄選單 ---
menu = st.sidebar.radio(
    "功能導航",
    ["目前學生管理", "新生報名", "師資需求計算"]
)

# ==========================================
# 功能 1: 目前學生管理 (含自動分班)
# ==========================================
if menu == "目前學生管理":
    st.header("👦👧 目前學生管理")

    # 1. 讀取資料
    df_students = load_data(STUDENT_FILE, ['姓名', '出生年月日', '班級', '備註'])

    # 2. 顯示統計看板 (新增幼幼班)
    st.subheader("📊 人數統計")
    if not df_students.empty:
        counts = df_students['班級'].value_counts()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("大班", f"{counts.get('大班', 0)} 人")
        c2.metric("中班", f"{counts.get('中班', 0)} 人")
        c3.metric("小班", f"{counts.get('小班', 0)} 人")
        c4.metric("幼幼班", f"{counts.get('幼幼班', 0)} 人")
    else:
        st.info("目前尚無學生資料")

    st.divider()

    # 3. 新增學生表單
    st.subheader("➕ 新增學生 (自動分班)")
    with st.form("add_student"):
        col1, col2 = st.columns(2)
        name = col1.text_input("學生姓名")
        
        # 改成日期選擇器 (預設選 2020/1/1 方便選取)
        default_date = date(2020, 1, 1)
        dob = col2.date_input("出生年月日", default_date, min_value=date(2015,1,1), max_value=date.today())
        
        # 顯示自動計算結果
        auto_grade = get_class_by_dob(dob)
        st.info(f"💡 系統判定：這位小朋友屬於 **{auto_grade}**")

        note = st.text_input("備註")
        
        submitted = st.form_submit_button("確認新增")
        
        if submitted and name:
            new_data = pd.DataFrame([{
                '姓名': name, 
                '出生年月日': dob, 
                '班級': auto_grade, # 這裡直接存入自動計算的班級
                '備註': note
            }])
            df_students = pd.concat([df_students, new_data], ignore_index=True)
            save_data(df_students, STUDENT_FILE)
            st.success(f"已新增：{name} ({auto_grade})")
            st.rerun()

    # 4. 顯示表格
    st.subheader("📋 學生名單")
    st.dataframe(df_students, use_container_width=True)

# ==========================================
# 功能 2: 新生報名
# ==========================================
elif menu == "新生報名":
    st.header("📝 新生報名登記")
    
    # 1. 讀取資料
    columns = ['報名日期', '家長姓名', '幼兒姓名', '幼兒生日', '判定班級', '家長電話', '聯絡方式']
    df_reg = load_data(REGISTRATION_FILE, columns)

    # 2. 報名表單
    with st.form("reg_form"):
        reg_date = st.date_input("報名日期", date.today())
        
        col1, col2 = st.columns(2)
        p_name = col1.text_input("家長姓名")
        c_name = col2.text_input("幼兒姓名")
        
        # 這裡也加入生日自動判斷
        dob_reg = col2.date_input("幼兒生日", date(2020, 1, 1))
        auto_grade_reg = get_class_by_dob(dob_reg)
        st.caption(f"📅 根據生日，預計入學班級為：{auto_grade_reg}")

        col3, col4 = st.columns(2)
        phone = col3.text_input("家長電話")
        contact_method = col4.selectbox("偏好聯絡方式", ["電話", "Line", "Email", "親自拜訪"])
        
        if st.form_submit_button("提交報名"):
            if p_name and c_name:
                new_reg = pd.DataFrame([{
                    '報名日期': reg_date,
                    '家長姓名': p_name, 
                    '幼兒姓名': c_name, 
                    '幼兒生日': dob_reg,
                    '判定班級': auto_grade_reg,
                    '家長電話': phone,
                    '聯絡方式': contact_method
                }])
                df_reg = pd.concat([df_reg, new_reg], ignore_index=True)
                save_data(df_reg, REGISTRATION_FILE)
                st.success("報名成功！")
                st.rerun()
            else:
                st.error("請至少填寫姓名")

    st.divider()
    st.subheader("📞 待聯絡清單")
    st.dataframe(df_reg, use_container_width=True)

# ==========================================
# 功能 3: 師資需求計算 (進階版)
# ==========================================
elif menu == "師資需求計算":
    st.header("👩‍🏫 師資人力規劃")
    st.markdown("由於幼幼班法定師生比通常較低 (1:8)，此處可分開設定。")

    # 1. 讀取學生數
    df_students = load_data(STUDENT_FILE, ['姓名', '班級', '備註'])
    counts = df_students['班級'].value_counts() if not df_students.empty else {}

    # 2. 設定參數
    col1, col2 = st.columns(2)
    with col1:
        ratio_normal = st.number_input("大/中/小班 師生比", min_value=1, value=15, help="通常為 1:15")
    with col2:
        ratio_toddler = st.number_input("幼幼班 師生比", min_value=1, value=8, help="通常為 1:8")

    # 3. 計算並顯示
    results = []
    
    # 定義每個班級對應的師生比
    class_config = [
        ('大班', ratio_normal),
        ('中班', ratio_normal),
        ('小班', ratio_normal),
        ('幼幼班', ratio_toddler)
    ]

    total_teachers = 0

    for grade, ratio in class_config:
        num = counts.get(grade, 0)
        teachers = math.ceil(num / ratio) if num > 0 else 0
        total_teachers += teachers
        
        results.append({
            "班級": grade,
            "目前學生數": num,
            "設定師生比": f"1 : {ratio}",
            "所需老師": teachers
        })
    
    st.table(pd.DataFrame(results))
    
    st.info(f"🏆 全園總計需要： **{total_teachers}** 位老師")
