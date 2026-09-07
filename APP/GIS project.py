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

    # Safe migration check: Add temp_admin_expires column if missing in existing databases
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

    cursor.execute("""
        INSERT OR IGNORE INTO app_settings (key, value)
        VALUES ('app_title', '📦 កម្មវិធីបិតផ្សាយ ខេត្តបាត់ដំបង')
    """)

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
    return row[0] if row else "📦 កម្មវិធីបិតផ្សាយ ខេត្តបាត់ដំបង"


def set_app_title(new_title):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('app_title', ?)", (new_title,))
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
    notes = str(row["ផ្សេងៗ"])
    return ("គ្មានទិន្នន័យ" in cond) or (notes.strip() == "គ្មានទិន្នន័យ")


def update_item_in_db(project_id, code, status, phone, notes, condition, custom_timestamp):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM items WHERE project_id = ? AND code = ?
    """, (project_id, code))
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
        action_type="Item Updated",
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
            "Date & Time": log[0] if log[0] else "",
            "ក្បាលដី": log[1] if log[1] else "",
            "Action": log[2] if log[2] else "",
            "Status": log_status if log_status else "",
            "លេខទូស័ព្ទ": log[4] if log[4] else "",
            "ផ្សេងៗ": log[5] if log[5] else "",
            "Condition": log[6] if log[6] else "ធម្មតា"
        })
    return pd.DataFrame(data)


def render_project_selector(key_prefix="modal"):
    projects = get_all_projects()
    mode = st.radio("Select Option", ["Select Existing Project", "Create New Project"], key=f"{key_prefix}_mode")

    if mode == "Select Existing Project":
        if projects:
            project_options = {f"{p[1]} (ក្បាលដីសរុប: {p[2]})": p for p in projects}
            selected_label = st.selectbox("Choose Project", list(project_options.keys()), key=f"{key_prefix}_select")
            if st.button("Load Selected Project", use_container_width=True, key=f"{key_prefix}_btn_load"):
                p_id, p_name, p_items = project_options[selected_label]
                st.session_state["active_project"] = (p_id, p_name, p_items)
                st.session_state["show_startup_popup"] = False
                st.session_state["msg"] = ("success", f"Successfully loaded project '{p_name}'!")
                st.session_state["active_tab"] = "Full Inventory"
                st.session_state["nav_expanded"] = False
                st.rerun()
        else:
            st.warning("No existing projects found. Please create one below.")

    if mode == "Create New Project" or not projects:
        new_name = st.text_input("Project Name", value="Default Project", key=f"{key_prefix}_name")
        total_items_input = st.number_input("ក្បាលដីសរុប", min_value=1, value=100, key=f"{key_prefix}_items")

        if st.button("Save & Open Project", use_container_width=True, key=f"{key_prefix}_btn_create"):
            p_id, p_name, p_items = create_new_project(new_name, int(total_items_input))
            st.session_state["active_project"] = (p_id, p_name, p_items)
            st.session_state["show_startup_popup"] = False
            st.session_state["msg"] = ("success", f"Successfully created/loaded project '{p_name}'!")
            st.session_state["active_tab"] = "Full Inventory"
            st.session_state["nav_expanded"] = False
            st.rerun()


@st.dialog(" ")
def show_success_dialog(summary):
    st.markdown("""
        <div style="text-align: center; padding: 10px 0;">
            <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="#28a745" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M9 12l2 2 4-4"></path>
            </svg>
            <h2 style="margin-top: 10px; margin-bottom: 5px; color: #111827; font-size: 22px; font-weight: 600;">
                Saved Successfully!
            </h2>
            <p style="color: #6b7280; font-size: 14px; margin-bottom: 20px;">
                Your item details have been recorded into the project database.
            </p>
        </div>
    """, unsafe_allow_html=True)

    summary_df = pd.DataFrame([
        {"Detail Field": "ក្បាលដី (Code)", "Saved Value": summary['code']},
        {"Detail Field": "Status", "Saved Value": summary['status']},
        {"Detail Field": "លេខទូស័ព្ទ (Phone)", "Saved Value": summary['phone']},
        {"Detail Field": "Condition", "Saved Value": summary['condition']},
        {"Detail Field": "ផ្សេងៗ (Notes)", "Saved Value": summary['notes']},
        {"Detail Field": "Date & Time", "Saved Value": summary['timestamp']},
    ])

    st.table(summary_df)

    if st.button("Close Window", use_container_width=True):
        st.session_state.pop("show_save_success_dialog", None)
        st.rerun()


if hasattr(st, "dialog"):
    @st.dialog("🚀 Welcome! Select or Create Project")
    def startup_project_modal():
        st.write("Please select an existing project or create a new one to continue.")
        render_project_selector(key_prefix="popup")
else:
    def startup_project_modal():
        st.subheader("🚀 Welcome! Select or Create Project")
        render_project_selector(key_prefix="popup")


def apply_center_alignment():
    st.markdown("""
        <style>
            .stAppViewContainer, .stMarkdown, h1, h2, h3, h4, h5, h6, p, label {
                text-align: center !important;
            }
            .stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox {
                text-align: center !important;
            }
            div[data-testid="stForm"] {
                text-align: center !important;
            }
            [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {
                text-align: center !important;
            }
        </style>
    """, unsafe_allow_html=True)


def switch_tab(tab_name):
    st.session_state["active_tab"] = tab_name
    st.session_state["nav_expanded"] = False
    st.rerun()


def main():
    st.set_page_config(page_title="Project Manager", layout="wide")
    apply_center_alignment()
    initialize_database()

    # Route 1: Pending User Waiting Screen
    if "pending_user" in st.session_state:
        render_pending_waiting_screen(st.session_state["pending_user"])
        return

    # Route 2: Unauthenticated - Show Login / Registration Portal
    if not st.session_state.get("authenticated", False):
        render_auth_page()
        return

    # Route 3: Authenticated App Logic
    if "nav_expanded" not in st.session_state:
        st.session_state["nav_expanded"] = False

    if st.session_state.get("show_startup_popup", True) or "active_project" not in st.session_state:
        startup_project_modal()
        if "active_project" not in st.session_state:
            return

    if st.session_state.get("show_save_success_dialog", False):
        show_success_dialog(st.session_state.get("last_saved_summary", {}))

    # Real-time check of session state role
    current_username = st.session_state.get("username", "Guest")
    user_data = get_user_from_db(current_username)
    
    if not user_data or user_data[4] == "inactive":
        st.error("Your account has been deactivated or removed.")
        st.session_state["authenticated"] = False
        st.rerun()

    current_role = user_data[3]
    st.session_state["role"] = current_role

    is_admin = current_role in ["admin", "temp_admin"]
    app_title = get_app_title()

    # Header Bar
    head_col1, head_col2 = st.columns([8, 2])
    with head_col1:
        st.title(app_title)
        st.caption(f"Logged in as: **{current_username}** ({current_role.upper().replace('_', ' ')})")
    with head_col2:
        if st.button("Logout"):
            st.session_state["authenticated"] = False
            st.session_state["show_startup_popup"] = True
            st.session_state.pop("active_project", None)
            st.session_state.pop("username", None)
            st.session_state.pop("role", None)
            st.rerun()

    project_id, project_name, total_items = st.session_state["active_project"]

    if "msg" in st.session_state:
        msg_type, msg_text = st.session_state["msg"]
        if msg_type == "success":
            st.success(msg_text)
        elif msg_type == "info":
            st.info(msg_text)
        elif msg_type == "warning":
            st.warning(msg_text)
        del st.session_state["msg"]

    st.subheader(f"Active Project: **{project_name}** (ក្បាលដីសរុប: {total_items})")

    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = "Full Inventory"

    # Navigation Drawer Menu
    with st.expander("☰ Navigation & Settings (Click to Open/Close)", expanded=st.session_state["nav_expanded"]):
        cols = st.columns(5 if is_admin else 4)
        with cols[0]:
            if st.button("📋 Full Inventory", use_container_width=True):
                switch_tab("Full Inventory")
            if st.button("✏️ Update Item", use_container_width=True):
                switch_tab("Update Item")

        with cols[1]:
            if st.button("⏳ មិនទាន់បានពិនិត្យ", use_container_width=True):
                switch_tab("Not Yet Checked")
            if st.button("✅ បានពិនិត្យ", use_container_width=True):
                switch_tab("Checked Items")

        with cols[2]:
            if st.button("🚫 ក្បាលដីគ្មានទិន្នន័យ", use_container_width=True):
                switch_tab("No Data Items")
            if st.button("📊 Condition Summary", use_container_width=True):
                switch_tab("Condition Summary")

        with cols[3]:
            if st.button("📜 History Log", use_container_width=True):
                switch_tab("History Log")
            if st.button("⚙️ Project Settings", use_container_width=True):
                switch_tab("Project Settings")

        if is_admin:
            with cols[4]:
                if st.button("👥 Admin Control", use_container_width=True):
                    switch_tab("Admin Control")

    st.write("---")

    active_tab = st.session_state["active_tab"]

    # Admin Control Panel
    if active_tab == "Admin Control" and is_admin:
        st.write("### 👥 Admin Control & User Management")

        # System Title Customization
        st.write("#### ✏️ Change Application Title")
        with st.form("admin_title_form"):
            new_title_input = st.text_input("Application Title", value=app_title)
            save_title_btn = st.form_submit_button("Update App Title")
            if save_title_btn and new_title_input.strip():
                set_app_title(new_title_input.strip())
                st.session_state["msg"] = ("success", "App title updated successfully!")
                st.rerun()

        st.write("---")
        st.write("#### 👥 Manage User Accounts & Permissions")
        df_users = get_all_users()
        st.dataframe(df_users, use_container_width=True)

        st.write("##### User Account Actions")
        target_user = st.selectbox("Select User Account to Modify", options=df_users["Username"].tolist())

        target_row = df_users[df_users["Username"] == target_user].iloc[0]
        t_id = target_row["ID"]
        t_role = target_row["Role"]
        t_status = target_row["Status"]

        # Immunity Protection Check
        if target_user == DEFAULT_ADMIN_USER:
            st.info(f"🛡️ **{DEFAULT_ADMIN_USER}** is the Root Administrator and cannot be edited or modified by anyone.")
        else:
            action_c1, action_c2, action_c3 = st.columns(3)

            with action_c1:
                st.write("**Account Active Status**")
                if t_status == "approved":
                    if st.button("Set to INACTIVE", use_container_width=True):
                        update_user_status(t_id, "inactive")
                        st.session_state["msg"] = ("warning", f"User {target_user} is now INACTIVE.")
                        st.rerun()
                else:
                    if st.button("Set to ACTIVE (Approve)", use_container_width=True):
                        update_user_status(t_id, "approved")
                        st.session_state["msg"] = ("success", f"User {target_user} activated.")
                        st.rerun()

            with action_c2:
                st.write("**Grant Temporary Admin Power**")
                hours = st.number_input("Admin Duration (Hours)", min_value=1, max_value=720, value=2)
                if st.button("Give Temporary Admin", use_container_width=True):
                    exp_dt = get_cambodia_now() + datetime.timedelta(hours=int(hours))
                    set_temporary_admin(t_id, exp_dt)
                    st.session_state["msg"] = ("success", f"Granted Temp Admin to {target_user} until {exp_dt.strftime('%d/%m/%Y %I:%M %p')}")
                    st.rerun()

                if t_role == "temp_admin":
                    if st.button("Revoke Temp Admin Immediately", use_container_width=True):
                        revoke_admin_role(t_id)
                        st.session_state["msg"] = ("info", f"Revoked admin privileges from {target_user}")
                        st.rerun()

            with action_c3:
                st.write("**Permanent Account Deletion**")
                if st.button(f"🚨 Delete Account '{target_user}'", use_container_width=True):
                    delete_user_account(t_id)
                    st.session_state["msg"] = ("warning", f"Account '{target_user}' permanently deleted.")
                    st.rerun()

    elif active_tab == "Project Settings":
        st.write("### ⚙️ Project Settings & Administration")

        if is_admin:
            st.write("#### ✏️ Edit Active Project Details")
            with st.form("edit_project_form"):
                edit_name = st.text_input("Project Name", value=project_name)
                edit_total = st.number_input("Total Items (ក្បាលដីសរុប)", min_value=1, value=total_items)
                update_proj_btn = st.form_submit_button("Update Project Info")

                if update_proj_btn:
                    success, msg = update_project_details(project_id, edit_name.strip(), int(edit_total))
                    if success:
                        st.session_state["active_project"] = (project_id, edit_name.strip(), int(edit_total))
                        st.session_state["msg"] = ("success", "Project details updated!")
                        st.rerun()
                    else:
                        st.error(msg)

            st.write("---")
            st.write("#### 🗑️ Delete Project")
            st.warning("Deleting this project will permanently remove all associated items and log history.")
            if st.button("🚨 Delete Active Project Completely", use_container_width=True):
                delete_project(project_id)
                st.session_state.pop("active_project", None)
                st.session_state["show_startup_popup"] = True
                st.session_state["msg"] = ("warning", f"Project '{project_name}' has been deleted.")
                st.rerun()

        st.write("---")
        st.write("#### 🔄 Switch or Create Project")
        render_project_selector(key_prefix="tab")

    else:
        df_items = get_project_items(project_id, total_items)

        df_valid_items = df_items[~df_items.apply(is_no_data, axis=1)]
        df_no_data_items = df_items[df_items.apply(is_no_data, axis=1)]

        if active_tab == "Full Inventory":
            st.write("### Complete Inventory List (Excluding គ្មានទិន្នន័យ)")
            st.dataframe(df_valid_items, use_container_width=True)

            if is_admin:
                st.write("---")
                st.write("### 🛠️ Admin Inventory Controls")
                inv_col1, inv_col2 = st.columns(2)

                with inv_col1:
                    st.write("#### ➕ Add Items to Inventory")
                    add_qty = st.number_input("How many items to add?", min_value=1, value=1, step=1, key="add_qty_input")
                    if st.button(f"Add {add_qty} Item(s)", use_container_width=True):
                        new_total = total_items + int(add_qty)
                        update_project_details(project_id, project_name, new_total)
                        st.session_state["active_project"] = (project_id, project_name, new_total)
                        st.session_state["msg"] = ("success", f"Added {add_qty} item(s). New total count is {new_total}.")
                        st.rerun()

                with inv_col2:
                    st.write("#### 🗑️ Delete Specific Item")
                    del_code = st.number_input("Enter Item Code (ក្បាលដី) to Delete", min_value=1, max_value=total_items, step=1, key="del_code_input")
                    if st.button(f"Delete Item #{del_code}", use_container_width=True):
                        delete_item_by_code(project_id, int(del_code))
                        st.session_state["msg"] = ("success", f"Item #{del_code} permanently removed.")
                        st.rerun()

        elif active_tab == "Update Item":
            st.write("### Update Item Details")

            search_col, load_btn_col = st.columns([3, 1])
            with search_col:
                code_to_update = st.number_input(
                    "ក្បាលដី",
                    min_value=1,
                    max_value=total_items,
                    step=1,
                    key="update_item_code_input"
                )
            with load_btn_col:
                st.write("&#160;")
                if st.button("🔄 Refresh Data", use_container_width=True):
                    st.rerun()

            current_row = df_items[df_items["ក្បាលដី"] == code_to_update].iloc[0] if not df_items.empty else None
            curr_status = current_row["Status"] if current_row is not None else "មិនទាន់បានពិនិត្យ"
            curr_phone = current_row["លេខទូស័ព្ទ"] if current_row is not None else ""
            curr_notes = current_row["ផ្សេងៗ"] if current_row is not None else ""

            curr_cond_str = current_row["Condition"] if (current_row is not None and current_row["Condition"] not in ["-", "ធម្មតា"]) else ""
            default_conditions = [c.strip() for c in curr_cond_str.split(", ") if c.strip() in CONDITION_OPTIONS]

            if st.session_state.get("clear_form_trigger", False):
                curr_status = "មិនទាន់បានពិនិត្យ"
                curr_phone = ""
                curr_notes = ""
                default_conditions = []
                st.session_state["clear_form_trigger"] = False

            with st.form("update_form"):
                is_checked = st.checkbox("បានពិនិត្យ", value=(curr_status == "បានពិនិត្យ"))
                no_data_checked = st.checkbox("គ្មានទិន្នន័យ", value=("គ្មានទិន្នន័យ" in default_conditions or curr_notes == "គ្មានទិន្នន័យ"))

                phone_input = st.text_input("លេខទូស័ព្ទ", value=curr_phone)
                notes_input = st.text_area("ផ្សេងៗ", value=curr_notes)

                selected_conditions = st.multiselect(
                    "Condition (Multiple selection allowed)",
                    options=CONDITION_OPTIONS,
                    default=default_conditions
                )

                st.write("---")
                st.write("#### Edit Date & Time")

                current_cambodia_dt = get_cambodia_now()

                date_col, time_col = st.columns(2)
                with date_col:
                    selected_date = st.date_input("Update Date", value=current_cambodia_dt.date())
                with time_col:
                    selected_time = st.time_input("Update Time", value=current_cambodia_dt.time())

                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                    submitted = st.form_submit_button("Save Changes", use_container_width=True)
                with btn_c2:
                    clear_form_btn = st.form_submit_button("🧹 Clear Form Inputs", use_container_width=True)

                if clear_form_btn:
                    st.session_state["clear_form_trigger"] = True
                    st.rerun()

                if submitted:
                    new_status = "បានពិនិត្យ" if is_checked else "មិនទាន់បានពិនិត្យ"

                    final_notes = "គ្មានទិន្នន័យ" if no_data_checked and not notes_input.strip() else notes_input

                    if no_data_checked and "គ្មានទិន្នន័យ" not in selected_conditions:
                        selected_conditions.append("គ្មានទិន្នន័យ")

                    condition_str = ", ".join(selected_conditions) if selected_conditions else "ធម្មតា"

                    combined_dt = datetime.datetime.combine(selected_date, selected_time)
                    formatted_dt = combined_dt.strftime("%d/%m/%Y, %I:%M %p")

                    update_item_in_db(project_id, code_to_update, new_status, phone_input, final_notes, condition_str, formatted_dt)

                    st.session_state["last_saved_summary"] = {
                        "code": str(code_to_update),
                        "status": new_status,
                        "phone": phone_input,
                        "notes": final_notes,
                        "condition": condition_str,
                        "timestamp": formatted_dt
                    }
                    st.session_state["show_save_success_dialog"] = True
                    st.rerun()

            if is_admin:
                st.write("---")
                st.write("#### 🧹 Admin: Clear Item Data")
                if st.button(f"Reset Item #{code_to_update} Back to Default", use_container_width=True):
                    reset_single_item_data(project_id, code_to_update)
                    st.session_state["msg"] = ("success", f"Item #{code_to_update} data cleared successfully.")
                    st.rerun()

        elif active_tab == "Not Yet Checked":
            not_checked_df = df_valid_items[df_valid_items["Status"] == "មិនទាន់បានពិនិត្យ"]
            st.write(f"### មិនទាន់បានពិនិត្យ (Total Left: {len(not_checked_df)})")
            st.dataframe(not_checked_df, use_container_width=True)

        elif active_tab == "Checked Items":
            checked_df = df_valid_items[df_valid_items["Status"] == "បានពិនិត្យ"]
            st.write(f"### បានពិនិត្យ (Total Checked: {len(checked_df)})")

            search_code = st.number_input("Search ក្បាលដី in បានពិនិត្យ", min_value=0, max_value=total_items, value=0)
            if search_code > 0:
                filtered_df = checked_df[checked_df["ក្បាលដី"] == search_code]
                st.dataframe(filtered_df, use_container_width=True)
            else:
                st.dataframe(checked_df, use_container_width=True)

        elif active_tab == "No Data Items":
            st.write(f"### 🚫 ក្បាលដីគ្មានទិន្នន័យ (Total: {len(df_no_data_items)})")
            st.dataframe(df_no_data_items, use_container_width=True)

        elif active_tab == "Condition Summary":
            st.write("### 📊 Condition Summary & Analysis")

            summary_data = []
            for option in CONDITION_OPTIONS:
                matching_codes = []
                for _, row in df_items.iterrows():
                    item_cond = row["Condition"]
                    if item_cond and item_cond not in ["-", "ធម្មតា"]:
                        cond_list = [c.strip() for c in item_cond.split(",")]
                        if option in cond_list:
                            matching_codes.append(str(row["ក្បាលដី"]))

                summary_data.append({
                    "Condition Category": option,
                    "Total Count": len(matching_codes),
                    "ក្បាលដី Codes": ", ".join(matching_codes) if matching_codes else ""
                })

            summary_df = pd.DataFrame(summary_data)
            st.dataframe(summary_df, use_container_width=True)

            if is_admin:
                st.write("---")
                st.write("#### 🧹 Admin Controls")
                if st.button("Clear All Condition Summaries from this Project", use_container_width=True):
                    clear_conditions_data(project_id)
                    st.session_state["msg"] = ("success", "Condition data cleared successfully!")
                    st.rerun()

        elif active_tab == "History Log":
            st.write("### 📜 Activity History Log")
            df_history = get_project_history(project_id)
            if not df_history.empty:
                st.dataframe(df_history, use_container_width=True)
            else:
                st.info("No activity logged for this project yet.")

            if is_admin:
                st.write("---")
                st.write("#### 🧹 Admin Controls")
                if st.button("Clear History Log for this Project", use_container_width=True):
                    clear_history_logs(project_id)
                    st.session_state["msg"] = ("success", "History log cleared successfully!")
                    st.rerun()


if __name__ == "__main__":
    main()
