# ==========================================
# 修改 1: load_registered_data (加入重要性欄位)
# ==========================================
@st.cache_data(ttl=60)
def load_registered_data():
    sheet = connect_to_gsheets_students()
    df = pd.DataFrame()
    if sheet:
        try:
            data = sheet.get_all_values()
            if data: df = pd.DataFrame(data[1:], columns=data[0])
        except: pass
    
    if df.empty:
        try: df = pd.read_csv(LOCAL_CSV)
        except: df = pd.DataFrame(columns=['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註', '重要性'])

    if '電話' in df.columns:
        df['電話'] = df['電話'].astype(str).str.strip().apply(lambda x: '0' + x if len(x) == 9 and x.startswith('9') else x)
    if '聯繫狀態' not in df.columns: df['聯繫狀態'] = '未聯繫'
    if '報名狀態' not in df.columns: df['報名狀態'] = '排隊中'
    # --- 新增：確保重要性欄位存在，預設為普通 ---
    if '重要性' not in df.columns: df['重要性'] = '🟢 普通' 
    return df

# ==========================================
# 修改 2: sync_data_to_gsheets (儲存重要性)
# ==========================================
def sync_data_to_gsheets(new_df):
    try:
        save_df = new_df.copy()
        for c in ['is_contacted', 'original_index']: 
            if c in save_df.columns: save_df = save_df.drop(columns=[c])
        
        # --- 新增：加入 '重要性' 到儲存列表 ---
        final_cols = ['報名狀態', '聯繫狀態', '登記日期', '幼兒姓名', '家長稱呼', '電話', '幼兒生日', '預計入學資訊', '推薦人', '備註', '重要性']
        for c in final_cols: 
            if c not in save_df.columns: save_df[c] = ""
            
        # 填補空值，避免儲存錯誤
        save_df['重要性'] = save_df['重要性'].replace('', '🟢 普通').fillna('🟢 普通')

        save_df = save_df[final_cols].astype(str)

        sheet = connect_to_gsheets_students()
        if sheet:
            try:
                sheet.clear()
                sheet.append_row(final_cols)
                if not save_df.empty: sheet.append_rows(save_df.values.tolist())
            except: pass 

        save_df.to_csv(LOCAL_CSV, index=False)
        load_registered_data.clear()
        return True
    except Exception as e:
        st.error(f"儲存錯誤: {e}")
        return False
