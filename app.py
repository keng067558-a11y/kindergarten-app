# --- 頁面 2: 資料管理中心 ---
elif menu == "📂 資料管理中心":
    st.markdown("### 📂 資料管理中心")
    
    col_search, col_dl = st.columns([4, 1])
    with col_search:
        search_keyword = st_keyup("🔍 搜尋資料 (輸入電話或姓名)", placeholder="開始打字即自動過濾...")
    with col_dl:
        if not df.empty:
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載", data=csv, file_name=f'kindergarten_data_{date.today()}.csv', mime='text/csv', use_container_width=True)

    if not df.empty:
        display_df = df.copy()
        display_df['original_index'] = display_df.index
        
        if search_keyword:
            display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search_keyword, case=False)).any(axis=1)]

        # 預先計算 is_contacted
        display_df['is_contacted'] = display_df['聯繫狀態'].apply(lambda x: True if str(x).strip() == '已聯繫' else False)

        tab_todo, tab_done, tab_all = st.tabs(["📞 待聯繫名單", "✅ 已聯繫名單 (含入學設定)", "📋 全部資料"])

        # --- 定義：統計儀表板函數 (新增功能) ---
        def show_admission_summary(source_df):
            # 篩選出「已聯繫」且狀態為「已安排」或「已確認」的學生
            confirmed_df = source_df[
                (source_df['聯繫狀態'] == '已聯繫') & 
                (source_df['報名狀態'].astype(str).str.contains('已安排|已確認'))
            ]
            
            if confirmed_df.empty:
                st.info("ℹ️ 目前尚無「已聯繫」且「已安排」入學的學生。")
            else:
                # 依照「預計入學資訊」分組統計
                summary = confirmed_df.groupby('預計入學資訊').size().reset_index(name='已安排人數')
                summary = summary.sort_values('預計入學資訊')
                
                st.markdown("#### 📊 目前已安排入學人數統計")
                # 轉換成橫向顯示或較美觀的 dataframe
                st.dataframe(
                    summary.style.background_gradient(cmap="Blues"), 
                    use_container_width=True,
                    hide_index=True
                )
                st.caption("※ 此統計僅包含「已聯繫」且狀態為「已安排/已確認」的學生。")
                st.divider()

        # --- 定義：顯示列表函數 (修改功能：加入入學年段編輯) ---
        def render_student_list(target_df, tab_key_suffix, show_summary=False):
            if show_summary:
                # 在列表上方顯示統計
                show_admission_summary(df) # 傳入完整的 df 以進行全局統計

            if target_df.empty:
                st.info("此區塊目前無資料。")
                return

            grouped_df_tab = target_df.groupby('電話')
            st.caption(f"在此列表中共找到 {len(grouped_df_tab)} 個家庭")

            for phone_num, group_data in grouped_df_tab:
                first_row = group_data.iloc[0]
                parent_name = first_row['家長稱呼']
                
                expander_title = f"👤 {parent_name} | 📞 {phone_num}"
                
                with st.expander(expander_title):
                    for _, row in group_data.iterrows():
                        orig_idx = row['original_index']
                        unique_key = f"{tab_key_suffix}_{orig_idx}"

                        status_color = "tag-yellow"
                        if "已安排" in str(row['報名狀態']): status_color = "tag-green"
                        elif "考慮" in str(row['報名狀態']): status_color = "tag-blue"
                        
                        child_name = row['幼兒姓名'] if row['幼兒姓名'] else "(未填姓名)"

                        # 顯示基本資訊
                        st.markdown(f"""
                        <div class="child-info-block">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-size:1.1em; font-weight:bold; color:#333;">👶 {child_name}</span>
                                <span class="card-tag {status_color}">{row['報名狀態']}</span>
                            </div>
                            <div style="font-size:0.85em; color:#666; margin-top:4px;">
                                🎂 {row['幼兒生日']} 
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # --- 編輯區塊開始 ---
                        c1, c2 = st.columns([1, 1])
                        
                        # 定義更新 Callback
                        def update_state(oid=orig_idx, k_con=f"c_{unique_key}", k_sta=f"s_{unique_key}", k_plan=f"p_{unique_key}", k_note=f"n_{unique_key}"):
                            if oid not in st.session_state.edited_rows:
                                st.session_state.edited_rows[oid] = {}
                            
                            st.session_state.edited_rows[oid]['聯繫狀態'] = "已聯繫" if st.session_state[k_con] else "未聯繫"
                            st.session_state.edited_rows[oid]['報名狀態'] = st.session_state[k_sta]
                            st.session_state.edited_rows[oid]['預計入學資訊'] = st.session_state[k_plan] # 新增這一行
                            st.session_state.edited_rows[oid]['備註'] = st.session_state[k_note]

                        # 1. 已聯繫 Checkbox
                        with c1:
                            is_con = st.checkbox("已聯繫", value=row['is_contacted'], key=f"c_{unique_key}", on_change=update_state)
                        
                        # 2. 報名狀態 Selectbox
                        with c2:
                            status_opts = ["排隊中", "已安排", "考慮中", "放棄", "超齡/畢業"]
                            curr_val = row['報名狀態']
                            if curr_val not in status_opts: status_opts.insert(0, curr_val)
                            st.selectbox("報名狀態", status_opts, index=status_opts.index(curr_val), key=f"s_{unique_key}", on_change=update_state, label_visibility="collapsed")

                        # 3. [新增] 預計入學資訊 Selectbox
                        # 計算合理的入學選項
                        try:
                            dob_parts = str(row['幼兒生日']).split('/')
                            dob_obj = date(int(dob_parts[0])+1911, int(dob_parts[1]), int(dob_parts[2]))
                            plan_opts = calculate_admission_roadmap(dob_obj)
                        except:
                            plan_opts = ["無法計算日期"]
                        
                        curr_plan = str(row['預計入學資訊'])
                        if curr_plan not in plan_opts: plan_opts.insert(0, curr_plan)
                        
                        st.write("📅 **預計就讀年段** (修改後請按下方儲存)")
                        st.selectbox("預計就讀年段", plan_opts, index=plan_opts.index(curr_plan), key=f"p_{unique_key}", on_change=update_state)

                        # 4. 備註 Textarea
                        st.text_area("備註", value=row['備註'], height=68, key=f"n_{unique_key}", on_change=update_state)

                        # 刪除按鈕
                        if st.button("🗑️ 刪除此幼兒", key=f"del_{unique_key}"):
                            new_df = df.drop(orig_idx)
                            if sync_data_to_gsheets(new_df):
                                st.success("已刪除")
                                time.sleep(0.5)
                                st.rerun()
                        st.divider()

        with tab_todo:
            st.warning("🔔 這裡顯示 **尚未聯繫** 的家長，請優先處理。")
            render_student_list(display_df[display_df['is_contacted'] == False], "todo")

        with tab_done:
            # 這裡開啟 show_summary=True，讓使用者一進來就看到統計
            st.success("✅ 這裡顯示 **已經聯繫過** 的家長，可編輯「預計就讀年段」。")
            render_student_list(display_df[display_df['is_contacted'] == True], "done", show_summary=True)

        with tab_all:
            render_student_list(display_df, "all")
        
        # 底部儲存按鈕
        st.write("")
        st.markdown("---")
        # 這裡做一個浮動效果或醒目提示
        col_save_1, col_save_2 = st.columns([1, 2])
        with col_save_2:
            if st.button("💾 儲存所有變更 (更新統計數據)", type="primary", use_container_width=True):
                if st.session_state.edited_rows:
                    full_df = df.copy()
                    for idx, changes in st.session_state.edited_rows.items():
                        if idx in full_df.index:
                            for col, val in changes.items():
                                full_df.at[idx, col] = val
                    
                    if sync_data_to_gsheets(full_df):
                        st.success("✅ 資料已儲存！統計數據已更新。")
                        st.session_state.edited_rows = {}
                        time.sleep(1)
                        st.rerun()
                else:
                    st.info("沒有偵測到任何變更。")

    else:
        st.info("目前無資料。")
