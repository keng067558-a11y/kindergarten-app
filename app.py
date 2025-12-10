# --- 頁面 2: 資料管理中心 (已新增：刪除按鈕) ---
elif menu == "📂 資料管理中心":
    st.markdown("### 📂 資料管理中心")
    col_search, col_dl = st.columns([4, 1])
    search_keyword = st_keyup("🔍 搜尋資料 (輸入電話或姓名)", placeholder="開始打字...", key="search_main")
    if not df.empty:
        col_dl.download_button("📥 下載", df.to_csv(index=False).encode('utf-8-sig'), f'kindergarten_{date.today()}.csv', 'text/csv')

    if not df.empty:
        display_df = df.copy()
        display_df['original_index'] = display_df.index
        if search_keyword:
            display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search_keyword, case=False)).any(axis=1)]
        display_df['is_contacted'] = display_df['聯繫狀態'].apply(lambda x: True if str(x).strip() == '已聯繫' else False)

        tab_todo, tab_done, tab_all = st.tabs(["📞 待聯繫名單", "✅ 已聯繫名單 (含入學設定)", "📋 全部資料"])

        def show_summary_dashboard():
            confirmed_df = df[(df['聯繫狀態']=='已聯繫') & (df['報名狀態'].astype(str).str.contains('已安排|已確認'))]
            if not confirmed_df.empty:
                st.markdown("#### 📊 目前已安排入學人數")
                st.dataframe(confirmed_df.groupby('預計入學資訊').size().reset_index(name='已安排人數'), use_container_width=True, hide_index=True)

        def render_list(target_df, tab_key, show_stats=False):
            if show_stats: show_summary_dashboard()
            if target_df.empty: st.info("無資料"); return
            
            for phone, group in target_df.groupby('電話'):
                with st.expander(f"👤 {group.iloc[0]['家長稱呼']} | 📞 {phone}"):
                    for _, row in group.iterrows():
                        oid = row['original_index']
                        uid = f"{tab_key}_{oid}"
                        
                        st.markdown(f"**👶 {row['幼兒姓名']}** | {row['幼兒生日']} | 狀態: {row['報名狀態']}")
                        c1, c2 = st.columns(2)
                        
                        def update(idx=oid, u=uid):
                            if idx not in st.session_state.edited_rows: st.session_state.edited_rows[idx] = {}
                            st.session_state.edited_rows[idx]['聯繫狀態'] = "已聯繫" if st.session_state[f"c_{u}"] else "未聯繫"
                            st.session_state.edited_rows[idx]['報名狀態'] = st.session_state[f"s_{u}"]
                            st.session_state.edited_rows[idx]['預計入學資訊'] = st.session_state[f"p_{u}"]
                            st.session_state.edited_rows[idx]['備註'] = st.session_state[f"n_{u}"]

                        c1.checkbox("已聯繫", row['is_contacted'], key=f"c_{uid}", on_change=update)
                        status_opts = ["排隊中", "已安排", "考慮中", "放棄", "超齡/畢業"]
                        curr_stat = row['報名狀態'] if row['報名狀態'] in status_opts else status_opts[0]
                        c2.selectbox("狀態", status_opts, index=status_opts.index(curr_stat), key=f"s_{uid}", on_change=update)
                        
                        try: 
                            dob_parts = str(row['幼兒生日']).split('/')
                            dob_obj = date(int(dob_parts[0])+1911, int(dob_parts[1]), int(dob_parts[2]))
                            plan_opts = calculate_admission_roadmap(dob_obj)
                        except: plan_opts = ["無法計算"]
                        curr_plan = str(row['預計入學資訊'])
                        if curr_plan not in plan_opts: plan_opts.insert(0, curr_plan)
                        st.selectbox("預計就讀年段", plan_opts, index=plan_opts.index(curr_plan), key=f"p_{uid}", on_change=update)
                        st.text_area("備註", row['備註'], key=f"n_{uid}", height=60, on_change=update)
                        
                        # --- 這裡增加了刪除按鈕 ---
                        if st.button("🗑️ 刪除此筆資料", key=f"del_{uid}"):
                            new_df = df.drop(oid)
                            if sync_data_to_gsheets(new_df):
                                st.success("已刪除！")
                                time.sleep(0.5)
                                st.rerun()
                        
                        st.divider()

        with tab_todo: render_list(display_df[~display_df['is_contacted']], "todo")
        with tab_done: render_list(display_df[display_df['is_contacted']], "done", True)
        with tab_all: render_list(display_df, "all")

        if st.button("💾 儲存所有變更", type="primary", use_container_width=True):
            if st.session_state.edited_rows:
                full_df = df.copy()
                for idx, changes in st.session_state.edited_rows.items():
                    if idx in full_df.index:
                        for col, val in changes.items(): full_df.at[idx, col] = val
                if sync_data_to_gsheets(full_df):
                    st.success("儲存成功！"); st.session_state.edited_rows = {}; time.sleep(1); st.rerun()
