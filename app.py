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
        # [修正] 強制將所有資料先讀成字串，避免電話號碼被當成數字去頭
        data = sheet.get_all_values()
        if not data: return pd.DataFrame()
        
        # 第一列是標題，下面是資料
        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        
        # [修正] 電話號碼補 0 機制
        if '電話' in df.columns:
            # 去除空白
            df['電話'] = df['電話'].astype(str).str.strip()
            # 如果是 9 碼且開頭是 9，自動補 0 (針對台灣手機)
            df['電話'] = df['電話'].apply(lambda x: '0' + x if len(x) == 9 and x.startswith('9') else x)
            
        return df
    except Exception as e:
        # st.error(f"讀取錯誤: {e}") 
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
        
        # 處理勾選框
        if '已聯繫' in save_df.columns:
            save_df['聯繫狀態'] = save_df['已聯繫'].apply(lambda x: '已聯繫' if x is True else '未聯繫')
            save_df = save_df.drop(columns=['已聯繫'])
        
        # [調整] 確保欄位順序與完整性 (這裡決定了 Google Sheet 存檔的順序)
        final_cols = ['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註']
        
        for col in final_cols:
            if col not in save_df.columns: save_df[col] = ""
            
        save_df = save_df[final_cols]
        
        # 轉成字串防止存檔時格式跑掉
        save_df = save_df.astype(str)
        
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
    
    # [修正] 確保已聯繫欄位是布林值 (Boolean)，解決報錯關鍵
    if not df.empty:
        df['已聯繫'] = df['聯繫狀態'].apply(lambda x: True if str(x).strip() == '已聯繫' else False)

    tab1, tab2 = st.tabs(["➕ 新增報名", "📊 戰情管理儀表板"])

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
                    '電話': str(phone), # 強制轉字串
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
        st.subheader("📊 招生戰情中心")
        
        if not df.empty:
            total_count = len(df)
            uncontacted_count = len(df[df['已聯繫'] == False])
            confirmed_count = len(df[df['報名狀態'].str.contains("已確認") | df['報名狀態'].str.contains("繳費")])
            waitlist_count = len(df[df['報名狀態'].str.contains("排隊")])

            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("總登記人數", total_count)
            kpi2.metric("待聯繫", uncontacted_count, delta=f"-{uncontacted_count} 需處理", delta_color="inverse")
            kpi3.metric("已確認入學", confirmed_count, "🎉")
            kpi4.metric("排隊候補中", waitlist_count)

            st.divider()

            col_tool1, col_tool2 = st.columns([3, 1])
            with col_tool1:
                search_query = st.text_input("🔍 搜尋資料", placeholder="輸入姓名、電話或備註...")
            
            with col_tool2:
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 下載 Excel", data=csv, file_name='kindergarten_data.csv', mime='text/csv', use_container_width=True)

            display_df = df.copy()
            if search_query:
                display_df = display_df[
                    display_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
                ]

            # [調整] 這裡是你要求的欄位順序：幼兒資料放到後面
            main_cols = [
                '已聯繫', 
                '報名狀態', 
                '登記日期',       # [新增]
                '預計入學資訊', 
                '家長稱呼', 
                '電話', 
                '推薦人', 
                '備註',
                '幼兒生日',       # [新增] 
                '幼兒姓名'        # [移動] 到最後
            ]
            
            for c in main_cols:
                if c not in display_df.columns: display_df[c] = ""
            
            # 確保電話是字串，才不會被當成數字去掉0
            display_df['電話'] = display_df['電話'].astype(str)

            # [修正] 設定 column_config 避免報錯，並解決電話 0 不見的問題
            cols_config = {
                "已聯繫": st.column_config.CheckboxColumn("已聯繫", width="small", default=False),
                "報名狀態": st.column_config.SelectboxColumn("報名狀態", options=["排隊候補", "已確認/已繳費", "考慮中/參觀"], width="medium", required=True),
                # 使用 TextColumn 強制電話顯示為文字
                "電話": st.column_config.TextColumn("電話", width="medium", help="聯絡電話"),
                "預計入學資訊": st.column_config.TextColumn("入學年段", width="medium"),
                "備註": st.column_config.TextColumn("備註", width="large"),
                "登記日期": st.column_config.TextColumn("登記日期", width="small"),
                "幼兒生日": st.column_config.TextColumn("幼兒生日", width="small"),
            }
            
            st.caption(f"共顯示 {len(display_df)} 筆資料。")
            
            edit_df = st.data_editor(
                display_df[main_cols],
                column_config=cols_config,
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                height=400
            )
            
            col_del, col_save = st.columns([2, 1])
            with col_del:
                del_options = edit_df.apply(
                    lambda x: f"{x['家長稱呼']} | {x['電話']} | {x['幼兒姓名']}", 
                    axis=1
                ).tolist()
                delete_list = st.multiselect("🗑️ 批次刪除", del_options)
            
            with col_save:
                if st.button("💾 確認儲存變更", type="primary", use_container_width=True):
                    full_df = df.copy()
                    
                    # 更新邏輯
                    for idx, row in edit_df.iterrows():
                        if idx in full_df.index:
                            full_df.at[idx, '報名狀態'] = row['報名狀態']
                            full_df.at[idx, '已聯繫'] = row['已聯繫']
                            full_df.at[idx, '備註'] = row['備註']
                            full_df.at[idx, '幼兒姓名'] = row['幼兒姓名'] # 允許補登
                            # 注意：data_editor 如果沒改動，電話會保持原樣，如果改動，會傳回字串
                    
                    final_df = full_df.copy()
                    
                    if delete_list:
                        final_df['id_temp'] = final_df.apply(
                            lambda x: f"{x['家長稱呼']} | {x['電話']} | {x['幼兒姓名']}", 
                            axis=1
                        )
                        final_df = final_df[~final_df['id_temp'].isin(delete_list)]
                        final_df = final_df.drop(columns=['id_temp'])
                    
                    if sync_data_to_gsheets(final_df):
                        st.success("✅ 儲存成功！")
                        st.session_state.df_cache = load_registered_data()
                        st.rerun()
        else:
            st.info("目前無資料。")

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
