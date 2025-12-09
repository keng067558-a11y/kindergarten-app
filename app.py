import streamlit as st
import pandas as pd
import math
import os
from datetime import date, datetime

# --- 設定資料庫檔案名稱 ---
STUDENT_FILE = 'students.csv'
REGISTRATION_FILE = 'registrations.csv'

# ==========================================
# 🛠️ [自製工具] 民國日期選擇器 (核心修改)
# ==========================================
def roc_date_input(label, default_date=None, key_suffix=""):
    """
    這是一個自製的介面，讓使用者可以直接選「民國」年/月/日
    回傳：標準的 Python date 物件 (西元)，方便系統內部計算
    """
    if default_date is None:
        default_date = date.today()
    
    st.write(f"**{label}**") # 標題
    c1, c2, c3 = st.columns([1, 1, 1])
    
    # 計算預設的民國年
    default_roc_year = default_date.year - 1911
    
    with c1:
        # 輸入民國年
        roc_year = st.number_input("民國(年)", min_value=80, max_value=150, value=default_roc_year, key=f"y_{key_suffix}")
    with c2:
        # 選擇月份
        month = st.selectbox("月", range(1, 13), index=default_date.month-1, key=f"m_{key_suffix}")
    with c3:
        # 選擇日期 (簡單處理，預設顯示1-31)
        day = st.selectbox("日", range(1, 32), index=default_date.day-1, key=f"d_{key_suffix}")

    # 嘗試轉換成日期，防止使用者選出 2/30 這種日期
    try:
        # 轉回西元計算
        ad_year = roc_year + 1911
        selected_date = date(ad_year, month, day)
        return selected_date
    except ValueError:
        st.error("日期無效 (例如沒有2月30日)，已自動修正為今日。")
        return date.today()

# --- [工具] 西元轉民國顯示字串 ---
def to_roc_date_str(date_obj):
    if pd.isnull(date_obj): return ""
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.strptime(date_obj, "%Y-%m-%d").date()
        except:
            return date_obj
    roc_year = date_obj.year - 1911
    return f"{roc_year}/{date_obj.month:02d}/{date_obj.day:02d}"

# --- [核心邏輯] 班級判定 (只保留托嬰到大班) ---
def get_grade_for_year(birth_date, target_school_year_roc):
    birth_year_roc = birth_date.year - 1911
    
    # 9/2 分界邏輯
    offset = 0
    if (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2):
        offset = 1
        
    # 計算學齡
    age_in_school = target_school_year_roc - birth_year_roc - offset

    # 依照您的要求，簡化分類
    if age_in_school >= 6: return "畢業/超齡"
    if age_in_school == 5: return "大班"
    if age_in_school == 4: return "中班"
    if age_in_school == 3: return "小班"
    if age_in_school == 2: return "幼幼班"
    # 2歲以下全部歸類為托嬰
    return "托嬰中心"

# --- 讀取/儲存 ---
def load_data(filename, columns):
    if os.path.exists(filename):
        return pd.read_csv(filename)
    else:
        return pd.DataFrame(columns=columns)

def save_data(df, filename):
    df.to_csv(filename, index=False, encoding='utf-8-sig')

# --- 網頁主程式 ---
st.set_page_config(page_title="幼兒園新生管理系統", layout="wide")
st.title("🏫 幼兒園新生管理系統")

menu = st.sidebar.radio("功能導航", ["目前學生管理", "新生報名與排程", "師資需求計算"])

# ==========================================
# 功能 1: 目前學生管理
# ==========================================
if menu == "目前學生管理":
    st.header("👦👧 目前學生管理")

    df_students = load_data(STUDENT_FILE, ['姓名', '出生年月日', '目前班級', '備註'])

    # 統計看板
    st.subheader("📊 人數統計")
    if not df_students.empty:
        counts = df_students['目前班級'].value_counts()
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("大班", f"{counts.get('大班', 0)}")
        c2.metric("中班", f"{counts.get('中班', 0)}")
        c3.metric("小班", f"{counts.get('小班', 0)}")
        c4.metric("幼幼班", f"{counts.get('幼幼班', 0)}")
        c5.metric("托嬰", f"{counts.get('托嬰中心', 0)}")
    else:
        st.info("尚無資料")

    st.divider()

    st.subheader("➕ 新增在校生")
    with st.form("add_student"):
        col1, col2 = st.columns(2)
        name = col1.text_input("學生姓名")
        
        # 使用自製的民國選擇器
        with col2:
            dob = roc_date_input("出生年月日", date(2020, 1, 1), key_suffix="student")
        
        # 自動判斷
        today = date.today()
        current_roc_year = today.year - 1911
        if today.month < 8: current_roc_year -= 1
        
        current_grade = get_grade_for_year(dob, current_roc_year)
        st.info(f"💡 系統判定：目前 ({current_roc_year}學年度) 為 **{current_grade}**")

        note = st.text_input("備註")
        
        if st.form_submit_button("確認新增"):
            if name:
                new_data = pd.DataFrame([{
                    '姓名': name, 
                    '出生年月日': dob, 
                    '目前班級': current_grade, 
                    '備註': note
                }])
                df_students = pd.concat([df_students, new_data], ignore_index=True)
                save_data(df_students, STUDENT_FILE)
                st.success(f"已新增 {name}")
                st.rerun()

    st.subheader("📋 學生名單")
    if not df_students.empty:
        display_df = df_students.copy()
        display_df['出生年月日'] = display_df['出生年月日'].apply(to_roc_date_str)
        st.dataframe(display_df, use_container_width=True)

# ==========================================
# 功能 2: 新生報名與排程
# ==========================================
elif menu == "新生報名與排程":
    st.header("📝 新生報名與入學規劃")
    
    df_reg = load_data(REGISTRATION_FILE, ['報名日期', '家長姓名', '幼兒姓名', '幼兒生日', '預計入學學年', '預計入學班級', '電話'])

    # --- 1. 未來入學試算區 ---
    st.markdown("### 📅 入學時程試算 (全民國顯示)")
    
    col_cal, col_info = st.columns([1, 2])
    with col_cal:
        # 使用自製的民國選擇器
        dob_reg = roc_date_input("請選擇幼兒生日", date(2021, 9, 2), key_suffix="reg_calc")
        
    today = date.today()
    this_roc_year = today.year - 1911
    if today.month < 8: this_roc_year -= 1
    
    roadmap_data = []
    # 顯示未來 4 年
    for i in range(0, 4): 
        target_year = this_roc_year + i
        grade = get_grade_for_year(dob_reg, target_year)
        
        # 只顯示在範圍內的班級 (不顯示超齡，也不顯示還沒出生的狀況)
        if grade != "畢業/超齡":
            roadmap_data.append({
                "學年度 (民國)": f"{target_year} 學年",
                "入學時間": f"民國{target_year}年 8月",
                "對應班級": grade,
                "狀態": "✅ 招生中" if i==0 else "⏳ 預約"
            })
    
    roadmap_df = pd.DataFrame(roadmap_data)
    
    with col_info:
        if not roadmap_df.empty:
            st.table(roadmap_df)
        else:
            st.warning("此幼兒年齡已超過幼兒園範圍。")

    st.divider()

    # --- 2. 正式報名表單 ---
    st.subheader("✍️ 填寫報名資料")
    with st.form("reg_form"):
        col1, col2 = st.columns(2)
        p_name = col1.text_input("家長姓名")
        c_name = col2.text_input("幼兒姓名")
        phone = col1.text_input("聯絡電話")
        
        # 選單邏輯
        if not roadmap_df.empty:
            options = roadmap_df['學年度 (民國)'] + " - " + roadmap_df['對應班級']
            target_year_str = col2.selectbox("欲登記之入學時間", options)
        else:
            target_year_str = col2.selectbox("欲登記之入學時間", ["無符合班級"])
            
        if st.form_submit_button("提交報名"):
            if p_name and c_name and target_year_str != "無符合班級":
                target_academic_year = target_year_str.split(" - ")[0]
                target_grade_class = target_year_str.split(" - ")[1]
                
                new_reg = pd.DataFrame([{
                    '報名日期': to_roc_date_str(date.today()),
                    '家長姓名': p_name, 
                    '幼兒姓名': c_name, 
                    '幼兒生日': to_roc_date_str(dob_reg),
                    '預計入學學年': target_academic_year,
                    '預計入學班級': target_grade_class,
                    '電話': phone
                }])
                df_reg = pd.concat([df_reg, new_reg], ignore_index=True)
                save_data(df_reg, REGISTRATION_FILE)
                st.success(f"已登記：{c_name} -> {target_academic_year} {target_grade_class}")
                st.rerun()
            elif target_year_str == "無符合班級":
                st.error("年齡不符，無法報名")
            else:
                st.error("請填寫姓名")

    st.subheader("📞 候補名單")
    st.dataframe(df_reg, use_container_width=True)

# ==========================================
# 功能 3: 師資需求計算
# ==========================================
elif menu == "師資需求計算":
    st.header("👩‍🏫 師資人力規劃")
    df_students = load_data(STUDENT_FILE, ['目前班級'])
    counts = df_students['目前班級'].value_counts() if not df_students.empty else {}

    col1, col2 = st.columns(2)
    r_norm = col1.number_input("大中小班 師生比 (1:X)", value=15)
    r_tod = col2.number_input("幼幼/托嬰 師生比 (1:X)", value=5, help="通常托嬰為1:5，幼幼1:8")

    data = []
    total = 0
    # 這裡也移除了國小
    class_order = [('大班', r_norm), ('中班', r_norm), ('小班', r_norm), ('幼幼班', r_tod), ('托嬰中心', r_tod)]
    
    for grade, r in class_order:
        n = counts.get(grade, 0)
        t = math.ceil(n / r) if n > 0 else 0
        total += t
        data.append({"班級": grade, "學生": n, "師生比": f"1:{r}", "需老師": t})

    st.table(pd.DataFrame(data))
    st.info(f"全園共需：{total} 位老師")
