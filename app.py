import streamlit as st
import pandas as pd
import math
import os
import datetime  # 新增：處理日期需要這個工具

# --- 設定資料庫檔案名稱 (CSV) ---
# 注意：在 Streamlit Cloud 免費版，App 重啟後 CSV 資料會重置
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

# --- 網頁設定 ---
st.set_page_config(page_title="幼兒園管理系統", layout="wide")
st.title("🏫 幼兒園管理系統 (GitHub版)")

# --- 側邊欄選單 ---
menu = st.sidebar.radio(
    "功能導航",
    ["目前學生管理", "新生報名", "師資需求計算"]
)

# ==========================================
# 功能 1: 目前學生管理
# ==========================================
if menu == "目前學生管理":
    st.header("👦👧 目前學生管理")

    # 1. 讀取資料
    df_students = load_data(STUDENT_FILE, ['姓名', '班級', '備註'])

    # 2. 顯示統計看板
    st.subheader("📊 人數統計")
    if not df_students.empty:
        counts = df_students['班級'].value_counts()
        c1, c2, c3 = st.columns(3)
        c1.metric("大班人數", f"{counts.get('大班', 0)} 人")
        c2.metric("中班人數", f"{counts.get('中班', 0)} 人")
        c3.metric("小班人數", f"{counts.get('小班', 0)} 人")
    else:
        st.info("目前尚無學生資料")

    st.divider()

    # 3. 新增學生表單
    st.subheader("➕ 新增學生")
    with st.form("add_student"):
        col1, col2 = st.columns(2)
        name = col1.text_input("學生姓名")
        grade = col2.selectbox("班級", ["大班", "中班", "小班"])
        note = st.text_input("備註")
        
        submitted = st.form_submit_button("新增確認")
        
        if submitted and name:
            new_data = pd.DataFrame([{'姓名': name, '班級': grade, '備註': note}])
            df_students = pd.concat([df_students, new_data], ignore_index=True)
            save_data(df_students, STUDENT_FILE)
            st.success(f"已新增：{name}")
            st.rerun()

    # 4. 顯示表格
    st.subheader("📋 學生名單")
    st.dataframe(df_students, use_container_width=True)

# ==========================================
# 功能 2: 新生報名 (這裡有重大更新！)
# ==========================================
elif menu == "新生報名":
    st.header("📝 新生報名登記")
    
    # 1. 讀取資料 (欄位增加了)
    columns = ['報名日期', '家長姓名', '幼兒姓名', '家長電話', '聯絡方式', '預計班級']
    df_reg = load_data(REGISTRATION_FILE, columns)

    # 2. 報名表單
    with st.form("reg_form"):
        # 新增：日期選擇器 (預設今天)
        reg_date = st.date_input("報名日期", datetime.date.today())
        
        col1, col2 = st.columns(2)
        p_name = col1.text_input("家長姓名")
        c_name = col2.text_input("幼兒姓名")
        
        col3, col4 = st.columns(2)
        phone = col3.text_input("家長電話")
        # 新增：聯絡方式下拉選單
        contact_method = col4.selectbox("偏好聯絡方式", ["電話", "Line", "Email", "親自拜訪"])
        
        target = st.selectbox("預計入學班級", ["大班", "中班", "小班"])
        
        if st.form_submit_button("提交報名"):
            if p_name and c_name:
                new_reg = pd.DataFrame([{
                    '報名日期': reg_date,
                    '家長姓名': p_name, 
                    '幼兒姓名': c_name, 
                    '家長電話': phone,
                    '聯絡方式': contact_method,
                    '預計班級': target
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
# 功能 3: 師資需求計算
# ==========================================
elif menu == "師資需求計算":
    st.header("👩‍🏫 師資人力規劃")

    # 1. 讀取學生數
    df_students = load_data(STUDENT_FILE, ['姓名', '班級', '備註'])
    counts = df_students['班級'].value_counts() if not df_students.empty else {}

    # 2. 設定參數
    st.info("請輸入法定的師生比 (例如 1:15 請輸入 15)")
    ratio = st.number_input("師生比", min_value=1, value=15)

    # 3. 計算並顯示
    results = []
    for grade in ['大班', '中班', '小班']:
        num = counts.get(grade, 0)
        teachers = math.ceil(num / ratio) if num > 0 else 0
        results.append({
            "班級": grade,
            "目前學生": num,
            "師生比": f"1:{ratio}",
            "所需老師": teachers
        })
    
    st.table(pd.DataFrame(results))
