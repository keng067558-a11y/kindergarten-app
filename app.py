# ... (前面的程式碼保持不變)

# --- 頁面 2: 資料管理 ---
elif menu == "📂 資料管理中心":
    st.header("📂 資料管理中心")
    col_search, col_dl = st.columns([4, 1])
    kw = st_keyup("🔍 搜尋", placeholder="電話或姓名...", key="search_kw")
    if not df.empty: col_dl.download_button("📥", df.to_csv(index=False).encode('utf-8-sig'), 'data.csv')

    if not df.empty:
        disp = df.copy()
        disp['original_index'] = disp.index
        
        # === 修改 1: 加入排序邏輯 (優 > 中 > 差) ===
        prio_map = {"優": 0, "中": 1, "差": 2}
        # 將重要性轉為數字以利排序，預設為 1 (中)
        disp['sort_val'] = disp['重要性'].map(prio_map).fillna(1)
        # 先排重要性(小到大)，再排日期(新到舊)
        disp = disp.sort_values(by=['sort_val', '登記日期'], ascending=[True, False])
        # ========================================

        if kw: disp = disp[disp.astype(str).apply(lambda x: x.str.contains(kw, case=False)).any(axis=1)]
        disp['is_contacted'] = disp['聯繫狀態'] == '已聯繫'

        t1, t2, t3 = st.tabs(["待聯繫", "已聯繫", "全部"])

        def render_cards_in_form(tdf, key_pfx):
            if tdf.empty: 
                st.caption("無資料")
                return False 
            
            prio_opts = ["優", "中", "差"]
            
            # 使用 sort=False 確保維持我們上面做好的優先級排序
            for ph, gp in tdf.groupby('電話', sort=False):
                row_data = gp.iloc[0]
                curr_prio = row_data.get('重要性', '中')
                if curr_prio not in prio_opts: curr_prio = "中"
                
                # === 修改 2: 視覺化優化 (顏色與年段) ===
                # A. 定義優先級顏色符號
                icon_map = {"優": "🔴", "中": "🟡", "差": "⚪"} # 紅=優, 黃=中, 白=差
                prio_icon = icon_map.get(curr_prio, "⚪")

                # B. 擷取年段 (例如從 "113 學年 - 小班" 取出 "小班")
                plan_str = str(row_data['預計入學資訊'])
                grade_show = "未定"
                if " - " in plan_str:
                    grade_show = plan_str.split(" - ")[-1] # 取最後一段
                elif plan_str and plan_str != "nan":
                    grade_show = plan_str
                
                # C. 處理備註顯示
                raw_note = str(row_data['備註']).strip()
                note_str = f" | 📝 {raw_note[:10]}..." if raw_note else ""
                
                # D. 組裝新標題：[顏色] [年段] 家長稱呼
                expander_title = f"{prio_icon} 【{grade_show}】 {row_data['家長稱呼']} | 📞 {ph}{note_str}"
                # ========================================
                
                with st.expander(expander_title):
                    for _, r in gp.iterrows():
                        oid = r['original_index']
                        uk = f"{key_pfx}_{oid}"
                        
                        st.markdown(f"**{r['幼兒姓名']}** | 生日：{r['幼兒生日']}")
                        
                        c1, c2 = st.columns([1, 1])
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
                        # 這裡保留下拉選單讓你可以修改優先級
                        c4.selectbox("優先等級", prio_opts, index=prio_opts.index(curr_prio), key=f"imp_{uk}")

                        st.text_area("備註內容", r['備註'], key=f"n_{uk}", height=80, placeholder="備註...")
                        st.divider()
            return True

        def process_save(tdf, key_pfx):
            fulldf = load_registered_data()
            changes_made = False
            
            for _, r in tdf.iterrows():
                oid = r['original_index']
                uk = f"{key_pfx}_{oid}"
                
                new_contact = st.session_state.get(f"c_{uk}")
                new_status = st.session_state.get(f"s_{uk}")
                new_plan = st.session_state.get(f"p_{uk}")
                new_note = st.session_state.get(f"n_{uk}")
                new_imp = st.session_state.get(f"imp_{uk}")
                
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

        with t1:
            with st.form("form_t1"):
                # 這裡傳入的資料已經是依照優先級排序過的
                has_data = render_cards_in_form(disp[~disp['is_contacted']], "t1")
                if has_data:
                    if st.form_submit_button("💾 儲存本頁變更", type="primary", use_container_width=True):
                        process_save(disp[~disp['is_contacted']], "t1")

        with t2:
            with st.form("form_t2"):
                has_data = render_cards_in_form(disp[disp['is_contacted']], "t2")
                if has_data:
                    if st.form_submit_button("💾 儲存本頁變更", type="primary", use_container_width=True):
                        process_save(disp[disp['is_contacted']], "t2")

        with t3:
            with st.form("form_t3"):
                has_data = render_cards_in_form(disp, "t3")
                if has_data:
                    if st.form_submit_button("💾 儲存本頁變更", type="primary", use_container_width=True):
                        process_save(disp, "t3")

# ... (後面的程式碼保持不變)
