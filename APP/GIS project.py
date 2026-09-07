import sqlite3
import datetime
import time
from zoneinfo import ZoneInfo
import streamlit as st
import pandas as pd

# ==============================================================================
# 🔐 SYSTEM DEFAULT ADMIN (PROTECTED ROOT ADMIN)
# ==============================================================================
DEFAULT_ADMIN_USER = "Ra Vuth"
DEFAULT_ADMIN_PASS = "12354561"
# ==============================================================================

DB_NAME = "project_manager.db"
CAMBODIA_TZ = ZoneInfo("Asia/Phnom_Penh")

CONDITION_OPTIONS = [
    "គ្មានទិន្នន័យ",
    "ទំនាស់",
    "ខុសប្រភេទទ្រព្យ",
    "ខុសប្រភេទដី",
    "ខុសអក្ខរវិរុទ្ខ",
    "កែតម្រូវព្រំដី",
    "គ្មានហត្ថលេខា"
]


def get_cambodia_now():
    """Returns current datetime in Cambodia timezone."""
    return datetime.datetime.now(CAMBODIA_TZ)


def initialize_database():
    """Sets up database tables including multi-user accounts, temporary admin roles, and status management."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT '',
            temp_admin_expires TEXT DEFAULT ''
        )
    """)

    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if "temp_admin_expires" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN temp_admin_expires TEXT DEFAULT ''")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO app_settings (key, value)
        VALUES ('app_title', '📦 កម្មវិធីបិតផ្សាយ ខេត្តបាត់ដំបង')
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO users (username, password, role, status, created_at)
        VALUES (?, ?, 'admin', 'approved', ?)
    """, (DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASS, get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")))

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            total_items INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            code INTEGER,
            status TEXT DEFAULT 'មិនទាន់បានពិនិត្យ',
            updated_at TEXT DEFAULT '',
            customer_phone TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            condition TEXT DEFAULT '',
            FOREIGN KEY (project_id) REFERENCES projects (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            code INTEGER,
            action_type TEXT,
            status TEXT DEFAULT '',
            customer_phone TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            condition TEXT DEFAULT '',
            timestamp TEXT,
            FOREIGN KEY (project_id) REFERENCES projects (id)
        )
    """)

    conn.commit()
    conn.close()


def get_app_title():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM app_settings WHERE key = 'app_title'")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "📦 កម្មវិធីបិតផ្សាយ ខេត្តបាត់ដំបង"


def set_app_title(new_title):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('app_title', ?)", (new_title,))
    conn.commit()
    conn.close()


def log_activity(project_id, code, action_type, status="", phone="", notes="", condition="", custom_timestamp=""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = custom_timestamp if custom_timestamp else get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")

    cursor.execute("""
        INSERT INTO logs (project_id, code, action_type, status, customer_phone, notes, condition, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (project_id, code, action_type, status, phone, notes, condition, timestamp))

    conn.commit()
    conn.close()


def check_and_expire_temp_admins():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, temp_admin_expires FROM users WHERE role = 'temp_admin'")
    rows = cursor.fetchall()

    now = get_cambodia_now()
    for row in rows:
        user_id, username, expire_str = row
        if expire_str:
            try:
                expire_dt = datetime.datetime.strptime(expire_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CAMBODIA_TZ)
                if now >= expire_dt:
                    cursor.execute("UPDATE users SET role = 'user', temp_admin_expires = '' WHERE id = ?", (user_id,))
            except ValueError:
                pass
    conn.commit()
    conn.close()


def get_user_from_db(username):
    check_and_expire_temp_admins()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password, role, status, temp_admin_expires FROM users WHERE username = ?",
                   (username,))
    row = cursor.fetchone()
    conn.close()
    return row


def register_user(username, password, requested_role):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    created_at = get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")
    try:
        cursor.execute("""
            INSERT INTO users (username, password, role, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        """, (username, password, requested_role, created_at))
        conn.commit()
        conn.close()
        return True, "សំណើសុំចុះឈ្មោះត្រូវបានបញ្ជូន!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "ឈ្មោះអ្នកប្រើប្រាស់នេះមានរួចហើយ។"


def get_all_users():
    check_and_expire_temp_admins()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, status, created_at, temp_admin_expires FROM users ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=["ID", "ឈ្មោះអ្នកប្រើប្រាស់", "នាទី", "ស្ថានភាព", "កាលបរិច្ឆេទបង្កើត", "ការផុតកំណត់អែដមីនបណ្តោះអាសន្ន"])


def update_user_status(user_id, status):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
    conn.commit()
    conn.close()


def delete_user_account(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def set_temporary_admin(user_id, expiration_dt):
    exp_str = expiration_dt.strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = 'temp_admin', temp_admin_expires = ? WHERE id = ?", (exp_str, user_id))
    conn.commit()
    conn.close()


def get_all_projects():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, total_items FROM projects")
    projects = cursor.fetchall()
    conn.close()
    return projects


def create_new_project(name, total_items):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO projects (name, total_items) VALUES (?, ?)", (name, total_items))
        conn.commit()
        project_id = cursor.lastrowid
        log_activity(project_id, None, "បានបង្កើតគម្រោង",
                     notes=f"បានបង្កើតគម្រោង '{name}' ដែលមានក្បាលដីសរុប {total_items}")
    except sqlite3.IntegrityError:
        cursor.execute("SELECT id, name, total_items FROM projects WHERE name = ?", (name,))
        row = cursor.fetchone()
        project_id, name, total_items = row[0], row[1], row[2]
    conn.close()
    return project_id, name, total_items


def get_project_items(project_id, total_items):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT code, status, updated_at, customer_phone, notes, condition 
        FROM items 
        WHERE project_id = ? 
        ORDER BY code ASC
    """, (project_id,))

    existing_items = {row[0]: (row[1], row[2], row[3], row[4], row[5]) for row in cursor.fetchall()}
    conn.close()

    data = []
    for code in range(1, total_items + 1):
        if code in existing_items:
            status, updated_at, phone, notes, condition = existing_items[code]
            if status in ["Not Yet Checked", ""]:
                status = "មិនទាន់បានពិនិត្យ"
            elif status == "Checked":
                status = "បានពិនិត្យ"
        else:
            status, updated_at, phone, notes, condition = "មិនទាន់បានពិនិត្យ", "-", "", "", ""

        data.append({
            "ក្បាលដី": code,
            "ស្ថានភាព": status,
            "លេខទូស័ព្ទ": phone,
            "ផ្សេងៗ": notes,
            "លក្ខខណ្ឌ": condition if condition else "ធម្មតា",
            "បច្ចុប្បន្នភាពចុងក្រោយ": updated_at if updated_at else "-"
        })
    return pd.DataFrame(data)


def is_no_data(row):
    cond = str(row["លក្ខខណ្ឌ"])
    notes = str(row["ផ្សេងៗ"])
    return ("គ្មានទិន្នន័យ" in cond) or (notes.strip() == "គ្មានទិន្នន័យ")


def update_item_in_db(project_id, code, status, phone, notes, condition, custom_timestamp):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM items WHERE project_id = ? AND code = ?", (project_id, code))
    item = cursor.fetchone()

    if item:
        cursor.execute("""
            UPDATE items SET status = ?, updated_at = ?, customer_phone = ?, notes = ?, condition = ? 
            WHERE id = ?
        """, (status, custom_timestamp, phone, notes, condition, item[0]))
    else:
        cursor.execute("""
            INSERT INTO items (project_id, code, status, updated_at, customer_phone, notes, condition) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (project_id, code, status, custom_timestamp, phone, notes, condition))

    conn.commit()
    conn.close()

    log_activity(
        project_id=project_id,
        code=code,
        action_type="កែប្រែទិន្នន័យ",
        status=status,
        phone=phone,
        notes=notes,
        condition=condition,
        custom_timestamp=custom_timestamp
    )


def get_project_history(project_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, code, action_type, status, customer_phone, notes, condition 
        FROM logs 
        WHERE project_id = ? 
        ORDER BY id DESC
    """, (project_id,))
    logs = cursor.fetchall()
    conn.close()

    data = []
    for log in logs:
        log_status = log[3]
        if log_status in ["Not Yet Checked", ""]:
            log_status = "មិនទាន់បានពិនិត្យ"
        elif log_status == "Checked":
            log_status = "បានពិនិត្យ"

        data.append({
            "កាលបរិច្ឆេទ & ម៉ោង": log[0] if log[0] else "",
            "ក្បាលដី": log[1] if log[1] else "",
            "សកម្មភាព": log[2] if log[2] else "",
            "ស្ថានភាព": log_status if log_status else "",
            "លេខទូស័ព្ទ": log[4] if log[4] else "",
            "ផ្សេងៗ": log[5] if log[5] else "",
            "លក្ខខណ្ឌ": log[6] if log[6] else "ធម្មតា"
        })
    return pd.DataFrame(data)


def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Kantumruy+Pro:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
            
            /* Clean Professional ERP Palette */
            html, body, [class*="css"] {
                font-family: 'Kantumruy Pro', 'Plus Jakarta Sans', sans-serif !important;
                background-color: #F8FAFC !important;
                color: #0F172A !important;
            }
            
            /* Main Layout */
            .stApp {
                background-color: #F8FAFC !important;
            }
            
            /* Header Box */
            .erp-header {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 12px;
                padding: 1.25rem 1.75rem;
                margin-bottom: 1.25rem;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }
            .erp-header h1 {
                font-size: 1.4rem !important;
                color: #0F172A !important;
                font-weight: 700 !important;
                margin: 0 !important;
            }
            .erp-header p {
                color: #64748B !important;
                font-size: 0.875rem !important;
                margin: 0.25rem 0 0 0 !important;
            }

            /* Metric Cards */
            .stat-box {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
                padding: 1rem 1.25rem;
                box-shadow: 0 1px 2px rgba(0,0,0,0.04);
            }
            .stat-label {
                font-size: 0.8rem;
                color: #64748B;
                font-weight: 500;
            }
            .stat-num {
                font-size: 1.6rem;
                font-weight: 700;
                color: #0F172A;
                margin-top: 0.15rem;
            }

            /* Form Styling */
            div[data-testid="stForm"] {
                background: #FFFFFF !important;
                border: 1px solid #E2E8F0 !important;
                border-radius: 12px !important;
                padding: 1.5rem !important;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
            }

            /* Buttons */
            .stButton > button {
                border-radius: 8px !important;
                font-weight: 600 !important;
                background-color: #FFFFFF !important;
                border: 1px solid #CBD5E1 !important;
                color: #334155 !important;
            }
            .stButton > button:hover {
                border-color: #2563EB !important;
                color: #2563EB !important;
                background-color: #EFF6FF !important;
            }
        </style>
    """, unsafe_allow_html=True)


def render_auth_page():
    st.markdown("""
        <div style="text-align: center; max-width: 400px; margin: 4rem auto 2rem auto;">
            <h2 style="font-weight: 700; color: #0F172A;">ប្រព័ន្ធគ្រប់គ្រងបិតផ្សាយ</h2>
            <p style="color: #64748B; font-size: 0.9rem;">សូមបញ្ចូលគណនីរបស់អ្នក</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("erp_login_form"):
            username = st.text_input("ឈ្មោះអ្នកប្រើប្រាស់", placeholder="Username")
            password = st.text_input("ពាក្យសម្ងាត់", type="password", placeholder="Password")
            login_btn = st.form_submit_button("ចូលប្រើប្រាស់", use_container_width=True)

            if login_btn:
                user = get_user_from_db(username)
                if user and user[2] == password:
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = username
                    st.session_state["role"] = user[3]
                    st.rerun()
                else:
                    st.error("ឈ្មោះអ្នកប្រើប្រាស់ ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវ។")


def main():
    st.set_page_config(page_title="ERP Land Inventory", layout="wide")
    inject_custom_css()
    initialize_database()

    if not st.session_state.get("authenticated", False):
        render_auth_page()
        return

    current_username = st.session_state.get("username", "User")
    user_data = get_user_from_db(current_username)
    is_admin = user_data[3] in ["admin", "temp_admin"] if user_data else False

    projects = get_all_projects()
    if not projects:
        st.info("មិនទាន់មានគម្រោងទេ។ សូមទាក់ទង Admin។")
        return

    # Top Control Bar (Project Selector & Logout)
    top_c1, top_c2, top_c3 = st.columns([4, 2, 1])
    with top_c1:
        proj_dict = {f"{p[1]} (ក្បាលដីសរុប: {p[2]})": p for p in projects}
        selected_p_label = st.selectbox("ជ្រើសរើសគម្រោង", list(proj_dict.keys()))
        active_p = proj_dict[selected_p_label]
        project_id, project_name, total_items = active_p[0], active_p[1], active_p[2]
    with top_c3:
        st.write("&#160;")
        if st.button("🚪 ចាកចេញ", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

    app_title = get_app_title()

    # ERP Header Banner
    st.markdown(f"""
        <div class="erp-header">
            <h1>{app_title}</h1>
            <p>គម្រោង: <b>{project_name}</b> | គណនីប្រើប្រាស់: <b>{current_username}</b></p>
        </div>
    """, unsafe_allow_html=True)

    df_items = get_project_items(project_id, total_items)
    df_valid_items = df_items[~df_items.apply(is_no_data, axis=1)]
    df_no_data_items = df_items[df_items.apply(is_no_data, axis=1)]

    # Real-time Metrics Ribbon
    m1, m2, m3, m4 = st.columns(4)
    checked_cnt = len(df_valid_items[df_valid_items["ស្ថានភាព"] == "បានពិនិត្យ"])
    unchecked_cnt = len(df_valid_items[df_valid_items["ស្ថានភាព"] == "មិនទាន់បានពិនិត្យ"])
    nodata_cnt = len(df_no_data_items)

    with m1:
        st.markdown(f"""<div class="stat-box"><div class="stat-label">ក្បាលដីសរុប</div><div class="stat-num">{total_items}</div></div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""<div class="stat-box"><div class="stat-label">បានពិនិត្យរួច</div><div class="stat-num" style="color:#059669;">{checked_cnt}</div></div>""", unsafe_allow_html=True)
        st.progress(checked_cnt / total_items if total_items else 0)
    with m3:
        st.markdown(f"""<div class="stat-box"><div class="stat-label">មិនទាន់បានពិនិត្យ</div><div class="stat-num" style="color:#D97706;">{unchecked_cnt}</div></div>""", unsafe_allow_html=True)
        st.progress(unchecked_cnt / total_items if total_items else 0)
    with m4:
        st.markdown(f"""<div class="stat-box"><div class="stat-label">គ្មានទិន្នន័យ</div><div class="stat-num" style="color:#E11D48;">{nodata_cnt}</div></div>""", unsafe_allow_html=True)
        st.progress(nodata_cnt / total_items if total_items else 0)

    st.write("---")

    # Native Clean Tabs
    t1, t2, t3, t4, t5, t6, t7 = st.tabs([
        "📋 បញ្ជីសរុប",
        "✏️ កែប្រែក្បាលដី",
        "⏳ មិនទាន់ពិនិត្យ",
        "✅ បានពិនិត្យ",
        "🚫 គ្មានទិន្នន័យ",
        "📊 លក្ខខណ្ឌ",
        "📜 Logs"
    ])

    with t1:
        st.dataframe(df_valid_items, use_container_width=True)

    with t2:
        st.subheader("កែប្រែទិន្នន័យក្បាលដី")
        code_to_update = st.number_input("លេខក្បាលដី", min_value=1, max_value=total_items, step=1)
        current_row = df_items[df_items["ក្បាលដី"] == code_to_update].iloc[0] if not df_items.empty else None

        curr_status = current_row["ស្ថានភាព"] if current_row is not None else "មិនទាន់បានពិនិត្យ"
        curr_phone = current_row["លេខទូស័ព្ទ"] if current_row is not None else ""
        curr_notes = current_row["ផ្សេងៗ"] if current_row is not None else ""
        curr_cond_str = current_row["លក្ខខណ្ឌ"] if (current_row is not None and current_row["លក្ខខណ្ឌ"] not in ["-", "ធម្មតា"]) else ""
        default_conditions = [c.strip() for c in curr_cond_str.split(", ") if c.strip() in CONDITION_OPTIONS]

        with st.form("erp_update_form"):
            c_a, c_b = st.columns(2)
            with c_a:
                is_checked = st.checkbox("បានពិនិត្យ", value=(curr_status == "បានពិនិត្យ"))
                no_data_checked = st.checkbox("គ្មានទិន្នន័យ", value=("គ្មានទិន្នន័យ" in default_conditions or curr_notes == "គ្មានទិន្នន័យ"))
                phone_input = st.text_input("លេខទូស័ព្ទ", value=curr_phone)
            with c_b:
                selected_conditions = st.multiselect("លក្ខខណ្ឌ", options=CONDITION_OPTIONS, default=default_conditions)
                notes_input = st.text_area("ផ្សេងៗ", value=curr_notes)

            curr_cambodia_dt = get_cambodia_now()
            dt1, dt2 = st.columns(2)
            with dt1: selected_date = st.date_input("កាលបរិច្ឆេទ", value=curr_cambodia_dt.date())
            with dt2: selected_time = st.time_input("ម៉ោង", value=curr_cambodia_dt.time())

            if st.form_submit_button("រក្សាទុក", use_container_width=True):
                new_status = "បានពិនិត្យ" if is_checked else "មិនទាន់បានពិនិត្យ"
                final_notes = "គ្មានទិន្នន័យ" if no_data_checked and not notes_input.strip() else notes_input

                if no_data_checked and "គ្មានទិន្នន័យ" not in selected_conditions:
                    selected_conditions.append("គ្មានទិន្នន័យ")

                condition_str = ", ".join(selected_conditions) if selected_conditions else "ធម្មតា"
                combined_dt = datetime.datetime.combine(selected_date, selected_time)
                formatted_dt = combined_dt.strftime("%d/%m/%Y, %I:%M %p")

                update_item_in_db(project_id, code_to_update, new_status, phone_input, final_notes, condition_str, formatted_dt)
                st.success("បានរក្សាទុកទិន្នន័យជោគជ័យ!")
                st.rerun()

    with t3:
        st.dataframe(df_valid_items[df_valid_items["ស្ថានភាព"] == "មិនទាន់បានពិនិត្យ"], use_container_width=True)

    with t4:
        st.dataframe(df_valid_items[df_valid_items["ស្ថានភាព"] == "បានពិនិត្យ"], use_container_width=True)

    with t5:
        st.dataframe(df_no_data_items, use_container_width=True)

    with t6:
        summary_data = []
        for option in CONDITION_OPTIONS:
            matching_codes = []
            for _, row in df_items.iterrows():
                item_cond = row["លក្ខខណ្ឌ"]
                if item_cond and item_cond not in ["-", "ធម្មតា"]:
                    cond_list = [c.strip() for c in item_cond.split(",")]
                    if option in cond_list:
                        matching_codes.append(str(row["ក្បាលដី"]))

            summary_data.append({
                "ប្រភេទលក្ខខណ្ឌ": option,
                "ចំនួនសរុប": len(matching_codes),
                "បញ្ជីលេខក្បាលដី": ", ".join(matching_codes) if matching_codes else ""
            })
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True)

    with t7:
        st.dataframe(get_project_history(project_id), use_container_width=True)


if __name__ == "__main__":
    main()
