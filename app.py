# ... (前面的程式碼保持不變) ...

# --- 頁面 2: 資料管理 ---
elif menu == "📂 資料管理中心":
    st.header("📂 資料管理中心")
    col_search, col_dl = st.columns([4, 1])
    kw = st_keyup("🔍 搜尋", placeholder="電話或姓名...", key="search_kw")
    if not df.empty: col_dl.download_button("📥", df.to_csv(index=False).encode('utf-8-sig'), 'data.csv')

    if not df.empty:
        disp = df.copy()
        disp['original_index'] = disp.index
        
        # 全局搜尋過濾
        if kw: disp = disp[disp.astype(str).apply(lambda x: x.str.contains(kw, case=False)).any(axis=1)]
        disp['is_contacted'] = disp['聯繫狀態'] == '已聯繫'

        # 分頁籤
        t1, t2, t3 = st.tabs(["🔴 待聯繫", "🟢 已聯繫", "📁 全部資料"])

        # === 核心修改：改為依照狀態分類的卡片渲染函數 ===
        def render_status_cards(tdf, key_pfx):
            # 定義狀態分類 (您可以依需求調整這些群組)
            status_groups = {
                "🔥 預約與考慮 (優先處理)": ["預約參觀", "考慮中"],
                "⏳ 排隊等待": ["排隊中", "未定"], # 若狀態為空或不在列表中，預設歸類於此
                "✅ 確認入學": ["確認入學", "已安排"],
                "❌ 放棄/不符/其他": ["放棄", "超齡/畢業"]
            }

            # 預處理：確保狀態欄位有值
            all_known_statuses = [s for sublist in status_groups.values() for s in sublist]
            
            # 依序渲染每個區塊
            for group_name, status_list in status_groups.items():
                # 篩選資料
                if group_name == "⏳ 排隊等待":
                    # 排隊中 + 所有未定義的狀態
                    sub_df = tdf[tdf['報名狀態'].isin(status_list) | ~tdf['報名狀態'].isin(all_known_statuses)]
                else:
                    sub_df = tdf[tdf['報名狀態'].isin(status_list)]

                if not sub_df.empty:
                    # 使用 Expander 區分狀態大類
                    with st.expander(f"{group_name} (共 {len(sub_df)} 筆)", expanded=True):
                        # 依重要性排序 (優 > 中 > 差)
                        prio_map = {"優": 0, "中": 1, "差": 2}
                        sub_df['sort_temp'] = sub_df['重要性'].map(prio_map).fillna(1)
                        sub_df = sub_df.sort_values(by=['sort_temp', '登記日期'], ascending=[True, False])

                        # 渲染每一張學生卡片
                        for _, r in sub_df.iterrows():
                            oid = r['original_index']
                            uk = f"{key_pfx}_{oid}" # Unique Key
                            
                            # 卡片樣式 (使用 container 加框線)
                            with st.container(border=True):
                                # 第一行：標題與基本資訊
                                top_c1, top_c2 = st.columns([3, 1])
                                priority_icon = {"優": "🔴", "中": "🟡", "差": "⚪"}.get(r['重要性'], "⚪")
                                top_c1.markdown(f"**{priority_icon} {r['幼兒姓名']}** | {r['幼兒生日']} | {r['家長稱呼']}")
                                top_c2.caption(f"📞 {r['電話']}")

                                # 第二行：核心操作區
                                r1, r2, r3, r4 = st.columns([1.2, 1.2, 1.5, 1])
                                
                                # 1. 聯繫勾選
                                r1.checkbox("已聯繫", r['is_contacted'], key=f"c_{uk}")
                                
                                # 2. 狀態選擇
                                opts_stat = ["預約參觀", "排隊中", "確認入學", "已安排", "考慮中", "放棄", "超齡/畢業"]
                                cur_stat = r['報名狀態'] if r['報名狀態'] in opts_stat else "排隊中"
                                r2.selectbox("狀態", opts_stat, index=opts_stat.index(cur_stat), key=f"s_{uk}", label_visibility="collapsed")

                                # 3. 預計年段 (自動計算 + 手動修正)
                                curr_plan = str(r['預計入學資訊'])
                                if curr_plan == 'nan': curr_plan = ""
                                plans = [curr_plan]
                                try:
                                    dob_obj = date(int(str(r['幼兒生日']).split('/')[0])+1911, int(str(r['幼兒生日']).split('/')[1]), int(str(r['幼兒生日']).split('/')[2]))
                                    plans = calculate_admission_roadmap(dob_obj)
                                    if curr_plan and curr_plan not in plans: plans.insert(0, curr_plan)
                                except: pass
                                
                                p_idx = 0
                                if curr_plan in plans: p_idx = plans.index(curr_plan)
                                r3.selectbox("入學年段", plans, index=p_idx, key=f"p_{uk}", label_visibility="collapsed")
                                
                                # 4. 重要性
                                r4.selectbox("優先", ["優", "中", "差"], index=["優", "中", "差"].index(r['重要性'] if r['重要性'] in ["優", "中", "差"] else "中"), key=f"imp_{uk}", label_visibility="collapsed")

                                # 第三行：備註與刪除
                                n_val = r['備註'] if str(r['備註'])!='nan' else ""
                                st.text_area("備註", n_val, key=f"n_{uk}", height=68, placeholder="在此輸入備註...")
                                
                                # 底部小工具
                                b1, b2 = st.columns([5, 1])
                                with b1: st.caption(f"登記日: {r['登記日期']}")
                                with b2: st.checkbox("刪除", key=f"del_{uk}")

        # === 儲存邏輯 (保持原有邏輯，但適配新的 key) ===
        def process_save_status(tdf, key_pfx):
            with st.spinner("正在更新資料庫..."):
                fulldf = load_registered_data()
                changes_made = False
                indices_to_drop = [] 
                
                for _, r in tdf.iterrows():
                    oid = r['original_index']
                    uk = f"{key_pfx}_{oid}"
                    
                    # 檢查刪除
                    if st.session_state.get(f"del_{uk}"):
                        indices_to_drop.append(oid)
                        changes_made = True
                        continue 
                    
                    # 讀取 Widget 數值
                    new_contact = st.session_state.get(f"c_{uk}")
                    new_status = st.session_state.get(f"s_{uk}")
                    new_plan = st.session_state.get(f"p_{uk}")
                    new_note = st.session_state.get(f"n_{uk}")
                    new_imp = st.session_state.get(f"imp_{uk}")
                    
                    def strict_val(v): return "" if str(v).strip() == 'nan' else str(v).strip()

                    # 比對並更新
                    if new_contact is not None:
                        ncon_str = "已聯繫" if new_contact else "未聯繫"
                        if strict_val(fulldf.at[oid, '聯繫狀態']) != strict_val(ncon_str):
                            fulldf.at[oid, '聯繫狀態'] = ncon_str; changes_made = True
                    
                    if new_status is not None and strict_val(fulldf.at[oid, '報名狀態']) != strict_val(new_status):
                        fulldf.at[oid, '報名狀態'] = new_status; changes_made = True
                        
                    if new_plan is not None and strict_val(fulldf.at[oid, '預計入學資訊']) != strict_val(new_plan):
                        fulldf.at[oid, '預計入學資訊'] = new_plan; changes_made = True
                        
                    if new_note is not None and strict_val(fulldf.at[oid, '備註']) != strict_val(new_note):
                        fulldf.at[oid, '備註'] = new_note; changes_made = True
                        
                    if new_imp is not None and strict_val(fulldf.at[oid, '重要性']) != strict_val(new_imp):
                        fulldf.at[oid, '重要性'] = new_imp; changes_made = True

                if indices_to_drop: fulldf = fulldf.drop(indices_to_drop)

                if changes_made:
                    if sync_data_to_gsheets(fulldf):
                        st.toast("✅ 資料已成功更新！", icon="💾")
                        st.rerun() 
                else:
                    st.toast("沒有偵測到變更", icon="ℹ️")

        # === 渲染 Tab 內容 ===
        with t1:
            target_data = disp[~disp['is_contacted']]
            if not target_data.empty:
                with st.form("form_t1"):
                    render_status_cards(target_data, "t1")
                    st.write("")
                    st.form_submit_button("💾 儲存所有變更", type="primary", use_container_width=True, on_click=lambda: process_save_status(target_data, "t1"))
            else: st.info("🎉 太棒了！目前沒有待聯繫的名單。")

        with t2:
            target_data = disp[disp['is_contacted']]
            if not target_data.empty:
                with st.form("form_t2"):
                    render_status_cards(target_data, "t2")
                    st.write("")
                    st.form_submit_button("💾 儲存所有變更", type="primary", use_container_width=True, on_click=lambda: process_save_status(target_data, "t2"))
            else: st.info("目前沒有已聯繫的資料。")

        with t3:
            if not disp.empty:
                with st.form("form_t3"):
                    render_status_cards(disp, "t3")
                    st.write("")
                    st.form_submit_button("💾 儲存所有變更", type="primary", use_container_width=True, on_click=lambda: process_save_status(disp, "t3"))
            else: st.info("資料庫是空的。")

# ... (後面的程式碼保持不變) ...
