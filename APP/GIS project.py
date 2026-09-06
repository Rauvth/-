import sqlite3
import datetime
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
            status TEXT DEFAULT 'Not Yet Checked',
            updated_at TEXT DEFAULT '',
            customer_phone TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            FOREIGN KEY (project_id) REFERENCES projects (id)
        )
    """)

    # Safely migrate missing columns for existing 'items' table
    cursor.execute("PRAGMA table_info(items)")
    items_columns = [column[1] for column in cursor.fetchall()]
    if "updated_at" not in items_columns:
        cursor.execute("ALTER TABLE items ADD COLUMN updated_at TEXT DEFAULT ''")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            code INTEGER,
            action_type TEXT,
            status TEXT DEFAULT '',
            customer_phone TEXT DEFAULT '',
            notes TEXT DEFAULT '',
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

    conn.commit()
    conn.close()


def log_activity(project_id, code, action_type, status="", phone="", notes="", custom_timestamp=""):
    """Records an action in the database with separate columns and date/time."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    timestamp = custom_timestamp if custom_timestamp else datetime.datetime.now().strftime("%d/%m/%Y, %I:%M %p")

    cursor.execute("""
        INSERT INTO logs (project_id, code, action_type, status, customer_phone, notes, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (project_id, code, action_type, status, phone, notes, timestamp))

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
        log_activity(project_id, None, "Project Created", notes=f"Created project '{name}' with capacity {total_items}")
    except sqlite3.IntegrityError:
        cursor.execute("SELECT id, name, total_items FROM projects WHERE name = ?", (name,))
        row = cursor.fetchone()
        project_id, name, total_items = row[0], row[1], row[2]
    conn.close()
    return project_id, name, total_items


def get_project_items(project_id, total_items):
    """Returns a full DataFrame of items for a given project with Last Updated date."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT code, status, updated_at, customer_phone, notes 
        FROM items 
        WHERE project_id = ? 
        ORDER BY code ASC
    """, (project_id,))

    existing_items = {row[0]: (row[1], row[2], row[3], row[4]) for row in cursor.fetchall()}
    conn.close()

    data = []
    for code in range(1, total_items + 1):
        if code in existing_items:
            status, updated_at, phone, notes = existing_items[code]
        else:
            status, updated_at, phone, notes = "Not Yet Checked", "-", "", ""
        data.append({
            "Code": code,
            "Status": status,
            "Last Updated": updated_at if updated_at else "-",
            "Customer Phone": phone,
            "Notes": notes
        })
    return pd.DataFrame(data)


def update_item_in_db(project_id, code, status, phone, notes, custom_timestamp):
    """Inserts or updates an item's details, date/time, and logs changes."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM items WHERE project_id = ? AND code = ?
    """, (project_id, code))
    item = cursor.fetchone()

    if item:
        cursor.execute("""
            UPDATE items SET status = ?, updated_at = ?, customer_phone = ?, notes = ? 
            WHERE id = ?
        """, (status, custom_timestamp, phone, notes, item[0]))
    else:
        cursor.execute("""
            INSERT INTO items (project_id, code, status, updated_at, customer_phone, notes) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (project_id, code, status, custom_timestamp, phone, notes))

    conn.commit()
    conn.close()

    log_activity(
        project_id=project_id,
        code=code,
        action_type="Item Updated",
        status=status,
        phone=phone,
        notes=notes,
        custom_timestamp=custom_timestamp
    )


def get_project_history(project_id):
    """Fetches all history logs for the active project in separate columns."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, code, action_type, status, customer_phone, notes 
        FROM logs 
        WHERE project_id = ? 
        ORDER BY id DESC
    """, (project_id,))
    logs = cursor.fetchall()
    conn.close()

    data = []
    for log in logs:
        data.append({
            "Date & Time": log[0],
            "Item Code": log[1] if log[1] else "N/A",
            "Action": log[2],
            "Status": log[3] if log[3] else "N/A",
            "Customer Phone": log[4] if log[4] else "N/A",
            "Notes": log[5] if log[5] else "N/A"
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
    st.set_page_config(page_title="Project Manager", layout="wide")
    apply_center_alignment()

    if not check_password():
        return

    initialize_database()

    # Top Header & Logout
    head_col1, head_col2 = st.columns([8, 2])
    with head_col1:
        st.title("📦 Store Project Manager")
    with head_col2:
        if st.button("Logout"):
            st.session_state["authenticated"] = False
            st.rerun()

    # Sidebar: Project Settings
    st.sidebar.header("Project Settings")
    projects = get_all_projects()

    project_mode = st.sidebar.radio("Project Mode", ["Select Existing", "Create New"])

    if project_mode == "Select Existing" and projects:
        project_options = {f"{p[1]} (Capacity: {p[2]})": p for p in projects}
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
        total_items_input = st.sidebar.number_input("Total Item Limit", min_value=1, value=100)

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

    st.subheader(f"Active Project: **{project_name}** (Capacity: {total_items})")

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
        if st.button("⏳ Not Yet Checked", use_container_width=True):
            st.session_state["active_tab"] = "Not Yet Checked"
            st.rerun()
        if st.button("✅ Checked Items", use_container_width=True):
            st.session_state["active_tab"] = "Checked Items"
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
                code_to_update = st.number_input("Item Code", min_value=1, max_value=total_items, step=1)

                current_row = df_items[df_items["Code"] == code_to_update].iloc[0] if not df_items.empty else None
                curr_status = current_row["Status"] if current_row is not None else "Not Yet Checked"
                curr_phone = current_row["Customer Phone"] if current_row is not None else ""
                curr_notes = current_row["Notes"] if current_row is not None else ""

                is_checked = st.checkbox("Mark as Checked", value=(curr_status == "Checked"))
                phone_input = st.text_input("Customer Phone", value=curr_phone)
                notes_input = st.text_area("Notes", value=curr_notes)

                st.write("---")
                st.write("#### Edit Date & Time")
                date_col, time_col = st.columns(2)
                with date_col:
                    selected_date = st.date_input("Update Date", value=datetime.datetime.now().date())
                with time_col:
                    selected_time = st.time_input("Update Time", value=datetime.datetime.now().time())

                submitted = st.form_submit_button("Save Changes")
                if submitted:
                    new_status = "Checked" if is_checked else "Not Yet Checked"

                    combined_dt = datetime.datetime.combine(selected_date, selected_time)
                    formatted_dt = combined_dt.strftime("%d/%m/%Y, %I:%M %p")

                    update_item_in_db(project_id, code_to_update, new_status, phone_input, notes_input, formatted_dt)
                    st.session_state["msg"] = ("success", f"✅ Changes saved & logged for Item Code #{code_to_update}!")
                    st.rerun()

        elif active_tab == "Not Yet Checked":
            not_checked_df = df_items[df_items["Status"] == "Not Yet Checked"]
            st.write(f"### Not Yet Checked (Total Left: {len(not_checked_df)})")
            st.dataframe(not_checked_df, use_container_width=True)

        elif active_tab == "Checked Items":
            checked_df = df_items[df_items["Status"] == "Checked"]
            st.write(f"### Checked Items (Total Checked: {len(checked_df)})")

            search_code = st.number_input("Search Code in Checked Items", min_value=0, max_value=total_items, value=0)
            if search_code > 0:
                filtered_df = checked_df[checked_df["Code"] == search_code]
                st.dataframe(filtered_df, use_container_width=True)
            else:
                st.dataframe(checked_df, use_container_width=True)

        elif active_tab == "History Log":
            st.write("### 📜 Activity History Log")
            df_history = get_project_history(project_id)
            if not df_history.empty:
                st.dataframe(df_history, use_container_width=True)
            else:
                st.info("No activity logged for this project yet.")


if __name__ == "__main__":
    main()