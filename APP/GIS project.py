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


def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
            
            html, body, [class*="css"] {
                font-family: 'Inter', system-ui, -apple-system, sans-serif;
            }
            
            /* Center Alignment */
            .stAppViewContainer, .stMarkdown, h1, h2, h3, h4, h5, h6, p, label {
                text-align: center !important;
            }
            .stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox {
                text-align: center !important;
                border-radius: 8px !important;
            }
            
            /* Modern Card Styling */
            div[data-testid="stForm"] {
                border-radius: 12px !important;
                border: 1px solid #E5E7EB !important;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03) !important;
                padding: 2rem !important;
                background-color: #ffffff !important;
            }
            
            /* Metric Box Styling */
            .metric-card {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                padding: 1.25rem;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
                margin-bottom: 1rem;
            }
            .metric-title {
                color: #6B7280;
                font-size: 0.875rem;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }
            .metric-value {
                color: #111827;
                font-size: 1.875rem;
                font-weight: 700;
                margin-top: 0.25rem;
            }
            
            /* Header Box */
            .header-banner {
                background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
                color: white;
                padding: 1.5rem;
                border-radius: 12px;
                margin-bottom: 1.5rem;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            }
            .header-banner h1 {
                color: #FFFFFF !important;
                font-weight: 700 !important;
                margin: 0 !important;
                font-size: 1.75rem !important;
            }
            .header-banner p {
                color: #94A3B8 !important;
                margin: 0.25rem 0 0 0 !important;
                font-size: 0.9rem !important;
            }
            
            /* Tables */
            [data-testid="stDataFrame"] {
                border-radius: 8px;
                overflow: hidden;
                border: 1px solid #E5E7EB;
            }
            [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {
                text-align: center !important;
            }
            
            /* Buttons */
            .stButton > button {
                border-radius: 8px !important;
                font-weight: 500 !important;
                transition: all 0.2s ease-in-out !important;
            }
            .stButton > button:hover {
                transform: translateY(-1px);
            }
        </style>
    """, unsafe_allow_html=True)


def render_auth_page():
    st.markdown("""
        <div style="max-width: 450px; margin: 0 auto; padding-top: 2rem;">
            <h1 style="font-size: 2rem; font-weight: 700; color: #1E293B; margin-bottom: 0.5rem;">Welcome Back</h1>
            <p style="color: #64748B; font-size: 0.95rem; margin-bottom: 2rem;">Authentication & Access Portal</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        mode = st.radio("Select Action", ["Log In", "Create New Account"], horizontal=True, label_visibility="collapsed")

        if mode == "Log In":
            st.write("---")
            role_type = st.selectbox("Login Role Mode", ["Normal User", "Admin / Temp Admin"])

            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                login_btn = st.form_submit_button("Sign In", use_container_width=True)

                if login_btn:
                    user = get_user_from_db(username)
                    if user and user[2] == password:
                        db_role = user[3]
                        db_status = user[4]

                        if db_status == "inactive":
                            st.error("🔒 Account INACTIVE. Contact root admin.")
                            return

                        if db_status == "pending":
                            st.session_state["pending_user"] = username
                            st.session_state["authenticated"] = False
                            st.rerun()
                        elif db_status == "rejected":
                            st.error("Account registration request was rejected.")
                        elif db_status == "approved":
                            if role_type == "Admin / Temp Admin" and db_role not in ["admin", "temp_admin"]:
                                st.error("Account lacks Admin permissions.")
                                return

                            st.session_state["authenticated"] = True
                            st.session_state["username"] = username
                            st.session_state["role"] = db_role
                            st.session_state["show_startup_popup"] = True
                            st.session_state.pop("pending_user", None)
                            st.success("Login successful!")
                            st.rerun()
                    else:
                        st.error("Invalid credentials.")

        elif mode == "Create New Account":
            st.write("---")
            requested_role = st.selectbox("Select Desired Role", ["user", "admin"])

            with st.form("register_form"):
                new_user = st.text_input("Username", placeholder="Choose a username")
                new_pass = st.text_input("Password", type="password", placeholder="••••••••")
                confirm_pass = st.text_input("Confirm Password", type="password", placeholder="••••••••")
                reg_btn = st.form_submit_button("Request Account", use_container_width=True)

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
    user = get_user_from_db(username)
    if not user:
        st.error("Account not found.")
        if st.button("Back to Login"):
            st.session_state.pop("pending_user", None)
            st.rerun()
        return

    status = user[4]

    st.markdown("<div style='height: 50px;'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])

    with c2:
        if status == "pending":
            st.info(f"⏳ **Account Approval Pending**\n\nHello **{username}**, your account request is pending admin review.")
            time.sleep(3)
            st.rerun()

        elif status == "approved":
            st.success(f"🎉 **Account Approved!**\n\nWelcome **{username}**!")
            if st.button("Continue to Dashboard", use_container_width=True):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.session_state["role"] = user[3]
                st.session_state["show_startup_popup"] = True
                st.session_state.pop("pending_user", None)
                st.rerun()

        elif status == "rejected":
            st.error(f"❌ **Request Rejected**\n\nSorry **{username}**, your registration request was declined.")
            if st.button("Return to Login", use_container_width=True):
                st.session_state.pop("pending_user", None)
                st.rerun()


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
        log_activity(project_id, None, "Project Created",
                     notes=f"Created project '{name}' with ក្បាលដីសរុប {total_items}")
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
    mode = st.radio("Select Option", ["Select Existing Project", "Create New Project"], key=f"{key_prefix}_mode", horizontal=True)

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
        <div style="text-align: center; padding: 5px 0;">
            <div style="background-color: #DEF7EC; width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 10px auto;">
                <span style="color: #0E9F6E; font-size: 24px;">✓</span>
            </div>
            <h3 style="margin: 0; color: #111827; font-size: 20px; font-weight: 600;">Saved Successfully</h3>
            <p style="color: #6B7280; font-size: 13px; margin-top: 4px; margin-bottom: 15px;">Item details updated in project database.</p>
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
    @st.dialog("🚀 Select or Create Project")
    def startup_project_modal():
        render_project_selector(key_prefix="popup")
else:
    def startup_project_modal():
        st.subheader("🚀 Select or Create Project")
        render_project_selector(key_prefix="popup")


def switch_tab(tab_name):
    st.session_state["active_tab"] = tab_name
    st.session_state["nav_expanded"] = False
    st.rerun()


def main():
    st.set_page_config(page_title="Project Manager", layout="wide")
    inject_custom_css()
    initialize_database()

    if "pending_user" in st.session_state:
        render_pending_waiting_screen(st.session_state["pending_user"])
        return

    if not st.session_state.get("authenticated", False):
        render_auth_page()
        return

    if "nav_expanded" not in st.session_state:
        st.session_state["nav_expanded"] = False

    if st.session_state.get("show_startup_popup", True) or "active_project" not in st.session_state:
        startup_project_modal()
        if "active_project" not in st.session_state:
            return

    if st.session_state.get("show_save_success_dialog", False):
        show_success_dialog(st.session_state.get("last_saved_summary", {}))

    current_username = st.session_state.get("username", "Guest")
    user_data = get_user_from_db(current_username)

    if not user_data or user_data[4] == "inactive":
        st.error("Account deactivated or removed.")
        st.session_state["authenticated"] = False
        st.rerun()

    current_role = user_data[3]
    st.session_state["role"] = current_role
    is_admin = current_role in ["admin", "temp_admin"]
    app_title = get_app_title()

    # Modern Header Banner
    st.markdown(f"""
        <div class="header-banner">
            <h1>{app_title}</h1>
            <p>Logged in as: <b>{current_username}</b> ({current_role.upper().replace('_', ' ')})</p>
        </div>
    """, unsafe_allow_html=True)

    logout_col1, logout_col2 = st.columns([8, 2])
    with logout_col2:
        if st.button("🚪 Log Out", use_container_width=True):
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

    st.subheader(f"Active Project: {project_name}")
    st.caption(f"Total Land Plots (ក្បាលដីសរុប): {total_items}")

    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = "Full Inventory"

    # Sleek Pill-Style Navigation Bar
    st.write("---")
    nav_cols = st.columns(5 if is_admin else 4)
    with nav_cols[0]:
        if st.button("📋 Inventory", use_container_width=True): switch_tab("Full Inventory")
        if st.button("✏️ Edit Item", use_container_width=True): switch_tab("Update Item")
    with nav_cols[1]:
        if st.button("⏳ Unchecked", use_container_width=True): switch_tab("Not Yet Checked")
        if st.button("✅ Checked", use_container_width=True): switch_tab("Checked Items")
    with nav_cols[2]:
        if st.button("🚫 No Data", use_container_width=True): switch_tab("No Data Items")
        if st.button("📊 Conditions", use_container_width=True): switch_tab("Condition Summary")
    with nav_cols[3]:
        if st.button("📜 Logs", use_container_width=True): switch_tab("History Log")
        if st.button("⚙️ Settings", use_container_width=True): switch_tab("Project Settings")
    if is_admin:
        with nav_cols[4]:
            if st.button("👥 Admin Control", use_container_width=True): switch_tab("Admin Control")

    st.write("---")
    active_tab = st.session_state["active_tab"]

    if active_tab == "Admin Control" and is_admin:
        st.markdown("### 👥 Admin Control & User Management")

        with st.form("admin_title_form"):
            st.markdown("#### App Title Settings")
            new_title_input = st.text_input("Application Title", value=app_title)
            save_title_btn = st.form_submit_button("Update App Title", use_container_width=True)
            if save_title_btn and new_title_input.strip():
                set_app_title(new_title_input.strip())
                st.session_state["msg"] = ("success", "App title updated successfully!")
                st.rerun()

        st.write("---")
        df_users = get_all_users()
        st.dataframe(df_users, use_container_width=True)

        target_user = st.selectbox("Select User Account to Modify", options=df_users["Username"].tolist())
        target_row = df_users[df_users["Username"] == target_user].iloc[0]
        t_id, t_role, t_status = target_row["ID"], target_row["Role"], target_row["Status"]

        if target_user == DEFAULT_ADMIN_USER:
            st.info(f"🛡️ **{DEFAULT_ADMIN_USER}** is protected and cannot be edited.")
        else:
            action_c1, action_c2, action_c3 = st.columns(3)
            with action_c1:
                if t_status == "approved":
                    if st.button("Set INACTIVE", use_container_width=True):
                        update_user_status(t_id, "inactive")
                        st.session_state["msg"] = ("warning", f"User {target_user} is now INACTIVE.")
                        st.rerun()
                else:
                    if st.button("Approve User", use_container_width=True):
                        update_user_status(t_id, "approved")
                        st.session_state["msg"] = ("success", f"User {target_user} activated.")
                        st.rerun()

            with action_c2:
                hours = st.number_input("Admin Duration (Hours)", min_value=1, max_value=720, value=2)
                if st.button("Grant Temp Admin", use_container_width=True):
                    exp_dt = get_cambodia_now() + datetime.timedelta(hours=int(hours))
                    set_temporary_admin(t_id, exp_dt)
                    st.session_state["msg"] = ("success", f"Temp Admin given to {target_user}")
                    st.rerun()

            with action_c3:
                if st.button(f"🚨 Delete Account", use_container_width=True):
                    delete_user_account(t_id)
                    st.session_state["msg"] = ("warning", f"Account '{target_user}' deleted.")
                    st.rerun()

    elif active_tab == "Project Settings":
        st.markdown("### ⚙️ Project Settings")
        if is_admin:
            with st.form("edit_project_form"):
                edit_name = st.text_input("Project Name", value=project_name)
                edit_total = st.number_input("Total Items (ក្បាលដីសរុប)", min_value=1, value=total_items)
                update_proj_btn = st.form_submit_button("Update Project Details", use_container_width=True)

                if update_proj_btn:
                    success, msg = update_project_details(project_id, edit_name.strip(), int(edit_total))
                    if success:
                        st.session_state["active_project"] = (project_id, edit_name.strip(), int(edit_total))
                        st.session_state["msg"] = ("success", "Project updated!")
                        st.rerun()
                    else:
                        st.error(msg)

            if st.button("🚨 Delete Project Completely", use_container_width=True):
                delete_project(project_id)
                st.session_state.pop("active_project", None)
                st.session_state["show_startup_popup"] = True
                st.session_state["msg"] = ("warning", f"Project '{project_name}' deleted.")
                st.rerun()

        st.write("---")
        render_project_selector(key_prefix="tab")

    else:
        df_items = get_project_items(project_id, total_items)
        df_valid_items = df_items[~df_items.apply(is_no_data, axis=1)]
        df_no_data_items = df_items[df_items.apply(is_no_data, axis=1)]

        if active_tab == "Full Inventory":
            st.markdown("### Complete Inventory List")
            st.dataframe(df_valid_items, use_container_width=True)

            if is_admin:
                st.write("---")
                inv_col1, inv_col2 = st.columns(2)
                with inv_col1:
                    add_qty = st.number_input("Add items count", min_value=1, value=1, step=1)
                    if st.button(f"Add {add_qty} Item(s)", use_container_width=True):
                        new_total = total_items + int(add_qty)
                        update_project_details(project_id, project_name, new_total)
                        st.session_state["active_project"] = (project_id, project_name, new_total)
                        st.session_state["msg"] = ("success", f"Added {add_qty} item(s).")
                        st.rerun()

                with inv_col2:
                    del_code = st.number_input("Delete Plot #", min_value=1, max_value=total_items, step=1)
                    if st.button(f"Delete Item #{del_code}", use_container_width=True):
                        delete_item_by_code(project_id, int(del_code))
                        st.session_state["msg"] = ("success", f"Item #{del_code} deleted.")
                        st.rerun()

        elif active_tab == "Update Item":
            st.markdown("### Update Item Details")

            search_col, load_btn_col = st.columns([3, 1])
            with search_col:
                code_to_update = st.number_input("ក្បាលដី", min_value=1, max_value=total_items, step=1)
            with load_btn_col:
                st.write("&#160;")
                if st.button("🔄 Refresh", use_container_width=True): st.rerun()

            current_row = df_items[df_items["ក្បាលដី"] == code_to_update].iloc[0] if not df_items.empty else None
            curr_status = current_row["Status"] if current_row is not None else "មិនទាន់បានពិនិត្យ"
            curr_phone = current_row["លេខទូស័ព្ទ"] if current_row is not None else ""
            curr_notes = current_row["ផ្សេងៗ"] if current_row is not None else ""

            curr_cond_str = current_row["Condition"] if (current_row is not None and current_row["Condition"] not in ["-", "ធម្មតា"]) else ""
            default_conditions = [c.strip() for c in curr_cond_str.split(", ") if c.strip() in CONDITION_OPTIONS]

            if st.session_state.get("clear_form_trigger", False):
                curr_status, curr_phone, curr_notes, default_conditions = "មិនទាន់បានពិនិត្យ", "", "", []
                st.session_state["clear_form_trigger"] = False

            with st.form("update_form"):
                is_checked = st.checkbox("បានពិនិត្យ", value=(curr_status == "បានពិនិត្យ"))
                no_data_checked = st.checkbox("គ្មានទិន្នន័យ", value=("គ្មានទិន្នន័យ" in default_conditions or curr_notes == "គ្មានទិន្នន័យ"))

                phone_input = st.text_input("លេខទូស័ព្ទ", value=curr_phone)
                notes_input = st.text_area("ផ្សេងៗ", value=curr_notes)

                selected_conditions = st.multiselect("Condition", options=CONDITION_OPTIONS, default=default_conditions)

                current_cambodia_dt = get_cambodia_now()
                date_col, time_col = st.columns(2)
                with date_col: selected_date = st.date_input("Update Date", value=current_cambodia_dt.date())
                with time_col: selected_time = st.time_input("Update Time", value=current_cambodia_dt.time())

                btn_c1, btn_c2 = st.columns(2)
                with btn_c1: submitted = st.form_submit_button("Save Changes", use_container_width=True)
                with btn_c2: clear_form_btn = st.form_submit_button("🧹 Clear Form", use_container_width=True)

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
                if st.button(f"Reset Item #{code_to_update} to Default", use_container_width=True):
                    reset_single_item_data(project_id, code_to_update)
                    st.session_state["msg"] = ("success", f"Item #{code_to_update} cleared.")
                    st.rerun()

        elif active_tab == "Not Yet Checked":
            not_checked_df = df_valid_items[df_valid_items["Status"] == "មិនទាន់បានពិនិត្យ"]
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Remaining Unchecked Items</div>
                    <div class="metric-value">{len(not_checked_df)}</div>
                </div>
            """, unsafe_allow_html=True)
            st.dataframe(not_checked_df, use_container_width=True)

        elif active_tab == "Checked Items":
            checked_df = df_valid_items[df_valid_items["Status"] == "បានពិនិត្យ"]
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Total Checked Items</div>
                    <div class="metric-value">{len(checked_df)}</div>
                </div>
            """, unsafe_allow_html=True)

            search_code = st.number_input("Search Plot #", min_value=0, max_value=total_items, value=0)
            if search_code > 0:
                st.dataframe(checked_df[checked_df["ក្បាលដី"] == search_code], use_container_width=True)
            else:
                st.dataframe(checked_df, use_container_width=True)

        elif active_tab == "No Data Items":
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">No Data Plots</div>
                    <div class="metric-value">{len(df_no_data_items)}</div>
                </div>
            """, unsafe_allow_html=True)
            st.dataframe(df_no_data_items, use_container_width=True)

        elif active_tab == "Condition Summary":
            st.markdown("### 📊 Condition Summary")
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

            st.dataframe(pd.DataFrame(summary_data), use_container_width=True)

            if is_admin and st.button("Clear Conditions", use_container_width=True):
                clear_conditions_data(project_id)
                st.session_state["msg"] = ("success", "Condition data cleared!")
                st.rerun()

        elif active_tab == "History Log":
            st.markdown("### 📜 Activity History Log")
            df_history = get_project_history(project_id)
            if not df_history.empty:
                st.dataframe(df_history, use_container_width=True)
            else:
                st.info("No activity logged for this project yet.")

            if is_admin and st.button("Clear History Log", use_container_width=True):
                clear_history_logs(project_id)
                st.session_state["msg"] = ("success", "History log cleared!")
                st.rerun()


if __name__ == "__main__":
    main()
