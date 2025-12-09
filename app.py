import streamlit as st
import pandas as pd
from datetime import date, datetime
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

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

@st.cache_resource
def get_gsheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def connect_to_gsheets():
    client = get_gsheet_client()
    return client.open(SHEET_NAME).sheet1

@st.cache_data(ttl=60)
def load_registered_data():
    try:
        sheet = connect_to_gsheets()
        data = sheet.get_all_values()
        if not data: return pd.DataFrame()
        
        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        
        if '電話' in df.columns:
            df['電話'] = df['電話'].astype(str).str.strip()
            df['電話'] = df['電話'].apply(lambda x: '0' + x if len(x) == 9 and x.startswith('9') else x)
            
        return df
    except Exception as e:
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
            save_df['聯繫狀態'] = save_df['已聯繫'].apply(lambda x: '已聯繫' if x is True else '未聯繫')
            save_df = save_df.drop(columns=['已聯繫'])
        
        final_cols = ['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註']
        
        for col in final_cols:
            if col not in save_df.columns: save_df[col] = ""
            
        save_df = save_df[final_cols]
        save_df = save_df.astype(str)
        
        sheet.clear()
        sheet.append_row(final_cols)
        if not save_df.empty:
            sheet.append_rows(save_df.values.tolist())
            
        load_registered_data.clear()
        return True
    except Exception as e:
        st.error(f"儲存失敗: {e}")
        return False

# ==========================================
# 🧠 核心邏輯
# ==========================================
def roc_date_input(label, default_date=None, key_suffix=""):
    st.markdown(f"**{label}**")
    c1, c2, c3 = st.columns([1, 1, 1])
    if default_date is None: default_date = date.today()
    
    k_y = f"year_{key_suffix}"
    k_m = f"month_{key_suffix}"
    k_d = f"day_{key_suffix}"
    
    roc_year = c1.selectbox("民國(年)", range(100, 121), index=(default_date.year - 1911) - 100, key=k_y)
    month = c2.selectbox("月", range(1, 13), index=default_date.month-1, key=k_m)
    day = c3.selectbox("日", range(1, 32), index=default_date.day-1, key=k_d)
    
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

# [功能] 加入暫存的回調函數
def add_child_callback():
    c_name = st.session_state.input_c_name
    note = st.session_state.input_note
    status = st.session_state.input_status
    
    y = st.session_state.year_add
    m = st.session_state.month_add
    d = st.session_state.day_add
    
    try:
        dob_obj = date(y + 1911, m, d)
    except:
        dob_obj = date.today()
        
    auto_plans = calculate_admission_roadmap(dob_obj)
    auto_plan = auto_plans[0] if auto_plans else "年齡不符/待確認"
    
    st.session_state.temp_children.append({
        "幼兒姓名": c_name if c_name else "(未填)",
        "幼兒生日": to_roc_str(dob_obj),
        "報名狀態": status,
        "預計入學資訊": auto_plan,
        "備註": note
    })
    
    # 清空幼兒欄位
    st.session_state.input_c_name = "" 
    st.session_state.input_note = ""

# [新增] 最終送出的回調函數 (解決 StreamlitAPIException 的關鍵)
def submit_all_callback():
    # 從 session_state 讀取家長資料
    p_name = st.session_state.input_p_name
    p_title = st.session_state.input_p_title
    phone = st.session_state.input_phone
    referrer = st.session_state.input_referrer
    
    # 檢查必填
    if not p_name or not phone:
        st.session_state['msg_error'] = "❌ 請填寫家長姓氏與電話"
        return

    # 檢查是否有幼兒名字在輸入框但未加入
    if st.session_state.input_c_name != "":
        st.session_state['msg_warning'] = "⚠️ 您輸入框裡還有名字，但沒有按「加入暫存」。請先加入暫存再送出。"
        return

    # 執行儲存
    current_df = load_registered_data()
    new_rows = []
    
    for child in st.session_state.temp_children:
        new_rows.append({
            '報名狀態': child['報名狀態'],
            '已聯繫': False,
            '登記日期': to_roc_str(date.today()),
            '幼兒姓名': child['幼兒姓名'] if child['幼兒姓名'] != "(未填)" else "",
            '家長稱呼': f"{p_name} {p_title}",
            '電話': str(phone), 
            '幼兒生日': child['幼兒生日'],
            '預計入學資訊': child['預計入學資訊'],
            '推薦人': referrer,
            '備註': child['備註']
        })
    
    if new_rows:
        new_df_chunk = pd.DataFrame(new_rows)
        updated_df = pd.concat([current_df, new_df_chunk], ignore_index=True)
        
        if sync_data_to_gsheets(updated_df):
            st.session_state['msg_success'] = f"✅ 成功新增 {len(new_rows)} 位幼兒資料！"
            
            # [安全清空] 這裡在回調函數內清空，不會報錯
            st.session_state.temp_children = []
            st.session_state.input_p_name = ""
            st.session_state.input_phone = ""
            st.session_state.input_referrer = ""
    else:
        st.session_state['msg_error'] = "❌ 沒有任何幼兒資料可送出"

# ==========================================
# 📱 APP 介面
# ==========================================
st.set_page_config(page_title="新生管理系統", layout="wide")
st.title("🏫 新生管理系統")

menu = st.sidebar.radio("系統切換", ["👶 新生報名管理", "👩‍🏫 師生人力預估系統"])

if menu == "👶 新生報名管理":
    # 初始化訊息狀態
    if 'msg_success' not in st.session_state: st.session_state['msg_success'] = None
    if 'msg_error' not in st.session_state: st.session_state['msg_error'] = None
    if 'msg_warning' not in st.session_state: st.session_state['msg_warning'] = None
    if 'temp_children' not in st.session_state: st.session_state.temp_children = []

    # 顯示並重置訊息 (確保訊息只出現一次)
    if st.session_state['msg_success']:
        st.balloons()
        st.success(st.session_state['msg_success'])
        st.session_state['msg_success'] = None
    if st.session_state['msg_error']:
        st.error(st.session_state['msg_error'])
        st.session_state['msg_error'] = None
    if st.session_state['msg_warning']:
        st.warning(st.session_state['msg_warning'])
        st.session_state['msg_warning'] = None

    df = load_registered_data()
    
    if not df.empty and '聯繫狀態' not in df.columns: df['聯繫狀態'] = '未聯繫'
    if not df.empty and '報名狀態' not in df.columns: df['報名狀態'] = '排隊候補'
    if not df.empty:
        df['已聯繫'] = df['聯繫狀態'].apply(lambda x: True if str(x).strip() == '已聯繫' else False)

    tab1, tab2, tab3 = st.tabs(["➕ 新增報名 (多寶模式)", "📂 新生資料庫", "📅 未來入學名單預覽"])

    # --- Tab 1: 新增 ---
    with tab1:
        st.subheader("第一步：填寫家長資料")
        c_p1, c_p2, c_p3 = st.columns([2, 1, 2])
        p_name = c_p1.text_input("家長姓氏 (必填)", key="input_p_name")
        p_title = c_p2.selectbox("稱謂", ["先生", "小姐", "爸爸", "媽媽"], key="input_p_title")
        phone = c_p3.text_input("聯絡電話 (必填)", key="input_phone")
        referrer = st.text_input("推薦人 (選填)", key="input_referrer")
        
        st.divider()
        st.subheader("第二步：新增幼兒 (可連續加入)")
        st.caption("💡 提示：輸入完一位幼兒後，請務必按下 **「⬇️ 加入暫存清單」**，再輸入下一位。")
        
        c_k1, c_k2 = st.columns([1, 2])
        with c_k1:
            st.text_input("幼兒姓名 (選填)", key="input_c_name")
            roc_date_input("幼兒出生年月日", date(2021, 9, 2), key_suffix="add")
        
        with c_k2:
            st.selectbox("報名狀態", ["排隊候補", "已確認/已繳費", "考慮中/參觀"], key="input_status")
            st.text_area("備註事項", placeholder="例如：雙胞胎哥哥、過敏...", height=100, key="input_note")

        st.button("⬇️ 加入暫存清單 (還有下一位)", on_click=add_child_callback, type="secondary")

        # 顯示暫存區
        if st.session_state.temp_children:
            st.info(f"目前已暫存 {len(st.session_state.temp_children)} 位幼兒")
            st.table(pd.DataFrame(st.session_state.temp_children))
            
            # [修正] 這裡使用 on_click 綁定回調函數，而不是在 if 裡面執行
            st.button("✅ 確認送出所有資料 (結束)", type="primary", on_click=submit_all_callback)
        else:
            st.info("尚未加入任何幼兒資料。請填寫上方資料並按下「加入暫存清單」。")

    # --- Tab 2: 新生資料庫 ---
    with tab2:
        st.subheader("📂 新生資料庫")
        
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
            
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載 Excel", data=csv, file_name='kindergarten_data.csv', mime='text/csv')

            display_df = df.copy()

            main_cols = ['已聯繫', '報名狀態', '幼兒生日', '登記日期', '家長稱呼', '電話', '推薦人', '備註', '幼兒姓名', '預計入學資訊']
            for c in main_cols:
                if c not in display_df.columns: display_df[c] = ""
            display_df['電話'] = display_df['電話'].astype(str)

            cols_config = {
                "已聯繫": st.column_config.CheckboxColumn("已聯繫", width="small", default=False),
                "報名狀態": st.column_config.SelectboxColumn("報名狀態", options=["排隊候補", "已確認/已繳費", "考慮中/參觀"], width="medium", required=True),
                "電話": st.column_config.TextColumn("電話", width="medium"),
                "預計入學資訊": st.column_config.TextColumn("入學年段", width="medium"),
                "備註": st.column_config.TextColumn("備註", width="large"),
                "登記日期": st.column_config.TextColumn("登記日期", width="small"),
                "幼兒生日": st.column_config.TextColumn("幼兒生日", width="small"),
            }
            
            st.caption(f"共顯示 {len(display_df)} 筆資料。")
            
            edit_df = st.data_editor(display_df[main_cols], column_config=cols_config, hide_index=True, use_container_width=True, num_rows="fixed", height=500)
            
            col_del, col_save = st.columns([2, 1])
            with col_del:
                del_options = edit_df.apply(lambda x: f"#{x.name+1} | {x['家長稱呼']} | {x['幼兒姓名']} ({x['幼兒生日']})", axis=1).tolist()
                delete_list = st.multiselect("🗑️ 批次刪除 (含編號)", del_options)
            
            with col_save:
                if st.button("💾 確認儲存變更", type="primary", use_container_width=True):
                    full_df = df.copy()
                    for idx, row in edit_df.iterrows():
                        if idx in full_df.index:
                            full_df.at[idx, '報名狀態'] = row['報名狀態']
                            full_df.at[idx, '已聯繫'] = row['已聯繫']
                            full_df.at[idx, '備註'] = row['備註']
                            full_df.at[idx, '幼兒姓名'] = row['幼兒姓名']
                    final_df = full_df.copy()
                    if delete_list:
                        indices_to_drop = [int(item.split("|")[0].replace("#", "").strip()) - 1 for item in delete_list]
                        final_df = final_df.drop(indices_to_drop)
                    
                    if sync_data_to_gsheets(final_df):
                        st.success("✅ 儲存成功！")
                        load_registered_data.clear()
                        st.rerun()
        else:
            st.info("目前無資料。")

    # --- Tab 3: 未來入學名單預覽 ---
    with tab3:
        st.subheader("📅 未來入學名單預覽")
        this_year = date.today().year - 1911
        search_year = st.number_input("請輸入查詢學年 (民國)", min_value=this_year, max_value=this_year+10, value=this_year+1)
        st.divider()
        st.write(f"### 🏫 民國 {search_year} 學年度 - 入學名單")

        if not df.empty:
            roster = {"托嬰中心": [], "幼幼班": [], "小班": [], "中班": [], "大班": []}
            for _, row in df.iterrows():
                try:
                    dob_str = str(row['幼兒生日'])
                    dob_parts = dob_str.split('/')
                    dob_obj = date(int(dob_parts[0])+1911, int(dob_parts[1]), int(dob_parts[2]))
                    grade = get_grade_for_year(dob_obj, search_year)
                    if grade in roster:
                        status_icon = "🟢" if "已確認" in row['報名狀態'] else "🟡"
                        roster[grade].append({
                            "狀態": f"{status_icon} {row['報名狀態']}",
                            "幼兒姓名": row['幼兒姓名'],
                            "家長": row['家長稱呼'],
                            "電話": row['電話'],
                            "備註": row['備註']
                        })
                except: pass

            for g in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]:
                students = roster[g]
                count = len(students)
                with st.expander(f"📍 {g} (符合資格：{count} 人)", expanded=(count > 0)):
                    if count > 0: st.table(pd.DataFrame(students))
                    else: st.write("無符合資格名單")
        else:
            st.info("目前無報名資料可供運算。")

elif menu == "👩‍🏫 師生人力預估系統":
    st.header("📊 未來學年師生人力預估")
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
                    try:
                        dob_str = str(row['幼兒生日'])
                        dob_parts = dob_str.split('/')
                        dob_obj = date(int(dob_parts[0])+1911, int(dob_parts[1]), int(dob_parts[2]))
                        grade = get_grade_for_year(dob_obj, year)
                        target_grade = grade if grade in confirmed_counts else None
                        if target_grade:
                            if "已確認" in status or "繳費" in status: confirmed_counts[target_grade] += 1
                            else: waitlist_counts[target_grade] += 1
                    except: pass

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
