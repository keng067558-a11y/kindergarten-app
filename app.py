# --- 頁面 3: 未來入學預覽 ---
elif menu == "📅 未來入學預覽":
    st.markdown("### 📅 未來入學名單預覽")
    c_year, c_info = st.columns([1, 3])
    with c_year:
        this_year = date.today().year - 1911
        search_year = st.number_input("查詢學年 (民國)", min_value=this_year, max_value=this_year+10, value=this_year+1)
    
    st.divider()

    if not df.empty:
        # 初始化統計容器
        roster = {
            "托嬰中心": {"confirmed": [], "pending": []}, 
            "幼幼班": {"confirmed": [], "pending": []}, 
            "小班": {"confirmed": [], "pending": []}, 
            "中班": {"confirmed": [], "pending": []}, 
            "大班": {"confirmed": [], "pending": []}
        }
        
        # 全局統計變數
        stats = {
            "total_qualified": 0, # 總符合資格 (不含放棄)
            "confirmed": 0,       # 已安排
            "pending": 0          # 待確認 (總 - 已安排)
        }
        
        for idx, row in df.iterrows():
            try:
                # 1. 決定該學生在「查詢學年」的年級
                current_plan = str(row['預計入學資訊'])
                target_year_str = f"{search_year} 學年"
                grade = None
                
                # A. 優先使用手動設定 (如果包含該學年)
                if target_year_str in current_plan:
                    parts = current_plan.split(" - ")
                    if len(parts) > 1:
                        grade = parts[1].strip()
                
                # B. 如果手動設定無效，則使用生日自動推算
                if not grade:
                    try:
                        dob_parts = str(row['幼兒生日']).split('/')
                        dob_obj = date(int(dob_parts[0])+1911, int(dob_parts[1]), int(dob_parts[2]))
                        grade = get_grade_for_year(dob_obj, search_year)
                    except:
                        pass
                
                # 2. 判斷學生狀態
                status_text = str(row['報名狀態'])
                is_confirmed = "已安排" in status_text or "已確認" in status_text
                is_given_up = "放棄" in status_text
                
                # 3. 進行歸類 (排除放棄與超齡)
                if grade in roster and not is_given_up:
                    stats['total_qualified'] += 1
                    
                    student_info = {
                        "原索引": idx,
                        "報名狀態": row['報名狀態'],
                        "聯繫狀態": row['聯繫狀態'],
                        "幼兒姓名": row['幼兒姓名'],
                        "家長": row['家長稱呼'],
                        "電話": row['電話'],
                        "備註": row['備註']
                    }

                    if is_confirmed:
                        stats['confirmed'] += 1
                        roster[grade]["confirmed"].append(student_info)
                    else:
                        stats['pending'] += 1
                        roster[grade]["pending"].append(student_info)
                        
            except Exception as e: 
                pass

        # --- 頂部數據儀表板 ---
        # 這裡實現您的需求：符合資格人數 要扣掉 已經安排的人數
        st.markdown(f"#### 📊 {search_year} 學年度 - 入學概況")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("✅ 已安排入學", f"{stats['confirmed']} 人", border=True)
        m2.metric("⏳ 尚有名單 (扣除已安排)", f"{stats['pending']} 人", delta_color="off", border=True, help="這是您還需要努力確認的潛在學生數 (已排除放棄者)")
        m3.metric("📋 總符合資格", f"{stats['total_qualified']} 人", border=True)
        
        st.progress(stats['confirmed'] / stats['total_qualified'] if stats['total_qualified'] > 0 else 0)
        st.caption("進度條：已安排人數 / 總符合資格人數")

        st.divider()
        st.markdown("#### 🔽 各班級詳細名單 (已分類)")

        # --- 顯示各班級名單 ---
        for g in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]:
            confirmed_list = roster[g]["confirmed"]
            pending_list = roster[g]["pending"]
            total_in_grade = len(confirmed_list) + len(pending_list)
            
            # 只有當該班級有人時才顯示 Expander
            with st.expander(f"📍 {g} (已安排: {len(confirmed_list)} / 待確認: {len(pending_list)})", expanded=(total_in_grade > 0)):
                if total_in_grade == 0:
                    st.caption("目前無資料")
                else:
                    # 1. 顯示已安排 (綠色區塊)
                    if confirmed_list:
                        st.markdown(f"**✅ 已安排入學 ({len(confirmed_list)}人)**")
                        st.dataframe(
                            pd.DataFrame(confirmed_list)[['幼兒姓名', '家長', '電話', '備註']], 
                            use_container_width=True, 
                            hide_index=True
                        )
                    
                    # 2. 顯示待確認 (黃色區塊)
                    if pending_list:
                        if confirmed_list: st.divider() # 如果上面有資料，畫條線分隔
                        st.markdown(f"**⏳ 待確認 / 排隊中 ({len(pending_list)}人)**")
                        
                        # 這裡使用 data_editor 讓您可以直接在這裡勾選或改狀態，不用跑回資料中心
                        pending_df = pd.DataFrame(pending_list)
                        pending_df['已聯繫'] = pending_df['聯繫狀態'].apply(lambda x: True if x=='已聯繫' else False)
                        
                        edited_pending = st.data_editor(
                            pending_df,
                            column_config={
                                "原索引": None,
                                "聯繫狀態": None, # 隱藏原始文字欄位，改用 checkbox
                                "已聯繫": st.column_config.CheckboxColumn(width="small"),
                                "報名狀態": st.column_config.SelectboxColumn(options=["排隊中", "已安排", "考慮中", "放棄"], width="medium"),
                                "家長": st.column_config.TextColumn(disabled=True),
                                "電話": st.column_config.TextColumn(disabled=True),
                            },
                            hide_index=True,
                            use_container_width=True,
                            key=f"preview_edit_{search_year}_{g}"
                        )
                        
                        # 儲存按鈕
                        if st.button(f"💾 更新 {g} 狀態", key=f"btn_update_{search_year}_{g}"):
                            full_df = load_registered_data()
                            has_change = False
                            
                            for i, row in edited_pending.iterrows():
                                orig_idx = row['原索引']
                                
                                # 更新聯繫
                                new_con = "已聯繫" if row['已聯繫'] else "未聯繫"
                                if full_df.at[orig_idx, '聯繫狀態'] != new_con:
                                    full_df.at[orig_idx, '聯繫狀態'] = new_con
                                    has_change = True
                                
                                # 更新狀態 (如果在這邊改成已安排，下次就會跑到上面的綠色區塊)
                                if full_df.at[orig_idx, '報名狀態'] != row['報名狀態']:
                                    full_df.at[orig_idx, '報名狀態'] = row['報名狀態']
                                    has_change = True
                                    
                                if full_df.at[orig_idx, '備註'] != row['備註']:
                                    full_df.at[orig_idx, '備註'] = row['備註']
                                    has_change = True
                            
                            if has_change:
                                if sync_data_to_gsheets(full_df):
                                    st.success("更新成功！名單將重新分類...")
                                    time.sleep(0.5)
                                    st.rerun()

    else:
        st.info("資料庫目前為空。")
