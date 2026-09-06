import sqlite3
import datetime
from zoneinfo import ZoneInfo
import streamlit as st
import pandas as pd

# ==============================================================================
# 🔐 AUTHENTICATION SETTINGS (CHANGE YOUR USERNAME & PASSWORD HERE)
# ==============================================================================
USER_CREDENTIALS = {
    "Ra Vuth": "12354561"  # Format: "USERNAME": "PASSWORD"
}
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
    """Returns the current datetime in Cambodia (Asia/Phnom_Penh) timezone."""
    return datetime.datetime.now(CAMBODIA_TZ)


def initialize_database():
    """Sets up the database tables and safely migrates missing columns."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

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

    # Safely migrate missing columns for existing 'items' table
    cursor.execute("PRAGMA table_info(items)")
    items_columns = [column[1] for column in cursor.fetchall()]
    if "updated_at" not in items_columns:
        cursor.execute("ALTER TABLE items ADD COLUMN updated_at TEXT DEFAULT ''")
    if "condition" not in items_columns:
        cursor.execute("ALTER TABLE items ADD COLUMN condition TEXT DEFAULT ''")

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

    # Safely migrate missing columns for existing 'logs' table
    cursor.execute("PRAGMA table_info(logs)")
    logs_columns = [column[1] for column in cursor.fetchall()]

    if "status" not in logs_columns:
        cursor.execute("ALTER TABLE logs ADD COLUMN status TEXT DEFAULT ''")
    if "customer_phone" not in logs_columns:
        cursor.execute("ALTER TABLE logs ADD COLUMN customer_phone TEXT DEFAULT ''")
    if "notes" not in logs_columns:
        cursor.execute("ALTER TABLE logs ADD COLUMN notes TEXT DEFAULT ''")
    if "condition" not in logs_columns:
        cursor.execute("ALTER TABLE logs ADD COLUMN condition TEXT DEFAULT ''")

    conn.commit()
    conn.close()


def log_activity(project_id, code, action_type, status="", phone="", notes="", condition="", custom_timestamp=""):
    """Records an action in the database using Cambodia local time by default."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    timestamp = custom_timestamp if custom_timestamp else get_cambodia_now().strftime("%d/%m/%Y, %I:%M %p")

    cursor.execute("""
        INSERT INTO logs (project_id, code, action_type, status, customer_phone, notes, condition, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (project_id, code, action_type, status, phone, notes, condition, timestamp))

    conn.commit()
    conn.close()


def check_password():
    """Returns True if the user has logged in successfully."""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return True

    st.title("🔒 App Login Required")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Log In")

        if login_btn:
            if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
                st.session_state["authenticated"] = True
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Incorrect username or password.")
    return False


def get_all_projects():
    """Fetches list of all existing projects."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, total_items FROM projects")
    projects = cursor.fetchall()
    conn.close()
    return projects


def create_new_project(name, total_items):
    """Creates a new project or returns existing if name matches."""
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


def get_project_items(project_id, total_items):
    """Returns a full DataFrame of items for a given project with Khmer column titles."""
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


def update_item_in_db(project_id, code, status, phone, notes, condition, custom_timestamp):
    """Inserts or updates an item's details, condition, date/time, and logs changes."""
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
    """Fetches all history logs for the active project with Khmer column headers."""
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


def apply_center_alignment():
    """Injects custom CSS to align UI text, headings, inputs, and tables to the center."""
    st.markdown("""
        <style>
            /* Center headings and paragraphs */
            .stAppViewContainer, .stMarkdown, h1, h2, h3, h4, h5, h6, p, label {
                text-align: center !important;
            }
            /* Center form inputs & buttons */
            .stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox {
                text-align: center !important;
            }
            div[data-testid="stForm"] {
                text-align: center !important;
            }
            /* Center table cells */
            [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {
                text-align: center !important;
            }
        </style>
    """, unsafe_allow_html=True)


def main():
    st.set_page_config(page_title="កម្មវិធីបិតផ្សាយ ខេត្តបាត់ដំបង", layout="wide")
    apply_center_alignment()

    if not check_password():
        return

    initialize_database()

    # Top Header & Logout
    head_col1, head_col2 = st.columns([8, 2])
    with head_col1:
        st.title("📦 កម្មវិធីបិតផ្សាយ ខេត្តបាត់ដំបង")
    with head_col2:
        if st.button("Logout"):
            st.session_state["authenticated"] = False
            st.rerun()

    # Sidebar: Project Settings
    st.sidebar.header("Project Settings")
    projects = get_all_projects()

    project_mode = st.sidebar.radio("Project Mode", ["Select Existing", "Create New"])

    if project_mode == "Select Existing" and projects:
        project_options = {f"{p[1]} (ក្បាលដីសរុប: {p[2]})": p for p in projects}
        selected_label = st.sidebar.selectbox("Choose Project", list(project_options.keys()))
        project_id, project_name, total_items = project_options[selected_label]

        if st.sidebar.button("Load Selected Project"):
            st.session_state["active_project"] = (project_id, project_name, total_items)
            st.session_state["msg"] = ("success", f"Successfully loaded project '{project_name}'!")
            st.rerun()

    else:
        if project_mode == "Select Existing" and not projects:
            st.sidebar.warning("No existing projects found. Please create one.")

        new_name = st.sidebar.text_input("Project Name", value="Default Project")
        total_items_input = st.sidebar.number_input("ក្បាលដីសរុប", min_value=1, value=100)

        if st.sidebar.button("Save & Create Project"):
            project_id, project_name, total_items = create_new_project(new_name, int(total_items_input))
            st.session_state["active_project"] = (project_id, project_name, total_items)
            st.session_state["msg"] = ("success", f"Successfully created/loaded project '{project_name}'!")
            st.rerun()

    if "active_project" in st.session_state:
        project_id, project_name, total_items = st.session_state["active_project"]
    elif projects and project_mode == "Select Existing":
        project_id, project_name, total_items = projects[0][0], projects[0][1], projects[0][2]
        st.session_state["active_project"] = (project_id, project_name, total_items)
    else:
        st.info("Please create or select a project from the sidebar to continue.")
        return

    if "msg" in st.session_state:
        msg_type, msg_text = st.session_state["msg"]
        if msg_type == "success":
            st.success(msg_text)
        elif msg_type == "info":
            st.info(msg_text)
        del st.session_state["msg"]

    st.subheader(f"Active Project: **{project_name}** (ក្បាលដីសរុប: {total_items})")

    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = "Full Inventory"

    df_items = get_project_items(project_id, total_items)

    # Main Layout: Content on Left (Width: 3), Navigation Stacked on Right (Width: 1)
    content_col, nav_col = st.columns([3, 1])

    # Right Column: Stacked Navigation Buttons
    with nav_col:
        st.write("### Navigation")
        if st.button("📋 Full Inventory", use_container_width=True):
            st.session_state["active_tab"] = "Full Inventory"
            st.rerun()
        if st.button("✏️ Update Item", use_container_width=True):
            st.session_state["active_tab"] = "Update Item"
            st.rerun()
        if st.button("⏳ មិនទាន់បានពិនិត្យ", use_container_width=True):
            st.session_state["active_tab"] = "Not Yet Checked"
            st.rerun()
        if st.button("✅ បានពិនិត្យ", use_container_width=True):
            st.session_state["active_tab"] = "Checked Items"
            st.rerun()
        if st.button("📊 Condition Summary", use_container_width=True):
            st.session_state["active_tab"] = "Condition Summary"
            st.rerun()
        if st.button("📜 History Log", use_container_width=True):
            st.session_state["active_tab"] = "History Log"
            st.rerun()

    # Left Column: Tab Views
    with content_col:
        active_tab = st.session_state["active_tab"]

        if active_tab == "Full Inventory":
            st.write("### Complete Inventory List")
            st.dataframe(df_items, use_container_width=True)

        elif active_tab == "Update Item":
            st.write("### Update Item Details")
            with st.form("update_form"):
                code_to_update = st.number_input("ក្បាលដី", min_value=1, max_value=total_items, step=1)

                current_row = df_items[df_items["ក្បាលដី"] == code_to_update].iloc[0] if not df_items.empty else None
                curr_status = current_row["Status"] if current_row is not None else "មិនទាន់បានពិនិត្យ"
                curr_phone = current_row["លេខទូស័ព្ទ"] if current_row is not None else ""
                curr_notes = current_row["ផ្សេងៗ"] if current_row is not None else ""
                
                curr_cond_str = current_row["Condition"] if (current_row is not None and current_row["Condition"] not in ["-", "ធម្មតា"]) else ""
                default_conditions = [c.strip() for c in curr_cond_str.split(", ") if c.strip() in CONDITION_OPTIONS]

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

                submitted = st.form_submit_button("Save Changes")
                if submitted:
                    new_status = "បានពិនិត្យ" if is_checked else "មិនទាន់បានពិនិត្យ"
                    
                    final_notes = "គ្មានទិន្នន័យ" if no_data_checked and not notes_input.strip() else notes_input

                    # Automatically append "គ្មានទិន្នន័យ" to condition if checkbox is checked
                    if no_data_checked and "គ្មានទិន្នន័យ" not in selected_conditions:
                        selected_conditions.append("គ្មានទិន្នន័យ")

                    condition_str = ", ".join(selected_conditions) if selected_conditions else "ធម្មតា"

                    combined_dt = datetime.datetime.combine(selected_date, selected_time)
                    formatted_dt = combined_dt.strftime("%d/%m/%Y, %I:%M %p")

                    update_item_in_db(project_id, code_to_update, new_status, phone_input, final_notes, condition_str, formatted_dt)
                    st.session_state["msg"] = ("success", f"✅ Changes saved & logged for ក្បាលដី #{code_to_update}!")
                    st.rerun()

        elif active_tab == "Not Yet Checked":
            not_checked_df = df_items[df_items["Status"] == "មិនទាន់បានពិនិត្យ"]
            st.write(f"### មិនទាន់បានពិនិត្យ (Total Left: {len(not_checked_df)})")
            st.dataframe(not_checked_df, use_container_width=True)

        elif active_tab == "Checked Items":
            checked_df = df_items[df_items["Status"] == "បានពិនិត្យ"]
            st.write(f"### បានពិនិត្យ (Total Checked: {len(checked_df)})")

            search_code = st.number_input("Search ក្បាលដី in បានពិនិត្យ", min_value=0, max_value=total_items, value=0)
            if search_code > 0:
                filtered_df = checked_df[checked_df["ក្បាលដី"] == search_code]
                st.dataframe(filtered_df, use_container_width=True)
            else:
                st.dataframe(checked_df, use_container_width=True)

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

        elif active_tab == "History Log":
            st.write("### 📜 Activity History Log")
            df_history = get_project_history(project_id)
            if not df_history.empty:
                st.dataframe(df_history, use_container_width=True)
            else:
                st.info("No activity logged for this project yet.")


if __name__ == "__main__":
    main()
