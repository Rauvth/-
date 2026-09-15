import psycopg2
from psycopg2 import pool
import datetime
import time
import re
from zoneinfo import ZoneInfo
import streamlit as st
import pandas as pd
from contextlib import contextmanager

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


# --- 🚀 SAFE CONNECTION POOLING ---
@st.cache_resource
def init_db_pool():
    # Supports up to 20 concurrent database connections safely
    return psycopg2.pool.SimpleConnectionPool(1, 20, st.secrets["postgres"]["url"])

@contextmanager
def get_db():
    """Context manager that guarantees connections return to pool even on exception."""
    pool_obj = init_db_pool()
    conn = pool_obj.getconn()
    try:
        yield conn
    finally:
        pool_obj.putconn(conn)


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
    with get_db() as conn:
        with conn.cursor() as cursor:
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


# --- 🌐 IP SESSION MANAGEMENT ---
def register_ip_session(ip, username):
    with get_db() as conn:
        with conn.cursor() as cursor:
            now_str = get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")
            cursor.execute("""
                INSERT INTO user_sessions (ip_address, username, login_time)
                VALUES (%s, %s, %s)
                ON CONFLICT (ip_address) DO UPDATE SET username = EXCLUDED.username, login_time = EXCLUDED.login_time
            """, (ip, username, now_str))
            conn.commit()


def get_username_by_ip(ip):
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT username FROM user_sessions WHERE ip_address = %s", (ip,))
            row = cursor.fetchone()
            return row[0] if row else None


def clear_ip_session(ip):
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM user_sessions WHERE ip_address = %s", (ip,))
            conn.commit()


@st.cache_data(ttl=300)
def get_app_title():
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT value FROM app_settings WHERE key = 'app_title'")
            row = cursor.fetchone()
            return row[0] if row else "📦 កម្មវិធីបិតផ្សាយ ខេត្តបាត់ដំបង"


def set_app_title(new_title):
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO app_settings (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, ('app_title', new_title))
            conn.commit()
    st.cache_data.clear()


def check_and_expire_temp_admins():
    with get_db() as conn:
        with conn.cursor() as cursor:
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


def get_user_from_db(username):
    check_and_expire_temp_admins()
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, password, role, status, temp_admin_expires FROM users WHERE username = %s",
                           (username,))
            return cursor.fetchone()


def register_user(username, password, requested_role):
    with get_db() as conn:
        with conn.cursor() as cursor:
            created_at = get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")
            try:
                cursor.execute("""
                    INSERT INTO users (username, password, role, status, created_at)
                    VALUES (%s, %s, %s, 'pending', %s)
                """, (username, password, requested_role, created_at))
                conn.commit()
                return True, "សំណើសុំចុះឈ្មោះត្រូវបានបញ្ជូន!"
            except psycopg2.IntegrityError:
                return False, "ឈ្មោះអ្នកប្រើប្រាស់នេះមានរួចហើយ។ សូមជ្រើសរើសឈ្មោះផ្សេង។"


def get_all_users():
    check_and_expire_temp_admins()
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, role, status, created_at, temp_admin_expires FROM users ORDER BY id DESC")
            rows = cursor.fetchall()
            return pd.DataFrame(rows, columns=["ID", "ឈ្មោះអ្នកប្រើប្រាស់", "នាទី", "ស្ថានភាព", "កាលបរិច្ឆេទបង្កើត", "ការផុតកំណត់អែដមីនបណ្តោះអាសន្ន"])


@st.cache_data(ttl=60)
def get_all_projects():
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name, total_items FROM projects ORDER BY id ASC")
            return cursor.fetchall()


def create_new_project(name, total_items):
    with get_db() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute("INSERT INTO projects (name, total_items) VALUES (%s, %s) RETURNING id", (name, total_items))
                project_id = cursor.fetchone()[0]
                conn.commit()
            except psycopg2.IntegrityError:
                conn.rollback()
                cursor.execute("SELECT id, name, total_items FROM projects WHERE name = %s", (name,))
                row = cursor.fetchone()
                project_id, name, total_items = row[0], row[1], row[2]
            st.cache_data.clear()
            return project_id, name, total_items


def update_project_details(project_id, new_name, new_total_items):
    with get_db() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute("UPDATE projects SET name = %s, total_items = %s WHERE id = %s",
                               (new_name, new_total_items, project_id))
                conn.commit()
                st.cache_data.clear()
                return True, "បានធ្វើបច្ចុប្បន្នភាពគម្រោងជោគជ័យ!"
            except psycopg2.IntegrityError:
                return False, "ឈ្មោះគម្រោងនេះមានរួចហើយ។"


def delete_project_by_id(project_id):
    with get_db() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute("DELETE FROM items WHERE project_id = %s", (project_id,))
                cursor.execute("DELETE FROM logs WHERE project_id = %s", (project_id,))
                cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))
                conn.commit()
                st.cache_data.clear()
                return True, "បានលុបគម្រោងជោគជ័យ!"
            except Exception as e:
                conn.rollback()
                return False, f"កំហុសក្នុងការលុបគម្រោង: {str(e)}"


def load_project_items(project_id, total_items):
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT code, status, updated_at, customer_phone, notes, condition, name_errors 
                FROM items 
                WHERE project_id = %s 
                ORDER BY code ASC
            """, (project_id,))

            existing_items = {row[0]: (row[1], row[2], row[3], row[4], row[5], row[6]) for row in cursor.fetchall()}

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
    notes = str(row["ផ្សេងៗ"]).strip()
    return cond == "គ្មានទិន្នន័យ" or "គ្មានទិន្នន័យ" in notes


def update_parcel_status(project_id, code, new_status, phone, notes, condition, name_errors):
    now_str = get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")
    phone = str(phone).strip() if phone else ""
    notes = str(notes).strip() if notes else ""
    condition = str(condition).strip() if condition else ""

    if isinstance(name_errors, list):
        name_errors = ", ".join(name_errors)
    else:
        name_errors = str(name_errors).strip() if name_errors else ""

    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO items (project_id, code, status, updated_at, customer_phone, notes, condition, name_errors)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (project_id, code, new_status, now_str, phone, notes, condition, name_errors))

            cursor.execute("""
                UPDATE items 
                SET status = %s, updated_at = %s, customer_phone = %s, notes = %s, condition = %s, name_errors = %s 
                WHERE project_id = %s AND code = %s
            """, (new_status, now_str, phone, notes, condition, name_errors, project_id, code))

            cursor.execute("""
                INSERT INTO logs (project_id, code, action_type, status, customer_phone, notes, condition, name_errors, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (project_id, code, 'កែប្រែ', new_status, phone, notes, condition, name_errors, now_str))

            conn.commit()


def get_logs_for_project(project_id):
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT code, action_type, status, customer_phone, notes, condition, name_errors, timestamp
                FROM logs
                WHERE project_id = %s
                ORDER BY id DESC
            """, (project_id,))
            rows = cursor.fetchall()
            return pd.DataFrame(rows, columns=["ក្បាលដី", "សកម្មភាព", "ស្ថានភាព", "លេខទូស័ព្ទ", "ផ្សេងៗ",
                                              "លក្ខខណ្ឌ", "ព័ត៌មានខុសឆ្គង", "ពេលវេលា"])


def build_status_and_note(input_str):
    raw = input_str.strip()
    if not raw:
        return "មិនទាន់បានពិនិត្យ", "", "", [], "ធម្មតា"

    name_errs = []
    condition = "ធម្មតា"

    if re.search(r'(?:no|គ្មានទិន្នន័យ|គ្មានក្បាលដី|គ្មាន)', raw, re.IGNORECASE):
        condition = "គ្មានទិន្នន័យ"

    if re.search(r'(?:ទំនាស់|ទាស់|ជម្លោះ)', raw, re.IGNORECASE):
        condition = "ទំនាស់"

    found_errs = []
    for opt in ERR_NAME_OPTIONS:
        if opt in raw:
            found_errs.append(opt)

    if found_errs:
        name_errs = found_errs
        if condition == "ធម្មតា":
            condition = "ខុសអក្ខរវិរុទ្ខ"

    phone_match = re.search(r'(?:0\d{8,9}|\+855\d{8,9})', raw)
    phone_found = phone_match.group(0) if phone_match else ""

    return "បានពិនិត្យ", phone_found, raw, name_errs, condition


# --- MAIN ENTRY POINT ---
def main():
    st.set_page_config(page_title="ប្រព័ន្ធគ្រប់គ្រងដីធ្លី", page_icon="📦", layout="wide")

    st.markdown("""
        <style, lang="css">
        .stButton button {
            width: 100%;
            border-radius: 8px;
            font-weight: bold;
        }
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 5rem;
        }

        .sticky-save-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background-color: #ffffff;
            box-shadow: 0px -4px 12px rgba(0,0,0,0.15);
            padding: 12px 24px;
            z-index: 999999;
            border-top: 2px solid #007bff;
        }
        </style>
    """, unsafe_allow_html=True)

    initialize_database()

    current_ip = get_client_ip()

    if "user_authenticated" not in st.session_state:
        st.session_state["user_authenticated"] = False
        st.session_state["username"] = ""
        st.session_state["role"] = ""

    if not st.session_state["user_authenticated"]:
        active_user = get_username_by_ip(current_ip)
        if active_user:
            user_data = get_user_from_db(active_user)
            if user_data and user_data[4] == "approved":
                st.session_state["user_authenticated"] = True
                st.session_state["username"] = user_data[1]
                st.session_state["role"] = user_data[3]

    if not st.session_state["user_authenticated"]:
        st.title(get_app_title())
        tab_login, tab_reg = st.tabs(["🔑 ចូលប្រព័ន្ធ (Login)", "📝 ចុះឈ្មោះ (Register)"])

        with tab_login:
            st.subheader("ចូលប្រព័ន្ធ")
            login_user = st.text_input("ឈ្មោះអ្នកប្រើប្រាស់")
            login_pass = st.text_input("ពាក្យសម្ងាត់", type="password")

            if st.button("ចូលប្រព័ន្ធ", use_container_width=True, type="primary"):
                user_data = get_user_from_db(login_user)
                if user_data:
                    u_id, u_name, u_pass, u_role, u_status, u_expires = user_data
                    if u_pass == login_pass:
                        if u_status == "approved":
                            register_ip_session(current_ip, u_name)
                            st.session_state["user_authenticated"] = True
                            st.session_state["username"] = u_name
                            st.session_state["role"] = u_role
                            st.success("ចូលប្រព័ន្ធជោគជ័យ!")
                            st.rerun()
                        else:
                            st.warning("គណនីរបស់អ្នកមិនទាន់បានអនុម័តដោយ Admin ទេ។")
                    else:
                        st.error("ពាក្យសម្ងាត់មិនត្រឹមត្រូវ។")
                else:
                    st.error("រកមិនឃើញឈ្មោះអ្នកប្រើប្រាស់នេះទេ។")

        with tab_reg:
            st.subheader("ស្នើសុំបង្កើតគណនីថ្មី")
            reg_user = st.text_input("ឈ្មោះអ្នកប្រើប្រាស់ថ្មី")
            reg_pass = st.text_input("ពាក្យសម្ងាត់ថ្មី", type="password")
            reg_role = st.selectbox("ស្នើសុំតួនាទី", ["user", "temp_admin"])

            if st.button("បញ្ជូនសំណើ", use_container_width=True):
                if reg_user and reg_pass:
                    ok, msg = register_user(reg_user, reg_pass, reg_role)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("សូមបំពេញព័ត៌មានឱ្យបានគ្រប់គ្រាន់។")
        return

    # --- LOGGED IN USER INTERFACE ---
    current_username = st.session_state["username"]
    current_role = st.session_state["role"]

    with st.sidebar:
        st.title("👤 គណនី")
        st.write(f"**អ្នកប្រើប្រាស់:** `{current_username}`")
        st.write(f"**តួនាទី:** `{current_role}`")

        if st.button("ចាកចេញពីប្រព័ន្ធ (Logout)", use_container_width=True):
            clear_ip_session(current_ip)
            st.session_state["user_authenticated"] = False
            st.session_state["username"] = ""
            st.session_state["role"] = ""
            st.rerun()

        st.divider()

        if current_role in ["admin", "temp_admin"]:
            st.subheader("⚙️ ការកំណត់ប្រព័ន្ធ (System Settings)")

            with st.expander("✏️ កែប្រែចំណងជើងកម្មវិធី (App Title)"):
                new_app_title = st.text_input("ចំណងជើងថ្មី", value=get_app_title())
                if st.button("រក្សាទុកចំណងជើង"):
                    set_app_title(new_app_title)
                    st.success("បានធ្វើបច្ចុប្បន្នភាពចំណងជើង!")
                    st.rerun()

            with st.expander("👥 គ្រប់គ្រងអ្នកប្រើប្រាស់ (Users)"):
                users_df = get_all_users()
                st.dataframe(users_df, use_container_width=True)

                selected_user = st.selectbox("ជ្រើសរើសអ្នកប្រើប្រាស់", users_df["ឈ្មោះអ្នកប្រើប្រាស់"].tolist())

                if selected_user != DEFAULT_ADMIN_USER:
                    action = st.selectbox("សកម្មភាព", ["អនុម័ត (Approve)", "កំណត់ជា User", "កំណត់ជា Temp Admin",
                                                      "កំណត់ជា Admin", "លុបអ្នកប្រើប្រាស់ (Delete)"])

                    duration = 0
                    if action == "កំណត់ជា Temp Admin":
                        duration = st.number_input("រយៈពេលជា Admin បណ្តោះអាសន្ន (នាទី)", min_value=1,
                                                   value=60)

                    if st.button("អនុវត្តសកម្មភាព"):
                        with get_db() as conn:
                            with conn.cursor() as cursor:
                                if action == "អនុម័ត (Approve)":
                                    cursor.execute("UPDATE users SET status = 'approved' WHERE username = %s",
                                                   (selected_user,))
                                elif action == "កំណត់ជា User":
                                    cursor.execute(
                                        "UPDATE users SET role = 'user', temp_admin_expires = '' WHERE username = %s",
                                        (selected_user,))
                                elif action == "កំណត់ជា Admin":
                                    cursor.execute(
                                        "UPDATE users SET role = 'admin', status = 'approved', temp_admin_expires = '' WHERE username = %s",
                                        (selected_user,))
                                elif action == "កំណត់ជា Temp Admin":
                                    exp_time = get_cambodia_now() + datetime.timedelta(minutes=duration)
                                    exp_str = exp_time.strftime("%Y-%m-%d %H:%M:%S")
                                    cursor.execute(
                                        "UPDATE users SET role = 'temp_admin', status = 'approved', temp_admin_expires = %s WHERE username = %s",
                                        (exp_str, selected_user))
                                elif action == "លុបអ្នកប្រើប្រាស់ (Delete)":
                                    cursor.execute("DELETE FROM users WHERE username = %s", (selected_user,))
                                conn.commit()
                        st.success("បានអនុវត្តជោគជ័យ!")
                        st.rerun()
                else:
                    st.info("Root Admin ត្រូវបានការពារ ហើយមិនអាចកែប្រែបានឡើយ។")

    st.title(get_app_title())

    projects = get_all_projects()
    project_options = {p[1]: (p[0], p[2]) for p in projects}

    col_proj_sel, col_proj_manage = st.columns([3, 1])

    with col_proj_sel:
        selected_project_name = st.selectbox("📁 ជ្រើសរើសគម្រោង:", list(project_options.keys()))
        selected_project_id, total_items = project_options[selected_project_name]

    with col_proj_manage:
        if current_role in ["admin", "temp_admin"]:
            with st.popover("➕ បង្កើត / កែប្រែគម្រោង"):
                tab_add, tab_edit, tab_del = st.tabs(["បន្ថែម", "កែប្រែ", "លុប"])

                with tab_add:
                    p_name = st.text_input("ឈ្មោះគម្រោងថ្មី")
                    p_items = st.number_input("ចំនួនក្បាលដីសរុប", min_value=1, value=100)
                    if st.button("បង្កើតគម្រោង", use_container_width=True):
                        if p_name:
                            create_new_project(p_name, p_items)
                            st.success("បានបង្កើតគម្រោងថ្មី!")
                            st.rerun()

                with tab_edit:
                    ep_name = st.text_input("ឈ្មោះគម្រោងថ្មី", value=selected_project_name)
                    ep_items = st.number_input("ចំនួនក្បាលដីថ្មី", min_value=1, value=total_items)
                    if st.button("កែប្រែគម្រោង", use_container_width=True):
                        ok, msg = update_project_details(selected_project_id, ep_name, ep_items)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

                with tab_del:
                    st.warning("⚠️ ប្រយ័ត្ន! ការលុបគម្រោងនឹងលុបជិន្នន័យក្បាលដី និងប្រវត្តិទាំងអស់។")
                    if st.button("លុបគម្រោងនេះចោល", use_container_width=True, type="primary"):
                        ok, msg = delete_project_by_id(selected_project_id)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    df_items = load_project_items(selected_project_id, total_items)

    st.markdown("---")

    tab_input, tab_data, tab_summary, tab_history = st.tabs([
        "📝 វាយបញ្ចូលទិន្នន័យ",
        "📊 បញ្ជីក្បាលដី",
        "📈 សង្ខេបរបាយការណ៍",
        "📜 ប្រវត្តិសកម្មភាព"
    ])

    with tab_input:
        st.subheader("បញ្ចូលទិន្នន័យក្បាលដី")

        input_mode = st.radio("ទម្រង់នៃការបញ្ចូល:", ["ក្បាលដីទោល (Single Parcel)", "បញ្ចូលច្រើនក្នុងពេលតែមួយ (Batch Input)"],
                              horizontal=True)

        if input_mode == "ក្បាលដីទោល (Single Parcel)":

            if "single_code" not in st.session_state:
                st.session_state["single_code"] = 1

            col_select, col_info = st.columns([1, 2])

            with col_select:
                selected_code = st.number_input("ជ្រើសរើសលេខក្បាលដី", min_value=1, max_value=total_items,
                                                value=st.session_state["single_code"], key="single_code_input")
                st.session_state["single_code"] = selected_code

            current_row = df_items[df_items["ក្បាលដី"] == selected_code].iloc[0]

            with col_info:
                st.info(
                    f"**ក្បាលដីទី {selected_code}** | ស្ថានភាពបច្ចុប្បន្ន: `{current_row['ស្ថានភាព']}` | បច្ចុប្បន្នភាព: `{current_row['បច្ចុប្បន្នភាពចុងក្រោយ']}`")

            # Load default values
            cur_status = current_row["ស្ថានភាព"]
            cur_phone = current_row["លេខទូស័ព្ទ"]
            cur_notes = current_row["ផ្សេងៗ"]
            cur_condition = current_row["លក្ខខណ្ឌ"]
            cur_errs = current_row["ព័ត៌មានខុសឆ្គង"]

            parsed_errs = [e.strip() for e in cur_errs.split(",") if e.strip() in ERR_NAME_OPTIONS] if cur_errs else []

            st.markdown("---")

            col_f1, col_f2 = st.columns(2)

            with col_f1:
                status_radio = st.radio("ស្ថានភាព", ["មិនទាន់បានពិនិត្យ", "បានពិនិត្យ"],
                                        index=0 if cur_status == "មិនទាន់បានពិនិត្យ" else 1)
                condition_sel = st.selectbox("លក្ខខណ្ឌដី/ប្រព័ន្ធ", CONDITION_OPTIONS,
                                             index=CONDITION_OPTIONS.index(
                                                 cur_condition) if cur_condition in CONDITION_OPTIONS else 0)
                phone_in = st.text_input("លេខទូស័ព្ទទំនាក់ទំនង", value=cur_phone)

            with col_f2:
                err_multisel = st.multiselect("ព័ត៌មានខុសឆ្គង (ប្រសិនបើមាន)", ERR_NAME_OPTIONS, default=parsed_errs)
                notes_in = st.text_area("ផ្សេងៗ / កំណត់ចំណាំ", value=cur_notes)

            def do_save():
                update_parcel_status(
                    selected_project_id,
                    selected_code,
                    status_radio,
                    phone_in,
                    notes_in,
                    condition_sel,
                    err_multisel
                )
                st.toast(f"✅ បានរក្សាទុកក្បាលដី {selected_code} រួចរាល់!", icon="🎉")
                time.sleep(0.3)

            # FLOATING BAR AT BOTTOM WITH PREV / NEXT / SAVE
            st.markdown("""
                <div class="sticky-save-bar">
                    <div id="sticky-bar-content"></div>
                </div>
            """, unsafe_allow_html=True)

            bar_c1, bar_c2, bar_c3 = st.columns([2, 2, 2])

            with bar_c2:
                if st.button("💾 រក្សាទុក (Save)", type="primary", use_container_width=True):
                    do_save()
                    st.rerun()

        else:
            st.subheader("បញ្ចូលទិន្នន័យច្រើនក្នុងពេលតែមួយ (Batch Input)")
            st.caption(
                "ឧទាហរណ៍ទម្រង់បញ្ចូល: `1=បានពិនិត្យ 012345678 ខុសឈ្មោះប្ដី` ឬ `2=គ្មានទិន្នន័យ` (មួយជួរសម្រាប់មួយក្បាលដី)")

            batch_text = st.text_area("វាយបញ្ចូលអត្ថបទទីនេះ", height=200)

            if st.button("🚀 ដំណើរការរក្សាទុកទិន្នន័យច្រើន", type="primary"):
                if batch_text.strip():
                    lines = batch_text.strip().split("\n")
                    success_count = 0
                    for line in lines:
                        if "=" in line:
                            parts = line.split("=", 1)
                            try:
                                code_p = int(parts[0].strip())
                                val_p = parts[1].strip()

                                if 1 <= code_p <= total_items:
                                    st_val, ph_val, nt_val, err_val, cond_val = build_status_and_note(val_p)
                                    update_parcel_status(selected_project_id, code_p, st_val, ph_val, nt_val, cond_val,
                                                         err_val)
                                    success_count += 1
                            except ValueError:
                                continue

                    st.success(f"បានធ្វើបច្ចុប្បន្នភាពក្បាលដីចំនួន {success_count} ជោគជ័យ!")
                    st.rerun()
                else:
                    st.warning("សូមបញ្ចូលទិន្នន័យជាមុនសិន។")

    with tab_data:
        st.subheader("បញ្ជីក្បាលដីទាំងអស់")

        filter_status = st.multiselect("តម្រងតាមស្ថានភាព:", ["មិនទាន់បានពិនិត្យ", "បានពិនិត្យ"],
                                       default=["មិនទាន់បានពិនិត្យ", "បានពិនិត្យ"])
        filter_cond = st.multiselect("តម្រងតាមលក្ខខណ្ឌ:", list(set(df_items["លក្ខខណ្ឌ"].tolist())),
                                     default=list(set(df_items["លក្ខខណ្ឌ"].tolist())))

        filtered_df = df_items[
            (df_items["ស្ថានភាព"].isin(filter_status)) &
            (df_items["លក្ខខណ្ឌ"].isin(filter_cond))
            ]

        st.dataframe(filtered_df, use_container_width=True, height=400)

    with tab_summary:
        st.subheader("សង្ខេបរបាយការណ៍")

        total_parcels = len(df_items)
        checked_parcels = len(df_items[df_items["ស្ថានភាព"] == "បានពិនិត្យ"])
        unchecked_parcels = total_parcels - checked_parcels

        c1, c2, c3 = st.columns(3)
        c1.metric("ក្បាលដីសរុប", total_parcels)
        c2.metric("បានពិនិត្យរួច", checked_parcels, f"{(checked_parcels / total_parcels) * 100:.1f}%")
        c3.metric("មិនទាន់បានពិនិត្យ", unchecked_parcels, f"{(unchecked_parcels / total_parcels) * 100:.1f}%")

        st.markdown("---")
        st.write("### ការបែងចែកតាមលក្ខខណ្ឌដី")
        cond_counts = df_items["លក្ខខណ្ឌ"].value_counts().reset_index()
        cond_counts.columns = ["លក្ខខណ្ឌ", "ចំនួនក្បាលដី"]
        st.dataframe(cond_counts, use_container_width=True)

    with tab_history:
        st.subheader("ប្រវត្តិសកម្មភាពកែប្រែ")
        logs_df = get_logs_for_project(selected_project_id)
        st.dataframe(logs_df, use_container_width=True, height=400)


if __name__ == "__main__":
    main()
