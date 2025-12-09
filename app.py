import streamlit as st
import pandas as pd
import math
import os
from datetime import date, datetime

# --- 設定資料庫檔案名稱 ---
STUDENT_FILE = 'students.csv'
REGISTRATION_FILE = 'registrations.csv'

# --- [工具函式] 西元轉民國字串 ---
# 為了讓資料表顯示民國，我們需要把 date 物件轉成字串
def to_roc_date_str(date_obj):
    if pd.isnull(date_obj): return ""
    # 如果傳進來的是字串，嘗試轉換
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.strptime(date_obj, "%Y-%m-%d").date()
        except:
            return date_obj # 轉不過就回傳原樣
            
    roc_year = date_obj.year - 1911
    return f"{roc_year}/{date_obj.month:02d}/{date_obj.day:02d}"

# --- [核心邏輯] 判斷某個學年度，這孩子該讀什麼班 ---
def get_grade_for_year(birth_date, target_school_year_roc):
    """
    輸入：孩子生日, 目標學年度(民國)
    輸出：該學年度他應該讀什麼班
    邏輯：台灣學制 9/2 切分
    """
    birth_year_roc = birth_date.year - 1911
    
    # 判斷是否為「屆齡」的調整
    # 如果是 9/2 (含) 以後出生，算是下一個年級，入學年齡要往後推一年
    offset = 0
    if (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2):
        offset = 1
        
    # 計算該學年度時，孩子的「學齡」
    # 學齡 = 學年度 - 出生年 - offset
    # 舉例：108/10/1出生 (offset=1)。在 113學年度時：
    # 113 - 108 - 1 = 4歲 (中班) -> 正確
    age_in_school = target_school_year_roc - birth_year_roc - offset

    if age_in_school >= 6: return "國小/畢業"
    if age_in_school == 5: return "大班"
    if age_in_school == 4: return "中班"
    if age_in_school == 3: return "小班"
    if age_in_school == 2: return "幼幼班"
    if age_in_school < 2: return "未足齡(托嬰)"
    return "未知"

# --- 讀取資料函式 (讀進來後不做轉換，顯示時再轉) ---
def load_data(filename, columns):
    if os.path.exists(filename):
        return pd.read_csv(filename)
    else:
        return pd.DataFrame(columns=columns)

# --- 儲存資料函式 ---
def save_data(df, filename):
    df.to_csv(filename, index=False, encoding='utf-8-sig')

# --- 網頁設定 ---
st.set_page_config(page_title="幼兒園新生管理系統", layout="wide")
st.title("🏫 幼兒園新生管理系統")

# --- 側邊欄選單 ---
menu = st.sidebar.radio(
    "功能導航",
    ["目前學生管理", "新生報名與排程", "師資需求計算"]
)

# ==========================================
# 功能 1: 目前學生管理
# ==========================================
if menu == "目前學生管理":
    st.header("👦👧 目前學生管理")

    df_students = load_data(STUDENT_FILE, ['姓名', '出生年月日', '目前班級', '備註'])

    # --- 統計看板 ---
    st.subheader("📊 人數統計")
    if not df_students.empty:
        counts = df_students['目前班級'].value_counts()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("大班", f"{counts.get('大班', 0)}")
        c2.metric("中班", f"{counts.get('中班', 0)}")
        c3.metric("小班", f"{counts.get('小班', 0)}")
        c4.metric("幼幼班", f"{counts.get('幼幼班', 0)}")
    else:
        st.info("尚無資料")

    st.divider()

    # --- 新增學生 ---
    st.subheader("➕ 新增在校生")
    with st.form("add_student"):
        col1, col2 = st.columns(2)
        name = col1.text_input("學生姓名")
        
        # 日期選擇器 (為了手機好選，還是用西元介面，但下方顯示民國)
        default_dob = date(2020, 1, 1)
        dob = col2.date_input("出生年月日 (選單為西元)", default_dob)
        st.caption(f"轉換民國：{to_roc_date_str(dob)}")
        
        # 自動判斷「目前(今年)」的班級
        today = date.today()
        current_roc_year = today.year - 1911
        if today.month < 8: current_roc_year -= 1 # 8月前還算上一學年
        
        current_grade = get_grade_for_year(dob, current_roc_year)
        st.info(f"💡 系統判定：目前 ({current_roc_year}學年度) 應為 **{current_grade}**")

        note = st.text_input("備註")
        
        if st.form_submit_button("確認新增"):
            if name:
                new_data = pd.DataFrame([{
                    '姓名': name, 
                    '出生年月日': dob,  # 存檔存西元格式方便計算
                    '目前班級': current_grade, 
                    '備註': note
                }])
                df_students = pd.concat([df_students, new_data], ignore_index=True)
                save_data(df_students, STUDENT_FILE)
                st.success(f"已新增 {name}")
                st.rerun()

    # --- 顯示清單 (將西元轉民國顯示) ---
    st.subheader("📋 學生名單")
    if not df_students.empty:
        # 複製一份來顯示，不影響原始資料
        display_df = df_students.copy()
        # 把出生年月日那一欄，全部套用轉民國函式
        display_df['出生年月日'] = display_df['出生年月日'].apply(to_roc_date_str)
        st.dataframe(display_df, use_container_width=True)

# ==========================================
# 功能 2: 新生報名與排程 (核心功能更新！)
# ==========================================
elif menu == "新生報名與排程":
    st.header("📝 新生報名與入學規劃")
    
    df_reg = load_data(REGISTRATION_FILE, ['報名日期', '家長姓名', '幼兒姓名', '幼兒生日', '預計入學學年', '預計入學班級', '電話'])

    # --- 1. 未來入學試算區 ---
    st.markdown("### 📅 入學時程試算 (給家長看)")
    st.info("輸入生日後，系統會列出該幼兒未來幾年的入學班級，方便您安排候補。")
    
    col_cal, col_info = st.columns([1, 2])
    with col_cal:
        dob_reg = st.date_input("請選擇幼兒生日", date(2021, 1, 1))
        st.write(f"**民國 {to_roc_date_str(dob_reg)} 出生**")

    # 計算未來 5 年的落點
    today = date.today()
    this_roc_year = today.year - 1911
    if today.month < 8: this_roc_year -= 1
    
    # 建立預測表
    roadmap_data = []
    for i in range(0, 4): # 顯示今、明、後、大後年
        target_year = this_roc_year + i
        grade = get_grade_for_year(dob_reg, target_year)
        # 西元年月
        west_year_start = target_year + 1911
        roadmap_data.append({
            "學年度 (民國)": f"{target_year} 學年",
            "入學時間": f"民國{target_year}年 8月",
            "對應班級": grade,
            "狀態": "✅ 目前招生中" if i==0 else "⏳ 預約候補"
        })
    
    roadmap_df = pd.DataFrame(roadmap_data)
    
    # 在右側顯示漂亮的表格
    with col_info:
        st.table(roadmap_df)

    st.divider()

    # --- 2. 正式報名表單 ---
    st.subheader("✍️ 填寫報名資料")
    with st.form("reg_form"):
        col1, col2 = st.columns(2)
        p_name = col1.text_input("家長姓名")
        c_name = col2.text_input("幼兒姓名")
        phone = col1.text_input("聯絡電話")
        
        # 讓使用者選擇要登記哪一年
        target_year_str = col2.selectbox(
            "欲登記之入學時間", 
            roadmap_df['學年度 (民國)'] + " - " + roadmap_df['對應班級']
        )
        
        # 解析選單字串，存入乾淨的資料
        # 例如選了 "115 學年 - 小班"，我們要拆開存
        target_academic_year = target_year_str.split(" - ")[0]
        target_grade_class = target_year_str.split(" - ")[1]

        if st.form_submit_button("提交報名"):
            if p_name and c_name:
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
                st.success(f"已登記：{c_name} 預計於 {target_academic_year} 就讀 {target_grade_class}")
                st.rerun()

    # --- 3. 顯示待聯絡清單 ---
    st.subheader("📞 候補/待聯絡名單")
    st.dataframe(df_reg, use_container_width=True)


# ==========================================
# 功能 3: 師資需求計算
# ==========================================
elif menu == "師資需求計算":
    st.header("👩‍🏫 師資人力規劃")
    
    # 讀取目前學生
    df_students = load_data(STUDENT_FILE, ['目前班級'])
    counts = df_students['目前班級'].value_counts() if not df_students.empty else {}

    col1, col2 = st.columns(2)
    r_norm = col1.number_input("大中小班 師生比 (1:X)", value=15)
    r_tod = col2.number_input("幼幼班 師生比 (1:X)", value=8)

    data = []
    total = 0
    for grade, r in [('大班', r_norm), ('中班', r_norm), ('小班', r_norm), ('幼幼班', r_tod)]:
        n = counts.get(grade, 0)
        t = math.ceil(n / r) if n > 0 else 0
        total += t
        data.append({"班級": grade, "學生": n, "師生比": f"1:{r}", "需老師": t})

    st.table(pd.DataFrame(data))
    st.info(f"全園共需：{total} 位老師")
