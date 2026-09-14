import psycopg2
from psycopg2 import pool
import datetime
import time
import re
from zoneinfo import ZoneInfo
import streamlit as st
import pandas as pd

# ==============================================================================
# 🔐 SYSTEM DEFAULT ADMIN (PROTECTED ROOT ADMIN)
# ==============================================================================
DEFAULT_ADMIN_USER = "Ra Vuth"
DEFAULT_ADMIN_PASS = "12354561"
# ==============================================================================

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


# --- 🚀 CONNECTION POOLING ---
@st.cache_resource
def init_db_pool():
    return psycopg2.pool.SimpleConnectionPool(1, 10, st.secrets["postgres"]["url"])


def get_db_connection():
    return init_db_pool().getconn()


def release_db_connection(conn):
    init_db_pool().putconn(conn)


def get_cambodia_now():
    return datetime.datetime.now(CAMBODIA_TZ)


def get_client_ip():
    """Retrieve client IP address from Streamlit headers."""
    try:
        headers = st.context.headers
        if "x-forwarded-for" in headers:
            return headers["x-forwarded-for"].split(",")[0].strip()
        return headers.get("host", "127.0.0.1")
    except Exception:
        return "127.0.0.1"


def initialize_database():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT '',
            temp_admin_expires TEXT DEFAULT ''
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            ip_address TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            login_time TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cursor.execute("""
        INSERT INTO app_settings (key, value)
        VALUES ('app_title', '📦 កម្មវិធីបិតផ្សាយ ខេត្តបាត់ដំបង')
        ON CONFLICT (key) DO NOTHING
    """)

    cursor.execute("""
        INSERT INTO users (username, password, role, status, created_at)
        VALUES (%s, %s, 'admin', 'approved', %s)
        ON CONFLICT (username) DO NOTHING
    """, (DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASS, get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")))

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            total_items INTEGER NOT NULL
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM projects")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO projects (name, total_items) VALUES ('គម្រោងទី១', 100)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            code INTEGER,
            status TEXT DEFAULT 'មិនទាន់បានពិនិត្យ',
            updated_at TEXT DEFAULT '',
            customer_phone TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            condition TEXT DEFAULT '',
            name_errors TEXT DEFAULT ''
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            code INTEGER,
            action_type TEXT,
            status TEXT DEFAULT '',
            customer_phone TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            condition TEXT DEFAULT '',
            name_errors TEXT DEFAULT '',
            timestamp TEXT
        )
    """)

    conn.commit()
    release_db_connection(conn)


# --- 🌐 IP SESSION MANAGEMENT ---
def register_ip_session(ip, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")
    cursor.execute("""
        INSERT INTO user_sessions (ip_address, username, login_time)
        VALUES (%s, %s, %s)
        ON CONFLICT (ip_address) DO UPDATE SET username = EXCLUDED.username, login_time = EXCLUDED.login_time
    """, (ip, username, now_str))
    conn.commit()
    release_db_connection(conn)


def get_username_by_ip(ip):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM user_sessions WHERE ip_address = %s", (ip,))
    row = cursor.fetchone()
    release_db_connection(conn)
    return row[0] if row else None


def clear_ip_session(ip):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_sessions WHERE ip_address = %s", (ip,))
    conn.commit()
    release_db_connection(conn)


@st.cache_data(ttl=300)
def get_app_title():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM app_settings WHERE key = 'app_title'")
    row = cursor.fetchone()
    release_db_connection(conn)
    return row[0] if row else "📦 កម្មវិធីបិតផ្សាយ ខេត្តបាត់ដំបង"


def set_app_title(new_title):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO app_settings (key, value) VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """, ('app_title', new_title))
    conn.commit()
    release_db_connection(conn)
    st.cache_data.clear()


def check_and_expire_temp_admins():
    conn = get_db_connection()
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
                    cursor.execute("UPDATE users SET role = 'user', temp_admin_expires = '' WHERE id = %s", (user_id,))
            except ValueError:
                pass
    conn.commit()
    release_db_connection(conn)


def get_user_from_db(username):
    check_and_expire_temp_admins()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password, role, status, temp_admin_expires FROM users WHERE username = %s",
                   (username,))
    row = cursor.fetchone()
    release_db_connection(conn)
    return row


def register_user(username, password, requested_role):
    conn = get_db_connection()
    cursor = conn.cursor()
    created_at = get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")
    try:
        cursor.execute("""
            INSERT INTO users (username, password, role, status, created_at)
            VALUES (%s, %s, %s, 'pending', %s)
        """, (username, password, requested_role, created_at))
        conn.commit()
        release_db_connection(conn)
        return True, "សំណើសុំចុះឈ្មោះត្រូវបានបញ្ជូន!"
    except psycopg2.IntegrityError:
        release_db_connection(conn)
        return False, "ឈ្មោះអ្នកប្រើប្រាស់នេះមានរួចហើយ។ សូមជ្រើសរើសឈ្មោះផ្សេង។"


def get_all_users():
    check_and_expire_temp_admins()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, status, created_at, temp_admin_expires FROM users ORDER BY id DESC")
    rows = cursor.fetchall()
    release_db_connection(conn)
    return pd.DataFrame(rows, columns=["ID", "ឈ្មោះអ្នកប្រើប្រាស់", "នាទី", "ស្ថានភាព", "កាលបរិច្ឆេទបង្កើត", "ការផុតកំណត់អែដមីនបណ្តោះអាសន្ន"])


@st.cache_data(ttl=60)
def get_all_projects():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, total_items FROM projects ORDER BY id ASC")
    projects = cursor.fetchall()
    release_db_connection(conn)
    return projects


def create_new_project(name, total_items):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO projects (name, total_items) VALUES (%s, %s) RETURNING id", (name, total_items))
        project_id = cursor.fetchone()[0]
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        cursor.execute("SELECT id, name, total_items FROM projects WHERE name = %s", (name,))
        row = cursor.fetchone()
        project_id, name, total_items = row[0], row[1], row[2]
    release_db_connection(conn)
    st.cache_data.clear()
    return project_id, name, total_items


def update_project_details(project_id, new_name, new_total_items):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE projects SET name = %s, total_items = %s WHERE id = %s",
                       (new_name, new_total_items, project_id))
        conn.commit()
        release_db_connection(conn)
        st.cache_data.clear()
        return True, "បានធ្វើបច្ចុប្បន្នភាពគម្រោងជោគជ័យ!"
    except psycopg2.IntegrityError:
        release_db_connection(conn)
        return False, "ឈ្មោះគម្រោងនេះមានរួចហើយ។"


def delete_project_by_id(project_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM items WHERE project_id = %s", (project_id,))
        cursor.execute("DELETE FROM logs WHERE project_id = %s", (project_id,))
        cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))
        conn.commit()
        release_db_connection(conn)
        st.cache_data.clear()
        return True, "បានលុបគម្រោងជោគជ័យ!"
    except Exception as e:
        conn.rollback()
        release_db_connection(conn)
        return False, f"កំហុសក្នុងការលុបគម្រោង: {str(e)}"


def load_project_items(project_id, total_items):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT code, status, updated_at, customer_phone, notes, condition, name_errors 
        FROM items 
        WHERE project_id = %s 
        ORDER BY code ASC
    """, (project_id,))

    existing_items = {row[0]: (row[1], row[2], row[3], row[4], row[5], row[6]) for row in cursor.fetchall()}
    release_db_connection(conn)

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
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM items WHERE project_id = %s AND code = %s", (project_id, code))
    item = cursor.fetchone()

    if item:
        cursor.execute("""
            UPDATE items SET status = %s, updated_at = %s, customer_phone = %s, notes = %s, condition = %s, name_errors = %s
            WHERE id = %s
        """, (status, custom_timestamp, phone, notes, condition, name_errors, item[0]))
    else:
        cursor.execute("""
            INSERT INTO items (project_id, code, status, updated_at, customer_phone, notes, condition, name_errors) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (project_id, code, status, custom_timestamp, phone, notes, condition, name_errors))

    cursor.execute("""
        INSERT INTO logs (project_id, code, action_type, status, customer_phone, notes, condition, name_errors, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (project_id, code, "កែប្រែទិន្នន័យ", status, phone, notes, condition, name_errors, custom_timestamp))

    conn.commit()
    release_db_connection(conn)


def parse_parcel_codes(input_str, max_limit):
    """Parse string inputs like '1, 2, 5-10, 12' into a sorted list of integer codes."""
    codes = set()
    parts = input_str.split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            subparts = part.split("-")
            if len(subparts) == 2 and subparts[0].isdigit() and subparts[1].isdigit():
                start = int(subparts[0])
                end = int(subparts[1])
                for c in range(min(start, end), max(start, end) + 1):
                    if 1 <= c <= max_limit:
                        codes.add(c)
        elif part.isdigit():
            c = int(part)
            if 1 <= c <= max_limit:
                codes.add(c)
    return sorted(list(codes))


def get_project_history(project_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, code, action_type, status, customer_phone, notes, condition, name_errors 
        FROM logs 
        WHERE project_id = %s 
        ORDER BY id DESC LIMIT 200
    """, (project_id,))
    logs = cursor.fetchall()
    release_db_connection(conn)

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
            @import url('https://fonts.googleapis.com/css2?family=Kantumruy+Pro:wght@300;400;500;600;700&display=swap');
            
            html, body, [class*="css"] {
                font-family: 'Kantumruy Pro', sans-serif !important;
                background-color: #0F172A !important;
                color: #F8FAFC !important;
            }
            .stApp { background: #0F172A !important; padding-bottom: 120px !important; }

            .slate-metric {
                background: #1E293B;
                border-left: 4px solid #10B981;
                border-radius: 8px;
                padding: 0.75rem 1rem;
            }
            .slate-metric-title { color: #94A3B8; font-size: 0.8rem; font-weight: 500; }
            .slate-metric-value { color: #F8FAFC; font-size: 1.5rem; font-weight: 700; }

            .stTextInput input, .stNumberInput input, .stTextArea textarea, div[data-baseweb="select"] > div {
                background-color: #0F172A !important;
                color: #F8FAFC !important;
                border: 1px solid #334155 !important;
                border-radius: 8px !important;
            }

            .stButton > button {
                background: #10B981 !important;
                color: #FFFFFF !important;
                border: 1px solid #059669 !important;
                border-radius: 8px !important;
                font-weight: 600 !important;
            }
            .stButton > button:hover {
                background: #059669 !important;
            }

            /* Floating Sticky Action Bar CSS */
            div[data-testid="stVerticalBlock"] > div:has(div.floating-hover-anchor) {
                position: fixed !important;
                bottom: 0 !important;
                left: 0 !important;
                right: 0 !important;
                width: 100% !important;
                background-color: #1E293B !important;
                border-top: 2px solid #334155 !important;
                padding: 12px 24px !important;
                z-index: 999999 !important;
                box-shadow: 0px -4px 20px rgba(0, 0, 0, 0.5) !important;
            }
        </style>
    """, unsafe_allow_html=True)


def render_auth_page(client_ip):
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

                            register_ip_session(client_ip, username)
                            st.session_state["authenticated"] = True
                            st.session_state["username"] = username
                            st.session_state["role"] = db_role
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
                client_ip = get_client_ip()
                register_ip_session(client_ip, username)
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.session_state["role"] = user[3]
                st.session_state.pop("pending_user", None)
                st.rerun()


@st.dialog(" ")
def show_success_dialog(summary):
    st.markdown(f"""
        <div style="text-align: center;">
            <h3 style="color: #10B981; margin-bottom: 0.5rem;">✓ រក្សាទុកជោគជ័យ</h3>
            <p style="color: #94A3B8; font-size: 0.85rem;">បានធ្វើបច្ចុប្បន្នភាពទិន្នន័យក្បាលដីរួចរាល់</p>
        </div>
    """, unsafe_allow_html=True)

    summary_df = pd.DataFrame([
        {"ព័ត៌មាន": "ក្បាលដី", "ទិន្នន័យ": summary['code']},
        {"ព័ត៌មាន": "ស្ថានភាព", "ទិន្នន័យ": summary['status']},
        {"ព័ត៌មាន": "លេខទូស័ព្ទ", "ទិន្នន័យ": summary['phone']},
        {"ព័ត៌មាន": "លក្ខខណ្ឌ", "ទិន្នន័យ": summary['condition']},
        {"ព័ត៌មាន": "ព័ត៌មានខុសឆ្គង", "ទិន្នន័យ": summary['name_errors']},
        {"ព័ត៌មាន": "ផ្សេងៗ", "ទិន្នន័យ": summary['notes']},
        {"ព័ត៌មាន": "កាលបរិច្ឆេទ & ម៉ោង", "ទិន្នន័យ": summary['timestamp']},
    ])

    st.table(summary_df)
    if st.button("បិទផ្ទាំង", use_container_width=True):
        st.session_state.pop("show_save_success_dialog", None)
        st.rerun()


def main():
    st.set_page_config(page_title="GIS Project Manager Slate", layout="wide")
    inject_custom_css()
    initialize_database()

    client_ip = get_client_ip()

    if not st.session_state.get("authenticated", False):
        saved_username = get_username_by_ip(client_ip)
        if saved_username:
            user = get_user_from_db(saved_username)
            if user and user[4] == "approved":
                st.session_state["authenticated"] = True
                st.session_state["username"] = user[1]
                st.session_state["role"] = user[3]

    if "pending_user" in st.session_state:
        render_pending_waiting_screen(st.session_state["pending_user"])
        return

    if not st.session_state.get("authenticated", False):
        render_auth_page(client_ip)
        return

    current_username = st.session_state.get("username", "Guest")
    user_data = get_user_from_db(current_username)

    if not user_data or user_data[4] == "inactive":
        st.error("គណនីត្រូវបញ្ឈប់។")
        clear_ip_session(client_ip)
        st.session_state["authenticated"] = False
        st.rerun()

    current_role = user_data[3]
    st.session_state["role"] = current_role
    is_admin = current_role in ["admin", "temp_admin"]

    projects = get_all_projects()

    p_col1, p_col2, p_col3 = st.columns([3, 2, 1])
    with p_col1:
        app_title = get_app_title()
        st.markdown(f"<h2 style='margin:0; font-size: 1.5rem; color:#F8FAFC;'>{app_title}</h2>", unsafe_allow_html=True)
    with p_col2:
        if projects:
            proj_dict = {f"{p[1]} (ក្បាលដី: {p[2]})": p for p in projects}

            if "active_project" not in st.session_state or st.session_state["active_project"] not in projects:
                default_p = projects[0]
                st.session_state["active_project"] = (default_p[0], default_p[1], default_p[2])
                st.session_state.pop("cached_df_items", None)

            current_p = st.session_state["active_project"]
            current_label = f"{current_p[1]} (ក្បាលដី: {current_p[2]})"
            labels = list(proj_dict.keys())
            idx = labels.index(current_label) if current_label in labels else 0

            selected_proj_label = st.selectbox("ជ្រើសរើសគម្រោង", labels, index=idx, label_visibility="collapsed")
            active_p = proj_dict[selected_proj_label]

            if st.session_state["active_project"] != (active_p[0], active_p[1], active_p[2]):
                st.session_state["active_project"] = (active_p[0], active_p[1], active_p[2])
                st.session_state.pop("cached_df_items", None)
                st.rerun()

    with p_col3:
        if st.button("🚪 ចាកចេញ", use_container_width=True):
            clear_ip_session(client_ip)
            st.session_state["authenticated"] = False
            st.session_state.pop("active_project", None)
            st.session_state.pop("cached_df_items", None)
            st.rerun()

    if "active_project" not in st.session_state:
        st.info("សូមជ្រើសរើស ឬបង្កើតគម្រោងដើម្បីបន្ត។")
        return

    project_id, project_name, total_items = st.session_state["active_project"]

    nav_choices = [
        "📋 បញ្ជីក្បាលដីសរុប",
        "✏️ កែប្រែទិន្នន័យក្បាលដី",
        "⏳ មិនទាន់បានពិនិត្យ",
        "✅ បានពិនិត្យ",
        "🚫 គ្មានទិន្នន័យ",
        "📊 សរុបលក្ខខណ្ឌ",
        "📜 ប្រវត្តិនៃការកែប្រែ (Logs)",
        "⚙️ កែប្រែគម្រោង"
    ]
    if is_admin:
        nav_choices.append("👥 គ្រប់គ្រងអ្នកប្រើប្រាស់ (Admin)")

    nav_choice = st.radio("Navigation Bar", options=nav_choices, horizontal=True, label_visibility="collapsed")

    if "cached_df_items" not in st.session_state:
        st.session_state["cached_df_items"] = load_project_items(project_id, total_items)

    df_items = st.session_state["cached_df_items"]
    df_valid_items = df_items[~df_items.apply(is_no_data, axis=1)]
    df_no_data_items = df_items[df_items.apply(is_no_data, axis=1)]

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""<div class="slate-metric"><div class="slate-metric-title">ក្បាលដីសរុប</div><div class="slate-metric-value">{total_items}</div></div>""", unsafe_allow_html=True)
    with m2:
        checked_count = len(df_valid_items[df_valid_items["ស្ថានភាព"] == "បានពិនិត្យ"])
        st.markdown(f"""<div class="slate-metric" style="border-left-color: #10B981;"><div class="slate-metric-title">បានពិនិត្យ</div><div class="slate-metric-value" style="color:#10B981;">{checked_count}</div></div>""", unsafe_allow_html=True)
    with m3:
        unchecked_count = len(df_valid_items[df_valid_items["ស្ថានភាព"] == "មិនទាន់បានពិនិត្យ"])
        st.markdown(f"""<div class="slate-metric" style="border-left-color: #F59E0B;"><div class="slate-metric-title">មិនទាន់បានពិនិត្យ</div><div class="slate-metric-value" style="color:#F59E0B;">{unchecked_count}</div></div>""", unsafe_allow_html=True)
    with m4:
        nodata_count = len(df_no_data_items)
        st.markdown(f"""<div class="slate-metric" style="border-left-color: #EF4444;"><div class="slate-metric-title">គ្មានទិន្នន័យ</div><div class="slate-metric-value" style="color:#EF4444;">{nodata_count}</div></div>""", unsafe_allow_html=True)

    st.write("---")

    if st.session_state.get("show_save_success_dialog", False):
        show_success_dialog(st.session_state.get("last_saved_summary", {}))

    if nav_choice == "📋 បញ្ជីក្បាលដីសរុប":
        st.subheader("📋 បញ្ជីក្បាលដីសរុប")
        st.dataframe(df_valid_items, use_container_width=True)

    elif nav_choice == "✏️ កែប្រែទិន្នន័យក្បាលដី":
        st.subheader("✏️ កែប្រែទិន្នន័យក្បាលដី")

        save_mode = st.radio("ទម្រង់នៃការរក្សាទុក", ["មួយក្បាលដី (Single)", "ច្រើនក្បាលដី (Multi-Save)"], horizontal=True)

        if "edit_parcel_code" not in st.session_state:
            st.session_state["edit_parcel_code"] = 1

        code_to_update = st.session_state["edit_parcel_code"]
        current_row = df_items[df_items["ក្បាលដី"] == code_to_update].iloc[0] if not df_items.empty else None

        curr_status = current_row["ស្ថានភាព"] if current_row is not None else "មិនទាន់បានពិនិត្យ"
        curr_phone = current_row["លេខទូស័ព្ទ"] if current_row is not None else ""
        curr_notes = current_row["ផ្សេងៗ"] if current_row is not None else ""
        curr_cond_str = current_row["លក្ខខណ្ឌ"] if (current_row is not None and current_row["លក្ខខណ្ឌ"] not in ["-", "ធម្មតា"]) else ""
        curr_err_str = current_row["ព័ត៌មានខុសឆ្គង"] if (current_row is not None and current_row["ព័ត៌មានខុសឆ្គង"] not in ["-", "គ្មាន"]) else ""

        default_conditions = [c.strip() for c in curr_cond_str.split(", ") if c.strip() in CONDITION_OPTIONS]
        default_err_names = [e.strip() for e in curr_err_str.split(", ") if e.strip() in ERR_NAME_OPTIONS]

        col1, col2 = st.columns(2)
        with col1:
            is_checked = st.checkbox("បានពិនិត្យ", value=(curr_status == "បានពិនិត្យ"))
            no_data_checked = st.checkbox("គ្មានទិន្នន័យ", value=("គ្មានទិន្នន័យ" in default_conditions or curr_notes == "គ្មានទិន្នន័យ"))
            phone_input = st.text_input("លេខទូស័ព្ទ", value=curr_phone)
            notes_input = st.text_area("ផ្សេងៗ", value=curr_notes)

        with col2:
            selected_conditions = st.pills("លក្ខខណ្ឌ", options=CONDITION_OPTIONS, default=default_conditions, selection_mode="multi")
            selected_name_errors = st.pills("ព័ត៌មានខុសឆ្គង (ឈ្មោះ / ថ្ងៃខែ / អាសយដ្ឋាន)", options=ERR_NAME_OPTIONS, default=default_err_names, selection_mode="multi")

        curr_cambodia_dt = get_cambodia_now()
        dt_col1, dt_col2 = st.columns(2)
        with dt_col1: selected_date = st.date_input("កាលបរិច្ឆេទ", value=curr_cambodia_dt.date())
        with dt_col2: selected_time = st.time_input("ម៉ោង", value=curr_cambodia_dt.time())

        # ----------------------------------------------------------------------
        # 📌 FLOATING ACTION HOVER BAR (BOTTOM FIXED)
        # ----------------------------------------------------------------------
        hover_bar = st.container()
        target_codes = []

        with hover_bar:
            st.markdown('<div class="floating-hover-anchor"></div>', unsafe_allow_html=True)

            if save_mode == "មួយក្បាលដី (Single)":
                b_col1, b_col2, b_col3, b_col4 = st.columns([1, 2, 1, 2])

                with b_col1:
                    if st.button("⬅️ ក្បាលដីមុន", use_container_width=True, disabled=(code_to_update <= 1)):
                        st.session_state["edit_parcel_code"] = max(1, code_to_update - 1)
                        st.rerun()

                with b_col2:
                    new_code = st.number_input(
                        "ក្បាលដី #",
                        min_value=1,
                        max_value=total_items,
                        value=code_to_update,
                        key="hover_code_input",
                        label_visibility="collapsed"
                    )
                    if new_code != code_to_update:
                        st.session_state["edit_parcel_code"] = new_code
                        st.rerun()

                with b_col3:
                    if st.button("ក្បាលដីបន្ទាប់ ➡️", use_container_width=True, disabled=(code_to_update >= total_items)):
                        st.session_state["edit_parcel_code"] = min(total_items, code_to_update + 1)
                        st.rerun()

                with b_col4:
                    save_trigger = st.button("💾 រក្សាទុក", type="primary", use_container_width=True)
                
                target_codes = [code_to_update]

            else:
                m_col1, m_col2 = st.columns([4, 2])
                with m_col1:
                    multi_input_str = st.text_input(
                        "បញ្ចូលលេខក្បាលដីច្រើន (ឧទាហរណ៍: 1, 2, 5-10, 15)",
                        value=f"{code_to_update}",
                        key="multi_code_input",
                        label_visibility="collapsed",
                        placeholder="បញ្ចូលលេខក្បាលដី (ឧទាហរណ៍: 1, 2, 5-10, 15)"
                    )
                    target_codes = parse_parcel_codes(multi_input_str, total_items)

                with m_col2:
                    save_trigger = st.button(f"💾 រក្សាទុក ({len(target_codes)} ក្បាលដី)", type="primary", use_container_width=True)

        if save_trigger:
            if not target_codes:
                st.error("សូមបញ្ចូលលេខក្បាលដីត្រឹមត្រូវយ៉ាងហោចណាស់មួយ!")
            else:
                new_status = "បានពិនិត្យ" if is_checked else "មិនទាន់បានពិនិត្យ"
                final_notes = "គ្មានទិន្នន័យ" if no_data_checked and not notes_input.strip() else notes_input

                selected_cond_list = list(selected_conditions) if selected_conditions else []
                if no_data_checked and "គ្មានទិន្នន័យ" not in selected_cond_list:
                    selected_cond_list.append("គ្មានទិន្នន័យ")

                condition_str = ", ".join(selected_cond_list) if selected_cond_list else "ធម្មតា"
                name_err_list = list(selected_name_errors) if selected_name_errors else []
                name_err_str = ", ".join(name_err_list) if name_err_list else "គ្មាន"

                combined_dt = datetime.datetime.combine(selected_date, selected_time)
                formatted_dt = combined_dt.strftime("%d/%m/%Y, %I:%M %p")

                for code in target_codes:
                    update_item_in_db(project_id, code, new_status, phone_input, final_notes, condition_str, name_err_str, formatted_dt)
                
                st.session_state.pop("cached_df_items", None)

                display_codes = ", ".join(map(str, target_codes)) if len(target_codes) <= 5 else f"{target_codes[0]}...{target_codes[-1]} ({len(target_codes)} ក្បាលដី)"

                st.session_state["last_saved_summary"] = {
                    "code": display_codes,
                    "status": new_status,
                    "phone": phone_input,
                    "notes": final_notes,
                    "condition": condition_str,
                    "name_errors": name_err_str,
                    "timestamp": formatted_dt
                }
                st.session_state["show_save_success_dialog"] = True
                st.rerun()

    elif nav_choice == "⏳ មិនទាន់បានពិនិត្យ":
        st.subheader("⏳ បញ្ជីក្បាលដីមិនទាន់បានពិនិត្យ")
        st.dataframe(df_valid_items[df_valid_items["ស្ថានភាព"] == "មិនទាន់បានពិនិត្យ"], use_container_width=True)

    elif nav_choice == "✅ បានពិនិត្យ":
        st.subheader("✅ បញ្ជីក្បាលដីបានពិនិត្យរួចរាល់")
        st.dataframe(df_valid_items[df_valid_items["ស្ថានភាព"] == "បានពិនិត្យ"], use_container_width=True)

    elif nav_choice == "🚫 គ្មានទិន្នន័យ":
        st.subheader("🚫 បញ្ជីក្បាលដីគ្មានទិន្នន័យ")
        st.dataframe(df_no_data_items, use_container_width=True)

    elif nav_choice == "📊 សរុបលក្ខខណ្ឌ":
        st.subheader("📊 សរុបតាមលក្ខខណ្ឌ")
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

    elif nav_choice == "📜 ប្រវត្តិនៃការកែប្រែ (Logs)":
        st.subheader("📜 ប្រវត្តិនៃការកែប្រែ (Logs)")
        st.dataframe(get_project_history(project_id), use_container_width=True)

    elif nav_choice == "⚙️ កែប្រែគម្រោង":
        st.subheader("⚙️ ការកំណត់ និងបង្កើតគម្រោង")

        col_left, col_right = st.columns(2)
        with col_left:
            with st.form("new_proj_form"):
                st.markdown("#### បង្កើតគម្រោងថ្មី")
                p_name_inp = st.text_input("ឈ្មោះគម្រោង", value="គម្រោងថ្មី")
                p_items_inp = st.number_input("ក្បាលដីសរុប", min_value=1, value=100)
                if st.form_submit_button("បង្កើតគម្រោង", use_container_width=True):
                    pid, pname, pitems = create_new_project(p_name_inp.strip(), int(p_items_inp))
                    st.session_state["active_project"] = (pid, pname, pitems)
                    st.session_state.pop("cached_df_items", None)
                    st.success(f"បានបង្កើតគម្រោង {pname} ជោគជ័យ!")
                    st.rerun()

        with col_right:
            with st.form("edit_proj_form"):
                st.markdown("#### កែប្រែគម្រោងបច្ចុប្បន្ន")
                edit_name = st.text_input("ឈ្មោះគម្រោងថ្មី", value=project_name)
                edit_total = st.number_input("ក្បាលដីសរុបថ្មី", min_value=1, value=total_items)
                if st.form_submit_button("ធ្វើបច្ចុប្បន្នភាពគម្រោង", use_container_width=True):
                    success, msg = update_project_details(project_id, edit_name.strip(), int(edit_total))
                    if success:
                        st.session_state["active_project"] = (project_id, edit_name.strip(), int(edit_total))
                        st.session_state.pop("cached_df_items", None)
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        if is_admin:
            st.write("---")
            st.markdown("### 🗑️ លុបគម្រោង (សម្រាប់ Admin តែប៉ុណ្ណោះ)")
            proj_to_del_options = {f"{p[1]} (ID: {p[0]})": p for p in projects}
            selected_del_label = st.selectbox("ជ្រើសរើសគម្រោងដែលត្រូវលុប", list(proj_to_del_options.keys()))
            target_proj = proj_to_del_options[selected_del_label]

            with st.expander("⚠️ បញ្ជាក់ការលុបគម្រោង"):
                st.warning(f"តើអ្នកពិតជាចង់លុបគម្រោង '{target_proj[1]}' នេះមែនទេ? ទិន្នន័យក្បាលដីទាំងអស់នឹងត្រូវលុបចោលទាំងស្រុង!")
                if st.button("🗑️ យល់ព្រមលុបគម្រោង", type="primary", use_container_width=True):
                    ok, msg = delete_project_by_id(target_proj[0])
                    if ok:
                        st.session_state.pop("active_project", None)
                        st.session_state.pop("cached_df_items", None)
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    elif nav_choice == "👥 គ្រប់គ្រងអ្នកប្រើប្រាស់ (Admin)" and is_admin:
        st.subheader("👥 គ្រប់គ្រងអ្នកប្រើប្រាស់ (Admin Control)")

        with st.form("app_title_form_slate"):
            new_title_val = st.text_input("ចំណងជើងកម្មវិធី (App Title)", value=app_title)
            if st.form_submit_button("រក្សាទុកចំណងជើង", use_container_width=True):
                set_app_title(new_title_val.strip())
                st.rerun()

        st.write("---")
        df_u = get_all_users()
        st.dataframe(df_u, use_container_width=True)


if __name__ == "__main__":
    main()
