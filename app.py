# --- 頁面 2: 資料管理 ---
elif menu == "📂 資料管理中心":
    st.header("📂 資料管理中心")
    col_search, col_dl = st.columns([4, 1])
    kw = st_keyup("🔍 搜尋", placeholder="電話或姓名...", key="search_kw")
    if not df.empty: col_dl.download_button("📥", df.to_csv(index=False).encode('utf-8-sig'), 'data.csv')

    if not df.empty:
        disp = df.copy()
        disp['original_index'] = disp.index
        if kw: disp = disp[disp.astype(str).apply(lambda x: x.str.contains(kw, case=False)).any(axis=1)]
        disp['is_contacted'] = disp['聯繫狀態'] == '已聯繫'

        t1, t2, t3 = st.tabs(["待聯繫", "已聯繫", "全部"])

        # 定義渲染卡片的函數 (移除 on_change，改為單純顯示)
        def render_cards_in_form(tdf, key_pfx):
            if tdf.empty: 
                st.caption("無資料")
                return False # 代表沒資料，不需要按鈕
            
            prio_opts = ["優", "中", "差"]
            
            # 這裡只負責「畫」出介面
            for ph, gp in tdf.groupby('電話'):
                row_data = gp.iloc[0]
                curr_prio = row_data.get('重要性', '中')
                if curr_prio not in prio_opts: curr_prio = "中"
                
                raw_note = str(row_data['備註']).strip()
                note_str = f" | 📝 {raw_note[:15]}..." if raw_note else ""
                
                expander_title = f"[{curr_prio}] {row_data['家長稱呼']} | 📞 {ph}{note_str}"
                
                with st.expander(expander_title):
                    for _, r in gp.iterrows():
                        oid = r['original_index']
                        uk = f"{key_pfx}_{oid}"
                        
                        st.markdown(f"**{r['幼兒姓名']}** | 生日：{r['幼兒生日']}")
                        
                        c1, c2 = st.columns([1, 1])
                        # 注意：這裡拿掉了 on_change=upd
                        c1.checkbox("已聯繫", r['is_contacted'], key=f"c_{uk}")
                        
                        opts = ["排隊中", "確認入學", "已安排", "考慮中", "放棄", "超齡/畢業"]
                        val = r['報名狀態'] if r['報名狀態'] in opts else opts[0]
                        c2.selectbox("狀態", opts, index=opts.index(val), key=f"s_{uk}")

                        c3, c4 = st.columns([1, 1])
                        try: 
                            dob = date(int(str(r['幼兒生日']).split('/')[0])+1911, int(str(r['幼兒生日']).split('/')[1]), int(str(r['幼兒生日']).split('/')[2]))
                            plans = calculate_admission_roadmap(dob)
                        except: plans = ["無法計算"]
                        plan_val = str(r['預計入學資訊'])
                        if plan_val not in plans: plans.insert(0, plan_val)
                        
                        c3.selectbox("預計年段", plans, index=plans.index(plan_val), key=f"p_{uk}")
                        c4.selectbox("優先等級", prio_opts, index=prio_opts.index(curr_prio), key=f"imp_{uk}")

                        st.text_area("備註內容", r['備註'], key=f"n_{uk}", height=80, placeholder="備註...")
                        st.divider()
            return True

        # 定義儲存邏輯 (按下按鈕後才執行)
        def process_save(tdf, key_pfx):
            fulldf = load_registered_data() # 讀取原始最新檔
            changes_made = False
            
            for _, r in tdf.iterrows():
                oid = r['original_index']
                uk = f"{key_pfx}_{oid}"
                
                # 從 session_state 抓取表單內的最新值
                new_contact = st.session_state.get(f"c_{uk}")
                new_status = st.session_state.get(f"s_{uk}")
                new_plan = st.session_state.get(f"p_{uk}")
                new_note = st.session_state.get(f"n_{uk}")
                new_imp = st.session_state.get(f"imp_{uk}")
                
                # 比對並更新
                if new_contact is not None:
                    ncon_str = "已聯繫" if new_contact else "未聯繫"
                    if fulldf.at[oid, '聯繫狀態'] != ncon_str: fulldf.at[oid, '聯繫狀態'] = ncon_str; changes_made = True
                
                if new_status is not None and fulldf.at[oid, '報名狀態'] != new_status:
                    fulldf.at[oid, '報名狀態'] = new_status; changes_made = True
                    
                if new_plan is not None and fulldf.at[oid, '預計入學資訊'] != new_plan:
                    fulldf.at[oid, '預計入學資訊'] = new_plan; changes_made = True
                    
                if new_note is not None and fulldf.at[oid, '備註'] != new_note:
                    fulldf.at[oid, '備註'] = new_note; changes_made = True
                    
                if new_imp is not None and fulldf.at[oid, '重要性'] != new_imp:
                    fulldf.at[oid, '重要性'] = new_imp; changes_made = True

            if changes_made:
                if sync_data_to_gsheets(fulldf):
                    st.success("✅ 資料已批次更新！")
                    time.sleep(1)
                    st.rerun()
            else:
                st.info("沒有偵測到變更")

        # --- 頁面渲染區 (將表單包在 Tab 裡面) ---
        
        # Tab 1: 待聯繫
        with t1:
            with st.form("form_t1"):
                has_data = render_cards_in_form(disp[~disp['is_contacted']], "t1")
                if has_data:
                    # 表單送出按鈕
                    if st.form_submit_button("💾 儲存本頁變更", type="primary", use_container_width=True):
                        process_save(disp[~disp['is_contacted']], "t1")

        # Tab 2: 已聯繫
        with t2:
            with st.form("form_t2"):
                has_data = render_cards_in_form(disp[disp['is_contacted']], "t2")
                if has_data:
                    if st.form_submit_button("💾 儲存本頁變更", type="primary", use_container_width=True):
                        process_save(disp[disp['is_contacted']], "t2")

        # Tab 3: 全部
        with t3:
            with st.form("form_t3"):
                has_data = render_cards_in_form(disp, "t3")
                if has_data:
                    if st.form_submit_button("💾 儲存本頁變更", type="primary", use_container_width=True):
                        process_save(disp, "t3")
