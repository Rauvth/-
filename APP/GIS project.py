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

    # User Accounts Table
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

    # Migration: Check temp_admin_expires
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if "temp_admin_expires" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN temp_admin_expires TEXT DEFAULT ''")

    # App Settings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Default App Settings
    default_settings = [
        ('app_title', '📦 កម្មវិធីបិតផ្សាយ'),
        ('loc_village', ''),
        ('loc_commune', ''),
        ('loc_district', ''),
        ('loc_province', 'បាត់ដំបង')
    ]
    for key, val in default_settings:
        cursor.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)", (key, val))

    # Safely insert default protected admin if not exists
    cursor.execute("""
        INSERT OR IGNORE INTO users (username, password, role, status, created_at)
        VALUES (?, ?, 'admin', 'approved', ?)
    """, (DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASS, get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")))

    # Projects Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            total_items INTEGER NOT NULL
        )
    """)

    # Items Table
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

    # Logs Table
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
    return row[0] if row else "📦 កម្មវិធីបិតផ្សាយ"


def set_app_title(new_title):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('app_title', ?)", (new_title,))
    conn.commit()
    conn.close()


def get_location_settings():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM app_settings WHERE key IN ('loc_village', 'loc_commune', 'loc_district', 'loc_province')")
    rows = cursor.fetchall()
    conn.close()
    
    settings = {'loc_village': '', 'loc_commune': '', 'loc_district': '', 'loc_province': 'បាត់ដំបង'}
    for k, v in rows:
        settings[k] = v if v is not None else ""
    return settings


def set_location_settings(village, commune, district, province):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('loc_village', ?)", (village,))
    cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('loc_commune', ?)", (commune,))
    cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('loc_district', ?)", (district,))
    cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('loc_province', ?)", (province,))
    conn.commit()
    conn.close()


def log_activity(project_id, code, action_type, status="", phone="", notes="", condition="", custom_timestamp=""):
    """Records system actions into logs table."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    timestamp = custom_timestamp if custom_timestamp else get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")

    cursor.execute("""
        INSERT INTO logs (project_id, code, action_type, status, customer_phone, notes, condition, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (project_id, code, action_type, status, phone, notes, condition, timestamp))

    conn.commit()
    conn.close()


# ==============================================================================
# 🔑 USER AUTHENTICATION & ADVANCED ROLE MANAGEMENT
# ==============================================================================
def check_and_expire_temp_admins():
    """Checks and demotes temporary admins whose admin duration has expired."""
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
    cursor.execute("SELECT id, username, password, role, status, temp_admin_expires FROM users WHERE username = ?", (username,))
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
        return True, "Registration submitted!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Username already exists. Please choose a different one."


def get_all_users():
    check_and_expire_temp_admins()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, status, created_at, temp_admin_expires FROM users ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=["ID", "Username", "Role", "Status", "Created At", "Temp Admin Expires"])


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


def revoke_admin_role(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = 'user', temp_admin_expires = '' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def render_auth_page():
    """Renders Login / Registration with status checks for pending/inactive users."""
    st.title("🔐 Authentication & Registration Portal")

    mode = st.radio("Select Action", ["Log In", "Create New Account"], horizontal=True)

    if mode == "Log In":
        st.subheader("Sign In")
        role_type = st.selectbox("Login Role Mode", ["Normal User", "Admin / Temp Admin"])

        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Log In")

            if login_btn:
                user = get_user_from_db(username)
                if user and user[2] == password:
                    db_role = user[3]
                    db_status = user[4]

                    # Account Activity Check
                    if db_status == "inactive":
                        st.error("🔒 Your account is set to INACTIVE. Please contact the root admin to activate your account.")
                        return

                    if db_status == "pending":
                        st.session_state["pending_user"] = username
                        st.session_state["authenticated"] = False
                        st.rerun()
                    elif db_status == "rejected":
                        st.error("Your account registration request was rejected by the admin.")
                    elif db_status == "approved":
                        if role_type == "Admin / Temp Admin" and db_role not in ["admin", "temp_admin"]:
                            st.error("This account does not have Admin or Temp Admin privileges.")
                            return

                        st.session_state["authenticated"] = True
                        st.session_state["username"] = username
                        st.session_state["role"] = db_role
                        st.session_state["show_startup_popup"] = True
                        st.session_state.pop("pending_user", None)
                        st.success("Login successful!")
                        st.rerun()
                else:
                    st.error("Invalid username or password.")

    elif mode == "Create New Account":
        st.subheader("Request New Account")
        requested_role = st.selectbox("Select Desired Role", ["user", "admin"])

        with st.form("register_form"):
            new_user = st.text_input("Username")
            new_pass = st.text_input("Password", type="password")
            confirm_pass = st.text_input("Confirm Password", type="password")
            reg_btn = st.form_submit_button("Submit Account Request")

            if reg_btn:
                if not new_user or not new_pass:
                    st.error("Please fill in all fields.")
                elif new_pass != confirm_pass:
                    st.error("Passwords do not match!")
                else:
                    success, msg = register_user(new_user, new_pass, requested_role)
                    if success:
                        st.session_state["pending_user"] = new_user
                        st.rerun()
                    else:
                        st.error(msg)


def render_pending_waiting_screen(username):
    st.title("⏳ Account Approval Pending")

    user = get_user_from_db(username)
    if not user:
        st.error("Account not found.")
        if st.button("Back to Login"):
            st.session_state.pop("pending_user", None)
            st.rerun()
        return

    status = user[4]

    if status == "pending":
        st.warning(f"Hello **{username}**, your account registration request is currently **PENDING** approval from an administrator.")
        st.info("Please wait on this screen. It will refresh automatically when approved.")

        time.sleep(3)
        st.rerun()

    elif status == "approved":
        st.success(f"🎉 Great news, **{username}**! Your account has been approved by the admin.")
        if st.button("Continue to Application", use_container_width=True):
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.session_state["role"] = user[3]
            st.session_state["show_startup_popup"] = True
            st.session_state.pop("pending_user", None)
            st.rerun()

    elif status == "rejected":
        st.error(f"Sorry **{username}**, your account registration request was rejected by an administrator.")
        if st.button("Return to Login", use_container_width=True):
            st.session_state.pop("pending_user", None)
            st.rerun()


# ==============================================================================
# 📊 DATABASE UTILITIES
# ==============================================================================
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
        log_activity(project_id, None, "Project Created", notes=f"Created project '{name}' with ក្បាលដីសរុប {total_items}")
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
        cursor.execute("UPDATE projects SET name = ?, total_items = ? WHERE id = ?", (new_name, new_total_items, project_id))
        conn.commit()
        conn.close()
        return True, "Project updated successfully!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Project name already exists."


def delete_project(project_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM logs WHERE project_id = ?", (project_id,))
    cursor.execute("DELETE FROM items WHERE project_id = ?", (project_id,))
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()


def clear_history_logs(project_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM logs WHERE project_id = ?", (project_id,))
    conn.commit()
    conn.close()


def clear_conditions_data(project_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE items SET condition = '' WHERE project_id = ?", (project_id,))
    conn.commit()
    conn.close()


def delete_item_by_code(project_id, code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM items WHERE project_id = ? AND code = ?", (project_id, code))
    conn.commit()
    conn.close()


def reset_single_item_data(project_id, code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE items 
        SET status = 'មិនទាន់បានពិនិត្យ', customer_phone = '', notes = '', condition = '', updated_at = '-'
        WHERE project_id = ? AND code = ?
    """, (project_id, code))
    conn.commit()
    conn.close()


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
            "Status": status,
            "លេខទូស័ព្ទ": phone,
            "ផ្សេងៗ": notes,
            "Condition": condition if condition else "ធម្មតា",
            "Last Updated": updated_at if updated_at else "-"
        })
    return pd.DataFrame(data)


def is_no_data(row):
    cond = str(row["Condition"])
    notes = str(row["ផ្សេងៗ"]).strip()
    return cond == "គ្មានទិន្នន័យ" or notes == "គ្មានទិន្នន័យ"


def execute_check_updates(project_id, updates_list):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    timestamp = get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")

    for update in updates_list:
        code = update["code"]
        new_status = update["status"]
        phone = update.get("phone", "")
        notes = update.get("notes", "")
        condition = update.get("condition", "")

        cursor.execute("SELECT id FROM items WHERE project_id = ? AND code = ?", (project_id, code))
        exists = cursor.fetchone()

        if exists:
            cursor.execute("""
                UPDATE items 
                SET status = ?, customer_phone = ?, notes = ?, condition = ?, updated_at = ?
                WHERE project_id = ? AND code = ?
            """, (new_status, phone, notes, condition, timestamp, project_id, code))
        else:
            cursor.execute("""
                INSERT INTO items (project_id, code, status, customer_phone, notes, condition, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (project_id, code, new_status, phone, notes, condition, timestamp))

        action = "Check Item" if new_status == "បានពិនិត្យ" else "Uncheck Item"
        log_activity(project_id, code, action, status=new_status, phone=phone, notes=notes, condition=condition, custom_timestamp=timestamp)

    conn.commit()
    conn.close()


def execute_import_excel_data(project_id, items_dict):
    """Bulk update items and logs from imported Excel file."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    for code, details in items_dict.items():
        status = details.get("status", "មិនទាន់បានពិនិត្យ")
        phone = details.get("phone", "")
        notes = details.get("notes", "")
        condition = details.get("condition", "")
        updated_at = details.get("updated_at", get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p"))

        cursor.execute("SELECT id FROM items WHERE project_id = ? AND code = ?", (project_id, code))
        exists = cursor.fetchone()

        if exists:
            cursor.execute("""
                UPDATE items 
                SET status = ?, customer_phone = ?, notes = ?, condition = ?, updated_at = ?
                WHERE project_id = ? AND code = ?
            """, (status, phone, notes, condition, updated_at, project_id, code))
        else:
            cursor.execute("""
                INSERT INTO items (project_id, code, status, customer_phone, notes, condition, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (project_id, code, status, phone, notes, condition, updated_at))

        action = "Import Excel"
        log_activity(project_id, code, action, status=status, phone=phone, notes=notes, condition=condition, custom_timestamp=updated_at)

    conn.commit()
    conn.close()


def get_history_logs(project_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, code, action_type, status, customer_phone, notes, condition 
        FROM logs 
        WHERE project_id = ? 
        ORDER BY id DESC
    """, (project_id,))
    rows = cursor.fetchall()
    conn.close()

    return pd.DataFrame(rows, columns=["Timestamp", "ក្បាលដី", "Action Type", "Status", "លេខទូស័ព្ទ", "ផ្សេងៗ", "Condition"])


# ==============================================================================
# 🎨 MAIN UI APPLICATION
# ==============================================================================
initialize_database()

# User Pending Interception
if "pending_user" in st.session_state:
    render_pending_waiting_screen(st.session_state["pending_user"])
    st.stop()

# Authentication Check
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    render_auth_page()
    st.stop()

# Get App Dynamic Title & Location Settings
app_title = get_app_title()
loc_settings = get_location_settings()

st.set_page_config(page_title=app_title, layout="wide")

# Root Title & Dynamic Sub-Header Display
st.title(app_title)

village_text = f"ភូមិ {loc_settings['loc_village']}" if loc_settings['loc_village'] else "ភូមិ ................"
commune_text = f"ឃុំ {loc_settings['loc_commune']}" if loc_settings['loc_commune'] else "ឃុំ ................"
district_text = f"ស្រុក {loc_settings['loc_district']}" if loc_settings['loc_district'] else "ស្រុក ................"
province_text = f"ខេត្ត {loc_settings['loc_province']}" if loc_settings['loc_province'] else "ខេត្ត បាត់ដំបង"

sub_header_location = f"{village_text}   {commune_text}   {district_text}   {province_text}"
st.markdown(f"##### {sub_header_location}")

# Handle Startup Notification Dialog
if st.session_state.get("show_startup_popup", False):
    st.session_state["show_startup_popup"] = False

    @st.dialog("🔔 Notification")
    def show_notice():
        st.write("លោកអ្នកអាចប្រើប្រាស់មុខងារស្វែងរកក្បាលដី និងបញ្ចូលទិន្នន័យបានយ៉ាងងាយស្រួល។")
        if st.button("យល់ព្រម", use_container_width=True):
            st.rerun()

    show_notice()

# Role Handling
current_user = st.session_state.get("username", "User")
current_role = st.session_state.get("role", "user")

# Sidebar
st.sidebar.markdown(f"👤 **Logged in as:** `{current_user}` ({current_role.upper()})")
if st.sidebar.button("🚪 Log Out", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.sidebar.divider()

# Sidebar: Admin Control System Options
if current_role in ["admin", "temp_admin"]:
    st.sidebar.title("⚙️ App Controls")
    new_app_title_input = st.sidebar.text_input("Edit App Title", value=app_title)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### 📍 Location Settings")
    v_val = st.sidebar.text_input("ភូមិ", value=loc_settings['loc_village'])
    c_val = st.sidebar.text_input("ឃុំ", value=loc_settings['loc_commune'])
    d_val = st.sidebar.text_input("ស្រុក", value=loc_settings['loc_district'])
    p_val = st.sidebar.text_input("ខេត្ត", value=loc_settings['loc_province'])

    if st.sidebar.button("💾 Save Settings", use_container_width=True):
        set_app_title(new_app_title_input)
        set_location_settings(v_val, c_val, d_val, p_val)
        st.sidebar.success("Settings updated successfully!")
        st.rerun()

    st.sidebar.divider()

# Project Selection
all_projects = get_all_projects()
project_options = {p[1]: (p[0], p[2]) for p in all_projects}

selected_project_name = st.sidebar.selectbox("📂 ជ្រើសរើស គម្រោង", list(project_options.keys()) if project_options else ["-- គ្មានគម្រោង --"])

if selected_project_name != "-- គ្មានគម្រោង --":
    active_project_id, active_total_items = project_options[selected_project_name]
else:
    active_project_id, active_total_items = None, 0

# Sidebar Project Creation
if current_role in ["admin", "temp_admin"]:
    st.sidebar.divider()
    st.sidebar.subheader("➕ បង្កើតគម្រោងថ្មី")
    new_proj_name = st.sidebar.text_input("ឈ្មោះ គម្រោង")
    new_proj_items = st.sidebar.number_input("ចំនួន ក្បាលដីសរុប", min_value=1, value=100, step=1)

    if st.sidebar.button("រក្សាទុក គម្រោង"):
        if new_proj_name:
            create_new_project(new_proj_name, new_proj_items)
            st.sidebar.success(f"គម្រោង '{new_proj_name}' ត្រូវបានបង្កើត!")
            st.rerun()

# --- MAIN WORKSPACE ---
if not active_project_id:
    st.info("👋 សូមជ្រើសរើស ឬ បង្កើត គម្រោង ដើម្បីចាប់ផ្តើម។")
    st.stop()

df = get_project_items(active_project_id, active_total_items)

# Admin Management Module Sub-Tab
if current_role in ["admin", "temp_admin"]:
    admin_tab, main_work_tab = st.tabs(["🔒 Admin Management Control", "📋 Main Data Operations"])
else:
    main_work_tab = st.container()

# ==============================================================================
# TAB 1: ADMIN MANAGEMENT CONTROL PANEL
# ==============================================================================
if current_role in ["admin", "temp_admin"]:
    with admin_tab:
        st.subheader("👥 Account Registration & User Management")

        users_df = get_all_users()
        st.dataframe(users_df, use_container_width=True)

        st.divider()

        col_adm1, col_adm2 = st.columns(2)

        with col_adm1:
            st.markdown("### 📥 Account Approvals")
            pending_users = users_df[users_df["Status"] == "pending"]

            if not pending_users.empty:
                for _, p_user in pending_users.iterrows():
                    p_id = p_user["ID"]
                    p_name = p_user["Username"]
                    p_role = p_user["Role"]

                    st.write(f"**{p_name}** (Requested: `{p_role}`)")
                    ac_col1, ac_col2 = st.columns(2)

                    if ac_col1.button(f"✅ Approve {p_name}", key=f"app_{p_id}"):
                        update_user_status(p_id, "approved")
                        st.success(f"Approved {p_name}")
                        st.rerun()

                    if ac_col2.button(f"❌ Reject {p_name}", key=f"rej_{p_id}"):
                        update_user_status(p_id, "rejected")
                        st.warning(f"Rejected {p_name}")
                        st.rerun()
            else:
                st.info("No pending user registration requests.")

            st.divider()

            st.markdown("### ⚡ User Status & Account Deletion")
            user_list = users_df["Username"].tolist()
            sel_user = st.selectbox("Select Target User", user_list)

            if sel_user:
                target_row = users_df[users_df["Username"] == sel_user].iloc[0]
                target_id = target_row["ID"]
                curr_st = target_row["Status"]

                st.write(f"Current Status: **{curr_st.upper()}**")

                c_a1, c_a2 = st.columns(2)
                if curr_st == "approved":
                    if c_a1.button("🔒 Set to Inactive", key=f"inact_{target_id}"):
                        update_user_status(target_id, "inactive")
                        st.rerun()
                elif curr_st == "inactive":
                    if c_a1.button("🔓 Re-Activate Account", key=f"react_{target_id}"):
                        update_user_status(target_id, "approved")
                        st.rerun()

                # Safety Lock preventing deletion of root protected default admin account
                if sel_user == DEFAULT_ADMIN_USER:
                    st.warning("⚠️ Protected Root Admin account cannot be deleted.")
                else:
                    if c_a2.button(f"🗑️ Delete Account '{sel_user}'", key=f"del_u_{target_id}"):
                        delete_user_account(target_id)
                        st.success(f"Deleted user account: {sel_user}")
                        st.rerun()

        with col_adm2:
            st.markdown("### ⏳ Temporary Admin Role Granting")
            active_users_df = users_df[users_df["Username"] != DEFAULT_ADMIN_USER]
            grant_user_list = active_users_df["Username"].tolist()

            if grant_user_list:
                sel_grant_user = st.selectbox("Select User for Admin Grant", grant_user_list)
                target_grant_row = active_users_df[active_users_df["Username"] == sel_grant_user].iloc[0]
                t_grant_id = target_grant_row["ID"]
                t_role = target_grant_row["Role"]

                st.write(f"Current Role: **{t_role.upper()}**")

                hours = st.number_input("Grant Duration (Hours)", min_value=1, max_value=720, value=24)

                if st.button("👑 Grant Temporary Admin Access"):
                    exp_time = get_cambodia_now() + datetime.timedelta(hours=hours)
                    set_temporary_admin(t_grant_id, exp_time)
                    st.success(f"Granted Admin privileges to {sel_grant_user} for {hours} hours!")
                    st.rerun()

                if t_role in ["temp_admin", "admin"]:
                    if st.button("🚫 Revoke Admin Privileges Now"):
                        revoke_admin_role(t_grant_id)
                        st.warning(f"Revoked Admin privileges for {sel_grant_user}")
                        st.rerun()
            else:
                st.info("No customizable non-root users found.")

            st.divider()

            st.markdown("### 🛠️ Edit Current Project Details")
            proj_new_name = st.text_input("Rename Project", value=selected_project_name)
            proj_new_total = st.number_input("Update Total Items", min_value=1, value=active_total_items, step=1)

            if st.button("💾 Update Project Info"):
                success, msg = update_project_details(active_project_id, proj_new_name, proj_new_total)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

            st.markdown("### 🗑️ Delete Project")
            if st.button("⚠️ Delete Entire Project", type="primary"):
                delete_project(active_project_id)
                st.success(f"Project '{selected_project_name}' deleted!")
                st.rerun()


# ==============================================================================
# TAB 2: MAIN DATA WORKSPACE OPERATIONS
# ==============================================================================
with main_work_tab:
    # Key Summary Dashboard Cards
    total_count = len(df)
    checked_count = len(df[df["Status"] == "បានពិនិត្យ"])
    unchecked_count = total_count - checked_count
    no_data_count = len(df[df.apply(is_no_data, axis=1)])
    condition_count = len(df[(df["Condition"] != "ធម្មតា") & (df["Condition"] != "")])

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("ក្បាលដីសរុប", total_count)
    col2.metric("បានពិនិត្យ", checked_count)
    col3.metric("មិនទាន់បានពិនិត្យ", unchecked_count)
    col4.metric("គ្មានទិន្នន័យ", no_data_count)
    col5.metric("មានលក្ខខណ្ឌ", condition_count)

    st.divider()

    # Functional Options Section
    action = st.radio(
        "ជ្រើសរើសសកម្មភាព",
        ["🔍 ស្វែងរក ក្បាលដី", "✍️ ពិនិត្យ/កែប្រែ ច្រើនក្បាលដី", "📤 នាំចេញ / នាំចូល (Excel)", "📜 ប្រវត្តិប្រតិបត្តិការ"],
        horizontal=True
    )

    # 1. SEARCH FUNCTIONALITY
    if action == "🔍 ស្វែងរក ក្បាលដី":
        st.subheader("🔍 ស្វែងរក និងកែប្រែទិន្នន័យក្បាលដី")

        search_col1, search_col2, search_col3 = st.columns(3)
        with search_col1:
            search_code = st.number_input("បញ្ចូលលេខក្បាលដី", min_value=1, max_value=active_total_items, value=1, step=1)
        with search_col2:
            search_phone = st.text_input("ស្វែងរកតាមលេខទូរស័ព្ទ")
        with search_col3:
            search_condition = st.selectbox("តម្រងតាម condition", ["ទាំងអស់"] + CONDITION_OPTIONS + ["ធម្មតា"])

        # Filter Logic
        filtered_df = df.copy()
        if search_code:
            filtered_df = filtered_df[filtered_df["ក្បាលដី"] == search_code]
        if search_phone:
            filtered_df = filtered_df[filtered_df["លេខទូស័ព្ទ"].str.contains(search_phone, na=False)]
        if search_condition != "ទាំងអស់":
            if search_condition == "ធម្មតា":
                filtered_df = filtered_df[(filtered_df["Condition"] == "ធម្មតា") | (filtered_df["Condition"] == "")]
            else:
                filtered_df = filtered_df[filtered_df["Condition"] == search_condition]

        st.dataframe(filtered_df, use_container_width=True)

        if not filtered_df.empty:
            st.divider()
            st.subheader(f"📝 កែប្រែក្បាលដីលេខ: {filtered_df.iloc[0]['ក្បាលដី']}")

            target_item = filtered_df.iloc[0]
            curr_code = int(target_item["ក្បាលដី"])

            with st.form("single_edit_form"):
                e_status = st.selectbox("Status", ["បានពិនិត្យ", "មិនទាន់បានពិនិត្យ"], index=0 if target_item["Status"] == "បានពិនិត្យ" else 1)
                e_phone = st.text_input("លេខទូស័ព្ទ", value=target_item["លេខទូស័ព្ទ"])
                e_notes = st.text_input("ផ្សេងៗ", value=target_item["ផ្សេងៗ"])

                curr_cond = target_item["Condition"]
                cond_idx = CONDITION_OPTIONS.index(curr_cond) if curr_cond in CONDITION_OPTIONS else 0
                e_cond = st.selectbox("Condition", CONDITION_OPTIONS, index=cond_idx)

                save_single = st.form_submit_button("💾 រក្សាទុកការកែប្រែ")

                if save_single:
                    execute_check_updates(active_project_id, [{
                        "code": curr_code,
                        "status": e_status,
                        "phone": e_phone,
                        "notes": e_notes,
                        "condition": e_cond
                    }])
                    st.success(f"ក្បាលដីលេខ {curr_code} ត្រូវបានកែប្រែជោគជ័យ!")
                    st.rerun()

    # 2. BULK CHECK/UNCHECK & CONDITIONAL OPERATIONS
    elif action == "✍️ ពិនិត្យ/កែប្រែ ច្រើនក្បាលដី":
        st.subheader("✍️ ពិនិត្យ និងកែប្រែទិន្នន័យច្រើនក្បាលដីក្នុងពេលតែមួយ")

        b_col1, b_col2 = st.columns(2)

        with b_col1:
            st.markdown("### 1️⃣ ជ្រើសរើសចន្លោះក្បាលដី (Range)")
            range_input = st.text_input("បញ្ចូលចន្លោះក្បាលដី (ឧទាហរណ៍: 1-10, 15, 20-25)", value="1-5")

            status_choice = st.radio("កំណត់ Status ថ្មី", ["បានពិនិត្យ", "មិនទាន់បានពិនិត្យ"], horizontal=True)
            bulk_phone = st.text_input("លេខទូស័ព្ទ (ជាជម្រើស)")
            bulk_notes = st.text_input("ផ្សេងៗ (ជាជម្រើស)")
            bulk_condition = st.selectbox("Condition (ជាជម្រើស)", [""] + CONDITION_OPTIONS)

            if st.button("🚀 អនុវត្តការកែប្រែជាក្រុម", use_container_width=True):
                codes_to_update = []
                parts = range_input.split(",")
                for part in parts:
                    part = part.strip()
                    if "-" in part:
                        try:
                            start, end = map(int, part.split("-"))
                            codes_to_update.extend(range(start, end + 1))
                        except ValueError:
                            pass
                    elif part.isdigit():
                        codes_to_update.append(int(part))

                codes_to_update = [c for c in codes_to_update if 1 <= c <= active_total_items]

                if codes_to_update:
                    updates = []
                    for c in codes_to_update:
                        updates.append({
                            "code": c,
                            "status": status_choice,
                            "phone": bulk_phone,
                            "notes": bulk_notes,
                            "condition": bulk_condition
                        })
                    execute_check_updates(active_project_id, updates)
                    st.success(f"បានធ្វើបច្ចុប្បន្នភាពក្បាលដីចំនួន {len(codes_to_update)} រួចរាល់!")
                    st.rerun()
                else:
                    st.error("សូមបញ្ចូលចន្លោះក្បាលដីឱ្យបានត្រឹមត្រូវ!")

        with b_col2:
            st.markdown("### 2️⃣ ការគ្រប់គ្រងទិន្នន័យ & Reset")

            st.write("🔄 **Reset ទិន្នន័យក្បាលដីមួយ**")
            reset_code = st.number_input("លេខក្បាលដីដែលត្រូវ Reset", min_value=1, max_value=active_total_items, value=1)
            if st.button(f"Reset ក្បាលដី {reset_code}"):
                reset_single_item_data(active_project_id, reset_code)
                st.success(f"ក្បាលដីលេខ {reset_code} ត្រូវបាន Reset រួចរាល់!")
                st.rerun()

            st.divider()

            if current_role in ["admin", "temp_admin"]:
                st.write("🧹 **Clear All Operations (Admin Only)**")

                if st.button("🧹 Clear All Conditions Data"):
                    clear_conditions_data(active_project_id)
                    st.success("ទិន្នន័យ Condition ទាំងអស់ត្រូវបានសំអាត!")
                    st.rerun()

                if st.button("🧹 Clear All Activity Logs History"):
                    clear_history_logs(active_project_id)
                    st.success("ប្រវត្តិប្រតិបត្តិការទាំងអស់ត្រូវបានលុប!")
                    st.rerun()

    # 3. IMPORT / EXPORT EXCEL DATA
    elif action == "📤 នាំចេញ / នាំចូល (Excel)":
        st.subheader("📤 នាំចេញ (Export) និង នាំចូល (Import) ទិន្នន័យ Excel")

        ex_col1, ex_col2 = st.columns(2)

        with ex_col1:
            st.markdown("### 📥 នាំចេញទិន្នន័យ (Export)")

            export_df = df.copy()

            # Format for Khmer Display Output Export
            csv_data = export_df.to_csv(index=False).encode('utf-8-sig')

            st.download_button(
                label="⬇️ ទាញយកទិន្នន័យជា Excel / CSV File",
                data=csv_data,
                file_name=f"{selected_project_name}_data.csv",
                mime="text/csv",
                use_container_width=True
            )

        with ex_col2:
            st.markdown("### 📤 នាំចូលទិន្នន័យ (Import Excel)")

            uploaded_file = st.file_uploader("ជ្រើសរើសឯកសារ Excel ឬ CSV", type=["csv", "xlsx"])

            if uploaded_file is not None:
                try:
                    if uploaded_file.name.endswith(".csv"):
                        imp_df = pd.read_csv(uploaded_file)
                    else:
                        imp_df = pd.read_excel(uploaded_file)

                    st.write("🔍 ពិនិត្យមើលគំរូទិន្នន័យដែលបានបញ្ចូល:")
                    st.dataframe(imp_df.head(), use_container_width=True)

                    if st.button("🚀 អនុវត្តការនាំចូលទិន្នន័យ", use_container_width=True):
                        items_to_import = {}

                        for _, row in imp_df.iterrows():
                            code = int(row.get("ក្បាលដី", row.get("code", 0)))
                            if 1 <= code <= active_total_items:
                                items_to_import[code] = {
                                    "status": str(row.get("Status", row.get("status", "មិនទាន់បានពិនិត្យ"))),
                                    "phone": str(row.get("លេខទូស័ព្ទ", row.get("customer_phone", ""))),
                                    "notes": str(row.get("ផ្សេងៗ", row.get("notes", ""))),
                                    "condition": str(row.get("Condition", row.get("condition", ""))),
                                    "updated_at": str(row.get("Last Updated", row.get("updated_at", get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p"))))
                                }

                        if items_to_import:
                            execute_import_excel_data(active_project_id, items_to_import)
                            st.success(f"បាននាំចូលទិន្នន័យចំនួន {len(items_to_import)} ក្បាលដីដោយជោគជ័យ!")
                            st.rerun()
                        else:
                            st.error("មិនមានទិន្នន័យក្បាលដីដែលត្រឹមត្រូវនៅក្នុងឯកសារនេះទេ!")

                except Exception as e:
                    st.error(f"មានកំហុសក្នុងការអានឯកសារ: {e}")

    # 4. TRANSACTION LOGS HISTORY
    elif action == "📜 ប្រវត្តិប្រតិបត្តិការ":
        st.subheader("📜 ប្រវត្តិប្រតិបត្តិការ (Activity Logs)")

        logs_df = get_history_logs(active_project_id)

        if not logs_df.empty:
            st.dataframe(logs_df, use_container_width=True)

            log_csv = logs_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="⬇️ ទាញយកប្រវត្តិប្រតិបត្តិការជា CSV",
                data=log_csv,
                file_name=f"{selected_project_name}_logs.csv",
                mime="text/csv"
            )
        else:
            st.info("មិនទាន់មានប្រវត្តិប្រតិបត្តិការនៅក្នុងគម្រោងនេះនៅឡើយទេ។")
