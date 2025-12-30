import streamlit as st
import pandas as pd
from datetime import date, datetime
import math

# ==========================================
# 0. 基礎設定 (系統核心)
#    ✅ 改善重點：
#    - 移除 Spinner / Toast 等「轉場效果」
#    - 儘量避免 st.rerun()（能即時更新就即時更新）
#    - 強化日期解析、避免 SettingWithCopyWarning
#    - Google Sheet 寫入改用一次 update，較穩定
# ==========================================
st.set_page_config(page_title="新生與經費管理系統", layout="wide", page_icon="🏫")

# 嘗試匯入 gspread
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    HAS_GSPREAD = True
except Exception:
    HAS_GSPREAD = False

# 嘗試匯入 st_keyup
try:
    from streamlit_keyup import st_keyup
except Exception:
    def st_keyup(label, placeholder=None, key=None):
        return st.text_input(label, placeholder=placeholder, key=key)

st.markdown("""
<style>
    .stApp { font-family: "Microsoft JhengHei", sans-serif; }
    .streamlit-expanderHeader { background-color: #f8f9fa; border: 1px solid #eee; font-weight: bold; color: #333; }
    .big-grade { font-size: 2em; font-weight: bold; color: #ff4b4b; }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] { gap: 0.5rem; }
    .metric-box {
        background-color: #f0f2f6;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
        border: 1px solid #ddd;
    }
</style>
""", unsafe_allow_html=True)

NEW_STATUS_OPTIONS = ["預約參觀", "排隊等待", "確認入學", "確定不收"]

if "calc_memory" not in st.session_state:
    st.session_state["calc_memory"] = {}

if "temp_children" not in st.session_state:
    st.session_state["temp_children"] = []

if "msg_error" not in st.session_state:
    st.session_state["msg_error"] = None

if "msg_ok" not in st.session_state:
    st.session_state["msg_ok"] = None


# ==========================================
# 1. 資料存取邏輯
# ==========================================
SHEET_NAME = "kindergarten_db"
LOCAL_CSV = "kindergarten_local_db.csv"
FINAL_COLS = ["報名狀態", "聯繫狀態", "登記日期", "幼兒姓名", "家長稱呼", "電話",
              "幼兒生日", "預計入學資訊", "推薦人", "備註", "重要性"]


def _safe_str(x) -> str:
    s = "" if x is None else str(x)
    s = s.strip()
    return "" if s.lower() == "nan" else s


def normalize_phone(s: str) -> str:
    s = _safe_str(s)
    if len(s) == 9 and s.startswith("9"):
        return "0" + s
    return s


def parse_roc_date_str(s: str):
    """
    期待格式：民國年/月/日，例如 112/09/01
    回傳：datetime.date 或 None
    """
    s = _safe_str(s)
    if not s:
        return None
    try:
        parts = s.replace("-", "/").replace(".", "/").split("/")
        if len(parts) != 3:
            return None
        y = int(parts[0]) + 1911
        m = int(parts[1])
        d = int(parts[2])
        return date(y, m, d)
    except Exception:
        return None


def to_roc_str(d: date) -> str:
    return f"{d.year-1911}/{d.month:02d}/{d.day:02d}"


def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🔒 系統登入")
        with st.form("login_form", clear_on_submit=False):
            pwd = st.text_input("請輸入通關密碼", type="password")
            ok = st.form_submit_button("登入", type="primary", use_container_width=True)
        if ok:
            if pwd == "1234":
                st.session_state.password_correct = True
            else:
                st.error("密碼錯誤")
    return st.session_state.password_correct


if not check_password():
    st.stop()


@st.cache_resource
def get_gsheet_client():
    if not HAS_GSPREAD:
        return None
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        if "gcp_service_account" not in st.secrets:
            return None
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            dict(st.secrets["gcp_service_account"]), scope
        )
        return gspread.authorize(creds)
    except Exception:
        return None


def connect_to_gsheets_students():
    c = get_gsheet_client()
    if not c:
        return None
    try:
        sh = c.open(SHEET_NAME)
        return sh.sheet1
    except Exception:
        return None


@st.cache_data(ttl=300)
def load_registered_data():
    # 先試 Google Sheet
    sheet = connect_to_gsheets_students()
    df = pd.DataFrame()

    if sheet:
        try:
            data = sheet.get_all_values()
            if data and len(data) >= 1:
                header = data[0]
                rows = data[1:] if len(data) > 1 else []
                df = pd.DataFrame(rows, columns=header)
        except Exception:
            df = pd.DataFrame()

    # 退回本機 CSV
    if df.empty:
        try:
            df = pd.read_csv(LOCAL_CSV, dtype=str)
        except Exception:
            df = pd.DataFrame(columns=FINAL_COLS)

    df = df.fillna("").astype(str)

    # 確保欄位完整
    for c in FINAL_COLS:
        if c not in df.columns:
            df[c] = ""

    df["電話"] = df["電話"].apply(normalize_phone)
    df["聯繫狀態"] = df["聯繫狀態"].replace("", "未聯繫")
    df["報名狀態"] = df["報名狀態"].replace("", "排隊等待")
    df["重要性"] = df["重要性"].replace("", "中")

    df = df[FINAL_COLS]
    return df


def sync_data_to_gsheets(new_df: pd.DataFrame) -> bool:
    try:
        save_df = new_df.copy()

        # 移除系統內部欄位（若存在）
        for c in ["is_contacted", "original_index", "sort_val", "sort_temp", "__force_reload__"]:
            if c in save_df.columns:
                save_df = save_df.drop(columns=[c])

        # 確保欄位完整 + 排序
        for c in FINAL_COLS:
            if c not in save_df.columns:
                save_df[c] = ""

        save_df["重要性"] = save_df["重要性"].replace("", "中").fillna("中")
        save_df = save_df[FINAL_COLS].fillna("").astype(str)

        # 先寫本機
        save_df.to_csv(LOCAL_CSV, index=False, encoding="utf-8-sig")

        # 再寫雲端（若可用）
        sheet = connect_to_gsheets_students()
        if sheet:
            try:
                values = [FINAL_COLS] + save_df.values.tolist()
                sheet.clear()
                sheet.update("A1", values)
            except Exception:
                # 雲端失敗不影響本機保存
                pass

        load_registered_data.clear()
        return True
    except Exception as e:
        st.session_state["msg_error"] = f"儲存錯誤: {e}"
        return False


# ==========================================
# 2. 核心計算邏輯
# ==========================================
def roc_date_input(label, default_date=None, key_suffix=""):
    st.write(f"**{label} (民國)**")
    c1, c2, c3 = st.columns([1, 1, 1])
    if default_date is None:
        default_date = date.today()

    cur_roc = default_date.year - 1911
    y_list = list(range(90, 131))
    y_idx = max(0, min(len(y_list) - 1, cur_roc - 90))

    y = c1.selectbox("年", y_list, index=y_idx, key=f"y_{key_suffix}")
    m = c2.selectbox("月", list(range(1, 13)), index=default_date.month - 1, key=f"m_{key_suffix}")
    d = c3.selectbox("日", list(range(1, 32)), index=min(default_date.day - 1, 30), key=f"d_{key_suffix}")

    try:
        return date(y + 1911, m, d)
    except Exception:
        return date.today()


def get_grade_for_year(birth_date: date, target_roc_year: int) -> str:
    if not birth_date:
        return "未知"

    by_roc = birth_date.year - 1911
    # 以 9/2 為切點
    offset = 1 if (birth_date.month > 9) or (birth_date.month == 9 and birth_date.day >= 2) else 0
    age = target_roc_year - by_roc - offset

    if age < 2:
        return "托嬰中心"
    if age == 2:
        return "幼幼班"
    if age == 3:
        return "小班"
    if age == 4:
        return "中班"
    if age == 5:
        return "大班"
    return "畢業/超齡"


def calculate_admission_roadmap(dob: date):
    today = date.today()
    cur_roc = today.year - 1911
    if today.month < 8:
        cur_roc -= 1

    roadmap = []
    for i in range(6):
        target = cur_roc + i
        grade = get_grade_for_year(dob, target)
        if "畢業" not in grade:
            roadmap.append(f"{target} 學年 - {grade}")
    return roadmap if roadmap else ["年齡不符"]


# ==========================================
# 3. 暫存與提交邏輯
# ==========================================
def add_child_cb():
    y = st.session_state.get("y_add", 112)
    m = st.session_state.get("m_add", 1)
    d = st.session_state.get("d_add", 1)
    try:
        dob = date(y + 1911, m, d)
    except Exception:
        dob = date.today()

    plans = calculate_admission_roadmap(dob)

    st.session_state.temp_children.append({
        "幼兒姓名": _safe_str(st.session_state.get("input_c_name")) or "(未填)",
        "幼兒生日": to_roc_str(dob),
        "報名狀態": "預約參觀",
        "預計入學資訊": plans[0] if plans else "待確認",
        "備註": _safe_str(st.session_state.get("input_note")),
        "重要性": "中",
    })

    st.session_state.input_c_name = ""
    st.session_state.input_note = ""


def submit_all_cb():
    if not st.session_state.temp_children:
        return

    p_name = _safe_str(st.session_state.get("input_p_name"))
    phone = normalize_phone(st.session_state.get("input_phone"))

    if not p_name or not phone:
        st.session_state["msg_error"] = "❌ 家長與電話必填"
        return

    cur_df = load_registered_data()
    rows = []

    p_title = _safe_str(st.session_state.get("input_p_title"))
    referrer = _safe_str(st.session_state.get("input_referrer"))

    for c in st.session_state.temp_children:
        dob_str = _safe_str(c.get("幼兒生日"))
        if dob_str and (parse_roc_date_str(dob_str) is None):
            dob_str = ""

        rows.append({
            "報名狀態": _safe_str(c.get("報名狀態")) or "預約參觀",
            "聯繫狀態": "未聯繫",
            "登記日期": to_roc_str(date.today()),
            "幼兒姓名": _safe_str(c.get("幼兒姓名")),
            "家長稱呼": f"{p_name} {p_title}".strip(),
            "電話": phone,
            "幼兒生日": dob_str,
            "預計入學資訊": _safe_str(c.get("預計入學資訊")),
            "推薦人": referrer,
            "備註": _safe_str(c.get("備註")),
            "重要性": _safe_str(c.get("重要性")) or "中",
        })

    new_df = pd.concat([cur_df, pd.DataFrame(rows)], ignore_index=True)

    if sync_data_to_gsheets(new_df):
        st.session_state["msg_ok"] = f"✅ 成功新增 {len(rows)} 筆資料"
        st.session_state.temp_children = []
        st.session_state.input_p_name = ""
        st.session_state.input_phone = ""
    else:
        st.session_state["msg_error"] = "儲存失敗，請檢查網路或權限。"


# ==========================================
# 4. 主程式與選單
# ==========================================
st.title("🏫 幼兒園新生管理系統")

# 顯示訊息（不使用 toast / spinner）
if st.session_state.get("msg_error"):
    st.error(st.session_state["msg_error"])
    st.session_state["msg_error"] = None

if st.session_state.get("msg_ok"):
    st.success(st.session_state["msg_ok"])
    st.session_state["msg_ok"] = None

df = load_registered_data()

menu = st.sidebar.radio(
    "功能導航",
    ["👶 新增報名", "📂 資料管理中心", "🎓 學年快速查詢", "📅 未來入學預覽", "👩‍🏫 招生缺額與師資試算"],
)

# --- 頁面 1: 新增 ---
if menu == "👶 新增報名":
    st.header("📝 新生報名登記")
    c1, c2 = st.columns(2)

    with c1:
        st.info("👤 **家長資訊**")
        st.text_input("家長姓氏", key="input_p_name")
        st.selectbox("稱謂", ["先生", "小姐", "爸爸", "媽媽"], key="input_p_title")
        st.text_input("電話", key="input_phone")
        st.text_input("推薦人", key="input_referrer")

    with c2:
        st.success("👶 **幼兒資訊**")
        st.text_input("幼兒姓名", key="input_c_name")
        roc_date_input("出生日", date(2022, 1, 1), key_suffix="add")
        st.text_area("備註", key="input_note", height=100)
        st.button("⬇️ 加入暫存", on_click=add_child_cb)

    # ✅ 待送出：可直接編輯 data_editor（你要的功能）
    if st.session_state.temp_children:
        st.divider()
        st.write(f"🛒 **待送出 ({len(st.session_state.temp_children)}) — 可直接編輯**")

        temp_df = pd.DataFrame(st.session_state.temp_children)

        for col in ["幼兒姓名", "幼兒生日", "報名狀態", "預計入學資訊", "備註", "重要性"]:
            if col not in temp_df.columns:
                temp_df[col] = ""

        if "__刪除__" not in temp_df.columns:
            temp_df["__刪除__"] = False

        edited = st.data_editor(
            temp_df,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            column_order=["__刪除__", "幼兒姓名", "幼兒生日", "報名狀態", "預計入學資訊", "重要性", "備註"],
            column_config={
                "__刪除__": st.column_config.CheckboxColumn("刪除", width="small"),
                "幼兒姓名": st.column_config.TextColumn("幼兒姓名", width="medium"),
                "幼兒生日": st.column_config.TextColumn("幼兒生日(民國)", help="格式如 112/09/01", width="small"),
                "報名狀態": st.column_config.SelectboxColumn("狀態", options=NEW_STATUS_OPTIONS, width="small"),
                "預計入學資訊": st.column_config.TextColumn("預計入學", width="medium"),
                "重要性": st.column_config.SelectboxColumn("重要性", options=["優", "中", "差"], width="small"),
                "備註": st.column_config.TextColumn("備註", width="large"),
            },
            key="temp_editor",
        )

        edited2 = edited.copy()
        edited2 = edited2.loc[~edited2["__刪除__"].fillna(False)].copy()
        edited2 = edited2.drop(columns=["__刪除__"], errors="ignore").fillna("").astype(str)

        # 寫回 session_state：讓你編輯後真的生效
        st.session_state.temp_children = edited2.to_dict("records")

        col_a, col_b = st.columns([1, 1])
        with col_a:
            if st.button("🧮 依生日重新推算入學年段（全部）", use_container_width=True):
                new_list = []
                for c in st.session_state.temp_children:
                    dob_obj = parse_roc_date_str(_safe_str(c.get("幼兒生日")))
                    if dob_obj:
                        plans = calculate_admission_roadmap(dob_obj)
                        c["預計入學資訊"] = plans[0] if plans else _safe_str(c.get("預計入學資訊"))
                    new_list.append(c)
                st.session_state.temp_children = new_list

        with col_b:
            st.button("✅ 確認送出", type="primary", on_click=submit_all_cb, use_container_width=True)

# --- 頁面 2: 資料管理 ---
elif menu == "📂 資料管理中心":
    st.header("📂 資料管理中心")
    col_search, col_dl = st.columns([4, 1])

    kw = st_keyup("🔍 搜尋", placeholder="電話或姓名...", key="search_kw")
    if not df.empty:
        col_dl.download_button("📥", df.to_csv(index=False).encode("utf-8-sig"), "data.csv")

    if df.empty:
        st.info("資料庫是空的。")
    else:
        disp = df.copy()
        disp["original_index"] = disp.index

        if kw:
            mask = disp.astype(str).apply(lambda x: x.str.contains(kw, case=False, na=False)).any(axis=1)
            disp = disp.loc[mask].copy()

        disp["is_contacted"] = disp["聯繫狀態"].astype(str).eq("已聯繫")

        t1, t2, t3 = st.tabs(["🔴 待聯繫", "🟢 已聯繫", "📁 全部資料"])

        def render_status_cards(tdf: pd.DataFrame, key_pfx: str):
            status_groups = {
                "🔥 預約與參觀": ["預約參觀"],
                "⏳ 排隊等待 (含其他)": ["排隊等待"],
                "✅ 確認入學": ["確認入學"],
                "❌ 確定不收": ["確定不收"],
            }
            known_list = ["預約參觀", "排隊等待", "確認入學", "確定不收"]

            for group_name, status_list in status_groups.items():
                if group_name == "⏳ 排隊等待 (含其他)":
                    sub_df = tdf.loc[tdf["報名狀態"].isin(status_list) | ~tdf["報名狀態"].isin(known_list)].copy()
                else:
                    sub_df = tdf.loc[tdf["報名狀態"].isin(status_list)].copy()

                if sub_df.empty:
                    continue

                prio_map = {"優": 0, "中": 1, "差": 2}
                sub_df["sort_temp"] = sub_df["重要性"].map(prio_map).fillna(1)
                sub_df = sub_df.sort_values(by=["sort_temp", "登記日期"], ascending=[True, False])

                with st.expander(f"{group_name} (共 {len(sub_df)} 筆)", expanded=True):
                    for _, r in sub_df.iterrows():
                        oid = int(r["original_index"])
                        uk = f"{key_pfx}_{oid}"

                        with st.container(border=True):
                            # 第一列：基本資料
                            c_edit1, c_edit2, c_edit3, c_edit4 = st.columns(4)
                            c_edit1.text_input("幼兒姓名", value=_safe_str(r["幼兒姓名"]), key=f"name_{uk}")
                            c_edit2.text_input("生日 (民國/月/日)", value=_safe_str(r["幼兒生日"]), key=f"dob_{uk}")
                            c_edit3.text_input("家長稱呼", value=_safe_str(r["家長稱呼"]), key=f"pname_{uk}")
                            c_edit4.text_input("電話", value=_safe_str(r["電話"]), key=f"phone_{uk}")

                            # 第二列：狀態 / 入學 / 優先
                            r1, r2, r3, r4 = st.columns([1.2, 1.2, 1.5, 1])
                            r1.checkbox("已聯繫", bool(r["is_contacted"]), key=f"c_{uk}")

                            cur_stat = _safe_str(r["報名狀態"])
                            ui_stat_idx = NEW_STATUS_OPTIONS.index(cur_stat) if cur_stat in NEW_STATUS_OPTIONS else NEW_STATUS_OPTIONS.index("排隊等待")
                            r2.selectbox("狀態", NEW_STATUS_OPTIONS, # label 不顯示
                                         index=ui_stat_idx, key=f"s_{uk}", label_visibility="collapsed")

                            curr_plan = _safe_str(r["預計入學資訊"])
                            plans = [curr_plan] if curr_plan else []
                            dob_obj = parse_roc_date_str(r["幼兒生日"])
                            if dob_obj:
                                auto_plans = calculate_admission_roadmap(dob_obj)
                                for p in auto_plans:
                                    if p not in plans:
                                        plans.append(p)
                            if not plans:
                                plans = ["待確認"]

                            p_idx = plans.index(curr_plan) if curr_plan in plans else 0
                            r3.selectbox("入學年段", plans, index=p_idx, key=f"p_{uk}", label_visibility="collapsed")

                            imp_val = _safe_str(r["重要性"])
                            if imp_val not in ["優", "中", "差"]:
                                imp_val = "中"
                            r4.selectbox("優先", ["優", "中", "差"],
                                         index=["優", "中", "差"].index(imp_val),
                                         key=f"imp_{uk}", label_visibility="collapsed")

                            # 第三列：備註
                            n_val = _safe_str(r["備註"])
                            st.text_area("備註", n_val, key=f"n_{uk}", height=68, placeholder="在此輸入備註...")

                            # 底部：資訊與刪除
                            b1, b2 = st.columns([5, 1])
                            with b1:
                                st.caption(f"登記日: {_safe_str(r['登記日期'])}")
                            with b2:
                                st.checkbox("刪除", key=f"del_{uk}")

        def process_save_status(tdf: pd.DataFrame, key_pfx: str):
            fulldf = load_registered_data().copy()
            changes_made = False
            indices_to_drop = []

            for _, r in tdf.iterrows():
                oid = int(r["original_index"])
                uk = f"{key_pfx}_{oid}"

                if st.session_state.get(f"del_{uk}"):
                    indices_to_drop.append(oid)
                    changes_made = True
                    continue

                # 讀取所有可編輯欄位
                new_name = _safe_str(st.session_state.get(f"name_{uk}"))
                new_dob = _safe_str(st.session_state.get(f"dob_{uk}"))
                new_pname = _safe_str(st.session_state.get(f"pname_{uk}"))
                new_phone = normalize_phone(st.session_state.get(f"phone_{uk}"))

                new_contact = st.session_state.get(f"c_{uk}")
                new_status = _safe_str(st.session_state.get(f"s_{uk}"))
                new_plan = _safe_str(st.session_state.get(f"p_{uk}"))
                new_note = _safe_str(st.session_state.get(f"n_{uk}"))
                new_imp = _safe_str(st.session_state.get(f"imp_{uk}")) or "中"

                if _safe_str(fulldf.at[oid, "幼兒姓名"]) != new_name:
                    fulldf.at[oid, "幼兒姓名"] = new_name
                    changes_made = True

                if _safe_str(fulldf.at[oid, "幼兒生日"]) != new_dob:
                    fulldf.at[oid, "幼兒生日"] = new_dob
                    changes_made = True

                if _safe_str(fulldf.at[oid, "家長稱呼"]) != new_pname:
                    fulldf.at[oid, "家長稱呼"] = new_pname
                    changes_made = True

                if _safe_str(fulldf.at[oid, "電話"]) != new_phone:
                    fulldf.at[oid, "電話"] = new_phone
                    changes_made = True

                if new_contact is not None:
                    ncon_str = "已聯繫" if bool(new_contact) else "未聯繫"
                    if _safe_str(fulldf.at[oid, "聯繫狀態"]) != ncon_str:
                        fulldf.at[oid, "聯繫狀態"] = ncon_str
                        changes_made = True

                if new_status and _safe_str(fulldf.at[oid, "報名狀態"]) != new_status:
                    fulldf.at[oid, "報名狀態"] = new_status
                    changes_made = True

                if new_plan and _safe_str(fulldf.at[oid, "預計入學資訊"]) != new_plan:
                    fulldf.at[oid, "預計入學資訊"] = new_plan
                    changes_made = True

                if _safe_str(fulldf.at[oid, "備註"]) != new_note:
                    fulldf.at[oid, "備註"] = new_note
                    changes_made = True

                if new_imp not in ["優", "中", "差"]:
                    new_imp = "中"
                if _safe_str(fulldf.at[oid, "重要性"]) != new_imp:
                    fulldf.at[oid, "重要性"] = new_imp
                    changes_made = True

            if indices_to_drop:
                fulldf = fulldf.drop(indices_to_drop)

            if not changes_made:
                st.info("系統沒有偵測到任何資料變更。")
                return

            if sync_data_to_gsheets(fulldf):
                st.success("✅ 資料已成功更新並儲存！")
                st.session_state["__force_reload__"] = str(datetime.now())
            else:
                st.error("儲存失敗，請檢查網路或權限。")

        with t1:
            target_data = disp.loc[~disp["is_contacted"]].copy()
            if target_data.empty:
                st.info("🎉 太棒了！目前沒有待聯繫的名單。")
            else:
                with st.form("form_t1"):
                    render_status_cards(target_data, "t1")
                    st.write("")
                    submitted_t1 = st.form_submit_button("💾 儲存所有變更", type="primary", use_container_width=True)
                if submitted_t1:
                    process_save_status(target_data, "t1")

        with t2:
            target_data = disp.loc[disp["is_contacted"]].copy()
            if target_data.empty:
                st.info("目前沒有已聯繫的資料。")
            else:
                with st.form("form_t2"):
                    render_status_cards(target_data, "t2")
                    st.write("")
                    submitted_t2 = st.form_submit_button("💾 儲存所有變更", type="primary", use_container_width=True)
                if submitted_t2:
                    process_save_status(target_data, "t2")

        with t3:
            if disp.empty:
                st.info("資料庫是空的。")
            else:
                with st.form("form_t3"):
                    render_status_cards(disp, "t3")
                    st.write("")
                    submitted_t3 = st.form_submit_button("💾 儲存所有變更", type="primary", use_container_width=True)
                if submitted_t3:
                    process_save_status(disp, "t3")

# --- 頁面 3: 學年查詢 ---
elif menu == "🎓 學年快速查詢":
    st.header("🎓 學年段快速查詢")
    tab_q1, tab_q2 = st.tabs(["📅 生日查詢 (計算)", "📊 年度對照總表"])

    with tab_q1:
        st.caption("輸入出生年月日，立即查看該生目前的學齡與未來入學規劃，無需建立資料。")
        c_mode = st.radio("選擇日期輸入方式", ["民國", "西元"], horizontal=True)
        dob = None
        if c_mode == "民國":
            dob = roc_date_input("請選擇幼兒生日", date(2023, 1, 1), key_suffix="quick_check")
        else:
            dob = st.date_input("請選擇幼兒生日 (西元)", value=date(2023, 1, 1))

        if dob:
            st.divider()
            roadmap = calculate_admission_roadmap(dob)
            current_status = roadmap[0] if roadmap else "年齡不符"
            grade_display = current_status.split(" - ")[-1] if " - " in current_status else current_status
            year_display = current_status.split(" - ")[0] if " - " in current_status else "目前"

            st.markdown(f"<div class='big-grade'>{grade_display}</div>", unsafe_allow_html=True)
            st.caption(f"學年度：{year_display} | 生日：{dob}")
            st.markdown("### 🗓️ 未來入學路徑")

            roadmap_data = []
            for item in roadmap:
                parts = item.split(" - ")
                if len(parts) == 2:
                    roadmap_data.append({"學年度": parts[0], "年段": parts[1]})
            if roadmap_data:
                st.dataframe(pd.DataFrame(roadmap_data), use_container_width=True, hide_index=True)
            else:
                st.warning("年齡超出範圍或無法計算。")

    with tab_q2:
        st.subheader("📊 各年份出生兒童入學對照表")
        cur_roc_year = date.today().year - 1911
        check_years = [cur_roc_year, cur_roc_year + 1, cur_roc_year + 2, cur_roc_year + 3]

        birth_rows = []
        base_y = date.today().year
        for dy in range(0, 8):
            b_year_ad = base_y - dy
            b_year_roc = b_year_ad - 1911
            sample_date = date(b_year_ad, 9, 1)
            row_data = {"西元出生": b_year_ad, "民國出生": b_year_roc}
            for y in check_years:
                row_data[f"{y}學年"] = get_grade_for_year(sample_date, y)
            birth_rows.append(row_data)

        df_ref = pd.DataFrame(birth_rows)
        cols = ["西元出生", "民國出生"] + [f"{y}學年" for y in check_years]
        st.dataframe(df_ref[cols], use_container_width=True, hide_index=True)

# --- 頁面 4: 未來入學預覽 ---
elif menu == "📅 未來入學預覽":
    st.header("📅 未來入學名單預覽")
    cur_y = date.today().year - 1911
    search_y = st.number_input("查詢學年", value=cur_y + 1, min_value=cur_y)
    st.caption(f"💡 系統依據生日自動推算 {search_y} 學年的班級。")
    st.divider()

    if df.empty:
        st.info("資料庫是空的。")
    else:
        roster = {k: {"conf": [], "pend": []} for k in ["托嬰中心", "幼幼班", "小班", "中班", "大班"]}
        stats = {"tot": 0, "conf": 0, "pend": 0}
        all_pending_list = []

        for idx, row in df.iterrows():
            if "確定不收" in _safe_str(row["報名狀態"]):
                continue

            grade = None
            p_str = _safe_str(row["預計入學資訊"])
            if f"{search_y} 學年" in p_str:
                parts = p_str.split(" - ")
                if len(parts) > 1:
                    grade = parts[1].strip()

            if not grade:
                dob = parse_roc_date_str(row["幼兒生日"])
                if dob:
                    grade = get_grade_for_year(dob, int(search_y))

            if grade not in roster:
                continue

            status = _safe_str(row["報名狀態"])
            is_conf = "確認入學" in status

            stats["tot"] += 1
            item = row.to_dict()
            item["idx"] = idx
            item["班級"] = grade

            if is_conf:
                stats["conf"] += 1
                roster[grade]["conf"].append(item)
            else:
                stats["pend"] += 1
                roster[grade]["pend"].append(item)
                all_pending_list.append(item)

        c1, c2, c3 = st.columns(3)
        c1.metric("✅ 確定入學", stats["conf"])
        c2.metric("⏳ 潛在/排隊", stats["pend"])
        c3.metric("📋 總符合人數", stats["tot"])

        with st.expander(f"📋 查看全校【待確認】總表 (共{len(all_pending_list)}人) - 可直接編輯", expanded=False):
            if not all_pending_list:
                st.info("目前沒有待確認的學生。")
            else:
                p_all_df = pd.DataFrame(all_pending_list)
                p_all_df["已聯繫"] = p_all_df["聯繫狀態"].astype(str).eq("已聯繫")

                with st.form("master_pending_form"):
                    edited_master = st.data_editor(
                        p_all_df,
                        column_order=["班級", "已聯繫", "報名狀態", "幼兒姓名", "家長稱呼", "電話", "備註"],
                        column_config={
                            "idx": None,
                            "聯繫狀態": None,
                            "班級": st.column_config.TextColumn(width="small", disabled=True),
                            "已聯繫": st.column_config.CheckboxColumn(width="small"),
                            "報名狀態": st.column_config.SelectboxColumn(options=NEW_STATUS_OPTIONS, width="medium"),
                            "幼兒姓名": st.column_config.TextColumn(disabled=True),
                            "家長稱呼": st.column_config.TextColumn(disabled=True),
                            "電話": st.column_config.TextColumn(disabled=True),
                            "備註": st.column_config.TextColumn(width="large"),
                        },
                        hide_index=True,
                        use_container_width=True,
                    )
                    st.caption("ℹ️ 將狀態改為「確認入學」並儲存，學生就會移動到下方的確認名單。")
                    if st.form_submit_button("💾 儲存待確認清單變更"):
                        fulldf = load_registered_data().copy()
                        chg = False
                        for _, r in edited_master.iterrows():
                            oid = int(r["idx"])
                            ncon = "已聯繫" if bool(r["已聯繫"]) else "未聯繫"
                            if _safe_str(fulldf.at[oid, "聯繫狀態"]) != ncon:
                                fulldf.at[oid, "聯繫狀態"] = ncon
                                chg = True
                            if _safe_str(fulldf.at[oid, "報名狀態"]) != _safe_str(r["報名狀態"]):
                                fulldf.at[oid, "報名狀態"] = _safe_str(r["報名狀態"])
                                chg = True
                            if _safe_str(fulldf.at[oid, "備註"]) != _safe_str(r["備註"]):
                                fulldf.at[oid, "備註"] = _safe_str(r["備註"])
                                chg = True

                        if not chg:
                            st.info("沒有任何變更。")
                        else:
                            if sync_data_to_gsheets(fulldf):
                                st.success("✅ 更新成功")
                            else:
                                st.error("❌ 更新失敗，請檢查網路或權限。")

        st.markdown("---")
        st.subheader(f"🏆 {search_y} 學年度 - 確認入學名單 (僅顯示確認入學)")

        col_l, col_m, col_s = st.columns(3)

        def render_board(column, title, data):
            with column:
                st.markdown(f"##### {title} ({len(data)}人)")
                if not data:
                    st.info("尚無名單")
                else:
                    disp_df = pd.DataFrame(data)[["幼兒姓名", "家長稱呼", "電話", "備註"]]
                    st.dataframe(disp_df, hide_index=True, use_container_width=True)

        render_board(col_l, "🐘 大班", roster["大班"]["conf"])
        render_board(col_m, "🦁 中班", roster["中班"]["conf"])
        render_board(col_s, "🐰 小班", roster["小班"]["conf"])

        st.write("")
        col_t, col_d, col_x = st.columns(3)
        render_board(col_t, "🐥 幼幼班", roster["幼幼班"]["conf"])
        render_board(col_d, "🍼 托嬰中心", roster["托嬰中心"]["conf"])

# --- 頁面 5: 招生缺額與師資試算 ---
elif menu == "👩‍🏫 招生缺額與師資試算":
    st.header("👩‍🏫 招生缺額與師資試算")
    st.info("計算邏輯：使用 **前一學年** 的在校生人數，推算 **預估學年** 升班後還需對外招收多少學生，並計算師資需求。")

    cal_y = st.number_input("📅 預估學年 (目標)", value=date.today().year - 1911 + 1)
    ref_y = int(cal_y) - 1

    ratio_mix = 12 if cal_y >= 115 else 15
    ratio_label = "1:12 (新制)" if cal_y >= 115 else "1:15 (舊制)"
    if cal_y >= 115:
        st.caption(f"ℹ️ 系統偵測為 **115學年度** 以後，3-6歲師生比自動設定為 **{ratio_label}**。")

    def get_prev_counts(year):
        c = {"幼幼": 0, "小": 0, "中": 0}
        for _, r in df.iterrows():
            if "確認入學" not in _safe_str(r["報名狀態"]):
                continue

            gr = None
            p = _safe_str(r["預計入學資訊"])
            if f"{year} 學年" in p:
                parts = p.split(" - ")
                if len(parts) > 1:
                    gr = parts[1].strip()

            if not gr:
                dob = parse_roc_date_str(r["幼兒生日"])
                if dob:
                    gr = get_grade_for_year(dob, year)

            if gr == "幼幼班":
                c["幼幼"] += 1
            elif gr == "小班":
                c["小"] += 1
            elif gr == "中班":
                c["中"] += 1
        return c

    if cal_y not in st.session_state["calc_memory"]:
        db_data = get_prev_counts(ref_y)
        st.session_state["calc_memory"][cal_y] = {
            "prev_t": db_data["幼幼"],
            "prev_s": db_data["小"],
            "prev_m": db_data["中"],
            "target_mixed": 90,
            "target_t": 16,
        }

    data = st.session_state["calc_memory"][cal_y]

    if st.button(f"🔄 重置為 {ref_y} 學年資料庫數據"):
        db_data = get_prev_counts(ref_y)
        data["prev_t"] = db_data["幼幼"]
        data["prev_s"] = db_data["小"]
        data["prev_m"] = db_data["中"]

    st.subheader(f"Step 1: 確認 {ref_y} 學年 (前一年) 在校生人數")
    c1, c2, c3 = st.columns(3)
    data["prev_t"] = c1.number_input(f"{ref_y} 幼幼班人數", value=int(data["prev_t"]), min_value=0)
    data["prev_s"] = c2.number_input(f"{ref_y} 小班人數", value=int(data["prev_s"]), min_value=0)
    data["prev_m"] = c3.number_input(f"{ref_y} 中班人數", value=int(data["prev_m"]), min_value=0)

    rising_students = int(data["prev_t"]) + int(data["prev_s"]) + int(data["prev_m"])

    st.markdown("---")
    st.subheader(f"Step 2: 設定 {cal_y} 學年 (預估年) 目標與計算")

    col_mix, col_t = st.columns(2)

    with col_mix:
        st.markdown("### 🐘 3-6歲 (小中大) 混齡區")
        st.write(f"預計直升舊生： **{rising_students}** 人")
        data["target_mixed"] = st.number_input(f"{cal_y} 學年【小中大】核定總名額", value=int(data["target_mixed"]), min_value=0)
        gap_mixed = int(data["target_mixed"]) - rising_students
        teachers_mix = math.ceil(int(data["target_mixed"]) / ratio_mix) if int(data["target_mixed"]) > 0 else 0

        st.markdown(f"""
        <div class="metric-box">
            <h4>還需招收</h4>
            <h2 style="color: {'green' if gap_mixed >= 0 else 'red'}">{gap_mixed} 人</h2>
            <hr>
            <h4>所需師資 (3-6歲 {ratio_label})</h4>
            <h2>{teachers_mix} 位</h2>
        </div>
        """, unsafe_allow_html=True)

    with col_t:
        st.markdown("### 🐥 2-3歲 (幼幼) 獨立區")
        data["target_t"] = st.number_input(f"{cal_y} 學年【幼幼班】預計招收名額", value=int(data["target_t"]), min_value=0)
        ratio_t = 8
        teachers_t = math.ceil(int(data["target_t"]) / ratio_t) if int(data["target_t"]) > 0 else 0

        st.markdown(f"""
        <div class="metric-box">
            <h4>預計招收</h4>
            <h2 style="color: green">{int(data["target_t"])} 人</h2>
            <hr>
            <h4>所需師資 (2-3歲 1:8)</h4>
            <h2>{teachers_t} 位</h2>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.caption(f"總結：{cal_y} 學年度全園需聘 **{teachers_mix + teachers_t}** 位老師 (不含托嬰)。")
