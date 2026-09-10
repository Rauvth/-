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

ERR_NAME_OPTIONS = [
    "ខុសឈ្មោះប្ដី",
    "ខុសឈ្មោះប្រពន្ធ",
    "ខុសថ្ងៃខែឆ្នាំកំណើតប្ដី",
    "ខុសថ្ងៃខែឆ្នាំកំណើតប្រពន្ធ",
    "ខុសឈ្មោះឪពុកខាងប្ដី",
    "ខុសឈ្មោះឪពុកខាងប្រពន្ធ",
    "ខុសឈ្មោះម្ដាយខាងប្ដី",
    "ខុសឈ្មោះម្ដាយខាងប្រពន្ធ",
    "ខុសថ្ងៃខែឆ្នាំកំណើតឪពុកខាងប្ដី",
    "ខុសថ្ងៃខែឆ្នាំកំណើតឪពុកខាងប្រពន្ធ",
    "ខុសថ្ងៃខែឆ្នាំកំណើម្ដាយខាងប្ដី",
    "ខុសថ្ងៃខែឆ្នាំកំណើតម្ដាយខាងប្រពន្ធ",
    "ខុសអស័យដ្ឋានកំណើត",
    "ខុសអស័យដ្ឋានបច្ចុប្បន្ន"
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
    user_columns = [col[1] for col in cursor.fetchall()]
    if "temp_admin_expires" not in user_columns:
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
            name_errors TEXT DEFAULT '',
            FOREIGN KEY (project_id) REFERENCES projects (id)
        )
    """)

    cursor.execute("PRAGMA table_info(items)")
    item_columns = [col[1] for col in cursor.fetchall()]
    if "name_errors" not in item_columns:
        cursor.execute("ALTER TABLE items ADD COLUMN name_errors TEXT DEFAULT ''")

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
            name_errors TEXT DEFAULT '',
            timestamp TEXT,
            FOREIGN KEY (project_id) REFERENCES projects (id)
        )
    """)

    cursor.execute("PRAGMA table_info(logs)")
    log_columns = [col[1] for col in cursor.fetchall()]
    if "name_errors" not in log_columns:
        cursor.execute("ALTER TABLE logs ADD COLUMN name_errors TEXT DEFAULT ''")

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


def log_activity(project_id, code, action_type, status="", phone="", notes="", condition="", name_errors="", custom_timestamp=""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = custom_timestamp if custom_timestamp else get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")

    cursor.execute("""
        INSERT INTO logs (project_id, code, action_type, status, customer_phone, notes, condition, name_errors, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (project_id, code, action_type, status, phone, notes, condition, name_errors, timestamp))

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
        return False, "ឈ្មោះអ្នកប្រើប្រាស់នេះមានរួចហើយ។ សូមជ្រើសរើសឈ្មោះផ្សេង។"


def get_all_users():
    check_and_expire_temp_admins()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, status, created_at, temp_admin_expires FROM users ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=["ID", "ឈ្មោះអ្នកប្រើប្រាស់", "នាទី", "ស្ថានភាព", "កាលបរិច្ឆេទបង្កើត", "ការផុតកំណត់អែដមីនបណ្តោះអាសន្ន"])


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


def update_project_details(project_id, new_name, new_total_items):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE projects SET name = ?, total_items = ? WHERE id = ?",
                       (new_name, new_total_items, project_id))
        conn.commit()
        conn.close()
        return True, "បានធ្វើបច្ចុប្បន្នភាពគម្រោងជោគជ័យ!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "ឈ្មោះគម្រោងនេះមានរួចហើយ។"


def get_project_items(project_id, total_items):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT code, status, updated_at, customer_phone, notes, condition, name_errors 
        FROM items 
        WHERE project_id = ? 
        ORDER BY code ASC
    """, (project_id,))

    existing_items = {row[0]: (row[1], row[2], row[3], row[4], row[5], row[6]) for row in cursor.fetchall()}
    conn.close()

    data = []
    for code in range(1, total_items + 1):
        if code in existing_items:
            status, updated_at, phone, notes, condition, name_errs = existing_items[code]
            if status in ["Not Yet Checked", ""]:
                status = "មិនទាន់បានពិនិត្យ"
            elif status == "Checked":
                status = "បានពិនិត្យ"
        else:
            status, updated_at, phone, notes, condition, name_errs = "មិនទាន់បានពិនិត្យ", "-", "", "", "", ""

        data.append({
            "ក្បាលដី": code,
            "ស្ថានភាព": status,
            "លេខទូស័ព្ទ": phone,
            "ផ្សេងៗ": notes,
            "លក្ខខណ្ឌ": condition if condition else "ធម្មតា",
            "ព័ត៌មានខុសឆ្គង": name_errs if name_errs else "គ្មាន",
            "បច្ចុប្បន្នភាពចុងក្រោយ": updated_at if updated_at else "-"
        })
    return pd.DataFrame(data)


def is_no_data(row):
    cond = str(row["លក្ខខណ្ឌ"])
    notes = str(row["ផ្សេងៗ"])
    return ("គ្មានទិន្នន័យ" in cond) or (notes.strip() == "គ្មានទិន្នន័យ")


def update_item_in_db(project_id, code, status, phone, notes, condition, name_errors, custom_timestamp):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM items WHERE project_id = ? AND code = ?", (project_id, code))
    item = cursor.fetchone()

    if item:
        cursor.execute("""
            UPDATE items SET status = ?, updated_at = ?, customer_phone = ?, notes = ?, condition = ?, name_errors = ?
            WHERE id = ?
        """, (status, custom_timestamp, phone, notes, condition, name_errors, item[0]))
    else:
        cursor.execute("""
            INSERT INTO items (project_id, code, status, updated_at, customer_phone, notes, condition, name_errors) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (project_id, code, status, custom_timestamp, phone, notes, condition, name_errors))

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
        name_errors=name_errors,
        custom_timestamp=custom_timestamp
    )


def get_project_history(project_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, code, action_type, status, customer_phone, notes, condition, name_errors 
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
            "លក្ខខណ្ឌ": log[6] if log[6] else "ធម្មតា",
            "ព័ត៌មានខុសឆ្គង": log[7] if log[7] else "គ្មាន"
        })
    return pd.DataFrame(data)


def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Kantumruy+Pro:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
            
            /* Slate Deep Theme */
            html, body, [class*="css"] {
                font-family: 'Kantumruy Pro', 'Space Grotesk', sans-serif !important;
                background-color: #0F172A !important;
                color: #F8FAFC !important;
            }
            
            .stApp {
                background: #0F172A !important;
            }

            .slate-metric {
                background: #1E293B;
                border-left: 4px solid #10B981;
                border-radius: 8px;
                padding: 0.75rem 1rem;
            }
            .slate-metric-title {
                color: #94A3B8;
                font-size: 0.8rem;
                font-weight: 500;
            }
            .slate-metric-value {
                color: #F8FAFC;
                font-size: 1.5rem;
                font-weight: 700;
            }

            .stTextInput input, .stNumberInput input, .stTextArea textarea, div[data-baseweb="select"] > div {
                background-color: #0F172A !important;
                color: #F8FAFC !important;
                border: 1px solid #334155 !important;
                border-radius: 8px !important;
            }

            .stButton > button {
                background: #1E293B !important;
                color: #F8FAFC !important;
                border: 1px solid #475569 !important;
                border-radius: 8px !important;
                font-weight: 600 !important;
            }
            .stButton > button:hover {
                border-color: #10B981 !important;
                color: #10B981 !important;
            }
        </style>
    """, unsafe_allow_html=True)


def render_auth_page():
    st.markdown("""
        <div style="text-align: center; max-width: 420px; margin: 3rem auto 1rem auto;">
            <h1 style="font-size: 1.8rem; font-weight: 700; color: #F8FAFC;">ប្រព័ន្ធគ្រប់គ្រងបិតផ្សាយ</h1>
            <p style="color: #94A3B8; font-size: 0.9rem;">សូមចូលប្រើប្រាស់ដើម្បីបន្ត</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        mode = st.radio("ជ្រើសរើស", ["ចូលប្រើប្រាស់", "បង្កើតគណនីថ្មី"], horizontal=True, label_visibility="collapsed")

        if mode == "ចូលប្រើប្រាស់":
            role_type = st.selectbox("ប្រភេទទិន្នន័យចូល", ["អ្នកប្រើប្រាស់ធម្មតា (User)", "អែដមីន (Admin)"])
            with st.form("login_form"):
                username = st.text_input("ឈ្មោះអ្នកប្រើប្រាស់", placeholder="Username")
                password = st.text_input("ពាក្យសម្ងាត់", type="password", placeholder="Password")
                login_btn = st.form_submit_button("ចូលប្រព័ន្ធ", use_container_width=True)

                if login_btn:
                    user = get_user_from_db(username)
                    if user and user[2] == password:
                        db_role = user[3]
                        db_status = user[4]

                        if db_status == "inactive":
                            st.error("🔒 គណនីនេះត្រូវផ្អាក។ សូមទាក់ទង Admin។")
                            return

                        if db_status == "pending":
                            st.session_state["pending_user"] = username
                            st.session_state["authenticated"] = False
                            st.rerun()
                        elif db_status == "approved":
                            if role_type == "អែដមីន (Admin)" and db_role not in ["admin", "temp_admin"]:
                                st.error("គណនីនេះគ្មានសិទ្ធិជា Admin ទេ។")
                                return

                            st.session_state["authenticated"] = True
                            st.session_state["username"] = username
                            st.session_state["role"] = db_role
                            st.session_state["show_startup_popup"] = True
                            st.session_state.pop("pending_user", None)
                            st.rerun()
                    else:
                        st.error("ឈ្មោះអ្នកប្រើប្រាស់ ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវ។")

        else:
            requested_role = st.selectbox("ស្នើសុំនាទី", ["user", "admin"])
            with st.form("register_form"):
                new_user = st.text_input("ឈ្មោះអ្នកប្រើប្រាស់", placeholder="Username")
                new_pass = st.text_input("ពាក្យសម្ងាត់", type="password", placeholder="Password")
                confirm_pass = st.text_input("បញ្ជាក់ពាក្យសម្ងាត់", type="password", placeholder="Confirm Password")
                reg_btn = st.form_submit_button("ស្នើសុំគណនី", use_container_width=True)

                if reg_btn:
                    if not new_user or not new_pass:
                        st.error("សូមបំពេញព័ត៌មានឱ្យគ្រប់។")
                    elif new_pass != confirm_pass:
                        st.error("ពាក្យសម្ងាត់ទាំងពីរមិនត្រូវគ្នាទេ!")
                    else:
                        success, msg = register_user(new_user, new_pass, requested_role)
                        if success:
                            st.session_state["pending_user"] = new_user
                            st.rerun()
                        else:
                            st.error(msg)


def render_pending_waiting_screen(username):
    user = get_user_from_db(username)
    if not user:
        st.error("រកមិនឃើញគណនី។")
        return

    status = user[4]
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if status == "pending":
            st.info(f"⏳ **រង់ចាំការអនុម័ត**\n\nសួស្តី **{username}**! គណនីរបស់អ្នកកំពុងរង់ចាំ Admin ពិនិត្យ។")
            time.sleep(3)
            st.rerun()
        elif status == "approved":
            st.success(f"🎉 **បានអនុម័តជោគជ័យ!**\n\nស្វាគមន៍ **{username}**!")
            if st.button("ចូលទៅកាន់ Dashboard", use_container_width=True):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.session_state["role"] = user[3]
                st.session_state["show_startup_popup"] = True
                st.session_state.pop("pending_user", None)
                st.rerun()


@st.dialog(" ")
def show_success_dialog(summary):
    st.markdown(f"""
        <div style="text-align: center;">
            <h3 style="color: #10B981; margin-bottom: 0.5rem;">✓ រក្សាទុកជោគជ័យ</h3>
       
