import streamlit as st
import pandas as pd
from datetime import date, datetime
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 🔒 安全鎖
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if not st.session_state.password_correct:
        st.title("🔒 請登入新生管理系統")
        password = st.text_input("請輸入通關密碼", type="password")
        if st.button("登入"):
            if password == "1234": 
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("密碼錯誤")
        return False
    return True

if not check_password():
    st.stop()

# ==========================================
# ⚙️ 設定與連線
# ==========================================
SHEET_NAME = 'kindergarten_db'
STUDENT_CSV = 'students.csv'

def connect_to_gsheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def load_registered_data():
    try:
        sheet = connect_to_gsheets()
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame()
        return df
    except:
        return pd.DataFrame()

def load_current_students():
    try:
        return pd.read_csv(STUDENT_CSV)
    except:
        return pd.DataFrame(columns=['姓名', '出生年月日', '目前班級'])

def sync_data_to_gsheets(new_df):
    try:
        sheet = connect_to_gsheets()
        save_df = new_df.copy()
        if '已聯繫' in save_df.columns:
            save_df['聯繫狀態'] = save_df['已聯繫'].apply(lambda x: '已聯繫' if x else '未聯繫')
            save_df = save_df.drop(columns=['已聯繫'])
        
        final_cols = ['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註']
        for col in final_cols:
            if col not in save_df.columns: save_df[col] = ""
        save_df = save_df[final_cols]
        sheet.clear()
        sheet.append_row(final_cols)
        if not save_df.empty:
            sheet.append_rows(save_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"儲存失敗: {e}")
        return False

# ==========================================
# 🧠 核心邏輯
# ==========================================
def roc_date_input(label, default_date=None):
    st.markdown(f"**{label}**")
    c1, c2, c3 = st.columns([1, 1, 1])
    if default_date is None: default_date = date.today()
    roc_year = c1.number_input("民國(年)", 100, 120, default_date.year - 1911)
    month = c2.selectbox("月", range(1, 13), index=default_date.month-1)
    day = c3.selectbox("日", range(1, 32), index=default_date.day-1)
    try: return date(roc_year + 1911, month, day)
    except: return date.today()

def to_roc_str(d):
    return f"{d.year-1911}/{d.month:02d}/{d.day:02d}"

def get_grade_for_year(birth_date, target_roc_year):
    if birth_date is None: return "未知"
    birth_year_roc = birth_date.year - 1911
    offset = 1 if (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2) else 0
    age = target_roc_year - birth_year_roc - offset
    if age < 2: return "托嬰中心"
    if age == 2: return "幼幼班"
    if age == 3: return "小班"
    if age == 4: return "中班"
    if age == 5: return "大班"
    return "畢業/超齡"

def calculate_admission_roadmap(dob):
    today = date.today()
    current_roc = today.year - 1911
    if today.month < 8: current_roc -= 1
    offset = 1 if (dob.month > 9) or (dob.month == 9 and dob.day >= 2) else 0
    roadmap = []
    for i in range(4): 
        target = current_roc + i
        age = target - (dob.year - 1911) - offset
        if age == 2: grade = "幼幼班"
        elif age == 3: grade = "小班"
        elif age == 4: grade = "中班"
        elif age == 5: grade = "大班"
        elif age < 2: grade = "托嬰中心"
        else: grade = "畢業/超齡"
        if "畢業" not in grade:
            roadmap.append(f"{target} 學年 - {grade}")
    return roadmap

# ==========================================
# 📱 APP 介面
# ==========================================
st.set_page_config(page_title="新生管理系統", layout="wide")
st.title("🏫 新生管理系統")

menu = st.sidebar.radio("系統切換", ["👶 新生報名管理", "👩‍🏫 師生人力預估系統"])

if menu == "👶 新生報名管理":
    if 'df_cache' not in st.session_state:
        st.session_state.df_cache = load_registered_data()
        
    df = st.session_state.df_cache
    if not df.empty and '聯繫狀態' not in df.columns: df['聯繫狀態'] = '未聯繫'
    if not df.empty and '報名狀態' not in df.columns: df['報名狀態'] = '排隊候補'
    if not df.empty: df['已聯繫'] = df['聯繫狀態'] == '已聯繫'

    tab1, tab2 = st.tabs(["➕ 新增報名", "📊 招生管理儀表板"]) # 改名，聽起來比較厲害

    with tab1:
        col_main, col_roadmap = st.columns([1, 1])
        with col_main:
            st.subheader("輸入資料")
            st.markdown("##### 📌 報名狀態")
            status = st.selectbox("狀態判定", ["排隊候補", "已確認/已繳費", "考慮中/參觀"], index=0)
            
            child_name = st.text_input("幼兒姓名 (選填)")
            dob = roc_date_input("幼兒生日", date(2021, 9, 2))
            
            c1, c2 = st.columns(2)
            p_name = c1.text_input("家長姓氏 (必填)")
            p_title = c2.selectbox("稱謂", ["先生", "小姐", "爸爸", "媽媽"])
            phone = st.text_input("聯絡電話 (必填)")
            referrer = st.text_input("推薦人 (選填)")

        with col_roadmap:
            st.subheader("入學年段判定")
            options = calculate_admission_roadmap(dob)
            if options:
                st.info("家長預計登記之年段：")
                selected_plan = st.radio("請選擇方案", options)
            else:
                st.warning("年齡不符")
                selected_plan = "不符資格"
        
        st.divider()
        note = st.text_area("備註事項 (選填)", placeholder="例如：雙胞胎、過敏...")

        if st.button("提交並儲存", type="primary"):
            if p_name and phone and selected_plan != "不符資格":
                current_df = load_registered_data()
                final_child_name = child_name if child_name else ""
                new_row = pd.DataFrame([{
                    '報名狀態': status,
                    '已聯繫': False,
                    '登記日期': to_roc_str(date.today()),
                    '幼兒姓名': final_child_name,
                    '家長稱呼': f"{p_name} {p_title}",
                    '電話': phone,
                    '幼兒生日': to_roc_str(dob),
                    '預計入學資訊': selected_plan,
                    '推薦人': referrer,
                    '備註': note
                }])
                updated_df = pd.concat([current_df, new_row], ignore_index=True)
                if sync_data_to_gsheets(updated_df):
                    st.success(f"✅ 已新增資料 (家長：{p_name} {p_title})")
                    st.session_state.df_cache = load_registered_data()
                    st.rerun()
            else:
                st.error("❌ 請確認「家長姓氏」與「電話」已填寫")

    with tab2:
        # ==========================================
        # ✨ 專業級儀表板設計
        # ==========================================
        st.subheader("📊 招生戰情中心")
        
        if not df.empty:
            # 1. 關鍵指標 (KPI Cards)
            # 計算數據
            total_count = len(df)
            uncontacted_count = len(df[df['已聯繫'] == False])
            confirmed_count = len(df[df['報名狀態'].str.contains("已確認") | df['報名狀態'].str.contains("繳費")])
            waitlist_count = len(df[df['報名狀態'].str.contains("排隊")])

            # 顯示漂亮的指標卡
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("總登記人數", total_count, help="目前資料庫總筆數")
            kpi2.metric("待聯繫", uncontacted_count, delta=f"-{uncontacted_count} 需處理", delta_color="inverse", help="尚未聯繫的家長")
            kpi3.metric("已確認入學", confirmed_count, "🎉", help="已繳費或確認就讀")
            kpi4.metric("排隊候補中", waitlist_count, help="潛在生源")

            st.divider()

            # 2. 智慧工具列 (搜尋 + 匯出)
            col_tool1, col_tool2 = st.columns([3, 1])
            with col_tool1:
                # 搜尋功能
                search_query = st.text_input("🔍 搜尋資料", placeholder="輸入幼兒姓名、家長或電話...")
            
            with col_tool2:
                # 匯出按鈕
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 下載 Excel (CSV)",
                    data=csv,
                    file_name='kindergarten_data.csv',
                    mime='text/csv',
                    use_container_width=True
                )

            # 3. 資料篩選邏輯
            # 如果有輸入搜尋文字，就過濾資料
            display_df = df.copy()
            if search_query:
                display_df = display_df[
                    display_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
                ]

            # 4. 專業表格顯示
            cols_config = {
                "已聯繫": st.column_config.CheckboxColumn("已聯繫", width="small"),
                "報名狀態": st.column_config.SelectboxColumn(
                    "報名狀態", 
                    options=["排隊候補", "已確認/已繳費", "考慮中/參觀"], 
                    width="medium",
                    required=True
                ),
                "幼兒姓名": st.column_config.TextColumn("幼兒姓名", width="small"),
                "預計入學資訊": st.column_config.TextColumn("入學年段", width="medium"),
                "備註": st.column_config.TextColumn("備註", width="large"),
                "電話": st.column_config.TextColumn("電話", width="medium"),
            }
            
            # 調整欄位順序，符合行政閱讀習慣
            main_cols = ['已聯繫', '報名狀態', '預計入學資訊', '幼兒姓名', '家長稱呼', '電話', '推薦人', '備註']
            # 補齊可能缺少的欄位
            for c in main_cols:
                if c not in display_df.columns: display_df[c] = ""

            st.caption(f"共顯示 {len(display_df)} 筆資料。可以直接在表格修改狀態，修改後請按下方的「儲存變更」。")
            
            edit_df = st.data_editor(
                display_df[main_cols],
                column_config=cols_config,
                hide_index=True,
                use_container_width=True,
                num_rows="fixed", # 固定行數，避免誤按新增
                height=400 # 設定高度，讓畫面更有質感
            )
            
            st.write("") # 空行

            # 5. 底部操作區
            col_del, col_save = st.columns([2, 1])
            with col_del:
                # 刪除選單
                del_options = edit_df.apply(
                    lambda x: f"{x['幼兒姓名'] if x['幼兒姓名'] else '(未填)'} | {x['家長稱呼']} | {x['電話']}", 
                    axis=1
                ).tolist()
                delete_list = st.multiselect("🗑️ 批次刪除 (可多選)", del_options)
            
            with col_save:
                # 儲存按鈕
                if st.button("💾 確認儲存所有變更", type="primary", use_container_width=True):
                    # 這裡需要把 edit_df (可能經過搜尋篩選) 的變更，合併回原始 df
                    # 邏輯：利用電話+家長稱呼作為 key 來更新 (假設這兩個同時重複機率低)
                    # 為了最安全，我們更新整個原始 df
                    
                    full_df = df.copy()
                    
                    # 逐行更新
                    for idx, row in edit_df.iterrows():
                        # 因為 edit_df 經過篩選，index 可能跟 full_df 不同
                        # 所以我們用原始資料的 index (如果沒經過篩選，index是一樣的)
                        # 如果經過篩選，我們需要更聰明的對應方式
                        # 簡單做法：我們在 data_editor 之前不重設 index，這樣 index 會保留
                        if idx in full_df.index:
                            full_df.at[idx, '報名狀態'] = row['報名狀態']
                            full_df.at[idx, '已聯繫'] = row['已聯繫']
                            full_df.at[idx, '備註'] = row['備註']
                            full_df.at[idx, '幼兒姓名'] = row['幼兒姓名']
                    
                    final_df = full_df.copy()
                    
                    # 處理刪除
                    if delete_list:
                        final_df['id_temp'] = final_df.apply(
                            lambda x: f"{x['幼兒姓名'] if x['幼兒姓名'] else '(未填)'} | {x['家長稱呼']} | {x['電話']}", 
                            axis=1
                        )
                        final_df = final_df[~final_df['id_temp'].isin(delete_list)]
                        final_df = final_df.drop(columns=['id_temp'])
                    
                    if sync_data_to_gsheets(final_df):
                        st.success("✅ 儲存成功！資料庫已更新")
                        st.session_state.df_cache = load_registered_data()
                        st.rerun()
        else:
            st.info("目前無資料，請至「新增報名」頁籤輸入。")

elif menu == "👩‍🏫 師生人力預估系統":
    st.header("📊 未來學年師生人力預估")
    st.info("💡 這裡將「已確認」與「排隊中」的人數分開計算，讓您評估人力需求的範圍。")

    with st.expander("⚙️ 師生比參數設定", expanded=False):
        c1, c2, c3 = st.columns(3)
        ratio_daycare = c1.number_input("托嬰 (0-2歲)", value=5)
        ratio_toddler = c2.number_input("幼幼 (2-3歲)", value=8)
        ratio_normal = c3.number_input("小/中/大 (3-6歲)", value=15)

    df_current = load_current_students() 
    df_new = load_registered_data()
    if not df_new.empty and '報名狀態' not in df_new.columns: df_new['報名狀態'] = '排隊候補'

    today = date.today()
    this_roc_year = today.year - 1911
    if today.month < 8: this_roc_year -= 1
    
    target_years = st.multiselect("請選擇預估學年", [this_roc_year+1, this_roc_year+2, this_roc_year+3], default=[this_roc_year+1])

    if target_years:
        st.divider()
        for year in sorted(target_years):
            st.subheader(f"📅 民國 {year} 學年度")
            confirmed_counts = {"托嬰中心": 0, "幼幼班": 0, "小班": 0, "中班": 0, "大班": 0}
            waitlist_counts = {"托嬰中心": 0, "幼幼班": 0, "小班": 0, "中班": 0, "大班": 0}
            
            if not df_current.empty:
                for _, row in df_current.iterrows():
                    try:
                        dob_obj = datetime.strptime(str(row['出生年月日']), "%Y-%m-%d").date()
                        grade = get_grade_for_year(dob_obj, year)
                        if grade in confirmed_counts: confirmed_counts[grade] += 1
                    except: pass

            if not df_new.empty:
                for _, row in df_new.iterrows():
                    plan_str = str(row['預計入學資訊'])
                    status = str(row['報名狀態'])
                    
                    if f"{year} 學年" in plan_str:
                        target_grade = None
                        if "幼幼班" in plan_str: target_grade = "幼幼班"
                        elif "小班" in plan_str: target_grade = "小班"
                        elif "中班" in plan_str: target_grade = "中班"
                        elif "大班" in plan_str: target_grade = "大班"
                        elif "托嬰" in plan_str: target_grade = "托嬰中心"
                        
                        if target_grade:
                            if "已確認" in status or "繳費" in status: confirmed_counts[target_grade] += 1
                            else: waitlist_counts[target_grade] += 1

            data = []
            total_teachers_min = 0
            total_teachers_max = 0
            class_rules = [("托嬰中心", ratio_daycare), ("幼幼班", ratio_toddler), ("小班", ratio_normal), ("中班", ratio_normal), ("大班", ratio_normal)]
            
            for grade, ratio in class_rules:
                base = confirmed_counts[grade]
                wait = waitlist_counts[grade]
                total_possible = base + wait
                tea_min = math.ceil(base / ratio) if base > 0 else 0
                tea_max = math.ceil(total_possible / ratio) if total_possible > 0 else 0
                total_teachers_min += tea_min
                total_teachers_max += tea_max
                
                data.append({
                    "班級": grade,
                    "師生比": f"1:{ratio}",
                    "已確認人數": base,
                    "排隊/考慮": wait,
                    "預估總人數": total_possible,
                    "需老師": f"{tea_min} ~ {tea_max} 位"
                })
            
            st.dataframe(pd.DataFrame(data), use_container_width=True)
            st.caption(f"💡 結論：老師需求介於 **{total_teachers_min}** ~ **{total_teachers_max}** 位")
            st.divider()
    else:
        st.info("請選擇學年。")
