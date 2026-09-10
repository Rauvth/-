import streamlit as st
import sqlite3
import pytz
from datetime import datetime

# --- CONFIGURATION & STYLING ---
st.set_page_config(
    page_title="GIS Project Manager",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Set Timezone
TIMEZONE = pytz.timezone("Asia/Phnom_Penh")

def get_now_str():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

# Custom CSS for Dark Modern Theme
st.markdown("""
<style>
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
</style>
""", unsafe_allow_html=True)


# --- DATABASE INITIALIZATION ---
DB_FILE = "project_manager.db"

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        status TEXT NOT NULL DEFAULT 'pending',
        temp_admin_expiry TEXT
    )
    """)
    
    # App Settings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    
    # Projects Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        total_items INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    
    # Items (Plots) Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        project_id INTEGER,
        item_number INTEGER,
        checked INTEGER DEFAULT 0,
        tags TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        updated_at TEXT,
        PRIMARY KEY (project_id, item_number)
    )
    """)
    
    # Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        username TEXT,
        action TEXT,
        details TEXT,
        timestamp TEXT
    )
    """)
    
    # Default Admin User
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, role, status) VALUES (?, ?, ?, ?)",
            ("admin", "admin123", "admin", "approved")
        )
        
    conn.commit()
    conn.close()

init_db()


# --- DATABASE HELPER FUNCTIONS ---
def get_app_title():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM app_settings WHERE key = 'app_title'")
    row = c.fetchone()
    conn.close()
    return row["value"] if row else "🗺️ Hệ thống quản lý GIS"

def update_app_title(new_title):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('app_title', ?)", (new_title,))
    conn.commit()
    conn.close()

def get_all_projects():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, total_items FROM projects ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def create_new_project(name, total_items):
    conn = get_db()
    c = conn.cursor()
    now = get_now_str()
    c.execute("INSERT INTO projects (name, total_items, created_at) VALUES (?, ?, ?)", (name, total_items, now))
    project_id = c.lastrowid
    
    # Seed items for project
    items_data = [(project_id, i, 0, "", "", now) for i in range(1, total_items + 1)]
    c.executemany("INSERT INTO items (project_id, item_number, checked, tags, notes, updated_at) VALUES (?, ?, ?, ?, ?, ?)", items_data)
    
    conn.commit()
    conn.close()
    return project_id, name, total_items

def get_project_items(project_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT item_number, checked, tags, notes FROM items WHERE project_id = ? ORDER BY item_number ASC", (project_id,))
    rows = c.fetchall()
    conn.close()
    return rows


# --- MAIN APPLICATION ---
def main():
    # Session state authentication init
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    # --- LOGIN SCREEN ---
    if not st.session_state["authenticated"]:
        st.title("🔐 ចូលប្រើប្រាស់ប្រព័ន្ធ (Login)")
        col1, col2 = st.columns([1, 1])
        with col1:
            username = st.text_input("ឈ្មោះគណនី (Username)")
            password = st.text_input("ពាក្យសម្ងាត់ (Password)", type="password")
            if st.button("ចូលប្រព័ន្ធ", use_container_width=True):
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT username, password, role, status FROM users WHERE username = ?", (username,))
                user = c.fetchone()
                conn.close()
                
                if user and user["password"] == password:
                    if user["status"] == "approved":
                        st.session_state["authenticated"] = True
                        st.session_state["username"] = user["username"]
                        st.session_state["role"] = user["role"]
                        st.rerun()
                    else:
                        st.error("គណនីរបស់អ្នកមិនទាន់បានទទួលការអនុញ្ញាត (Pending Approval)!")
                else:
                    st.error("ឈ្មោះគណនី ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវ!")
        return

    # --- APP NAVIGATION & TOP BAR ---
    projects = get_all_projects()

    p_col1, p_col2, p_col3 = st.columns([3, 2, 1])
    with p_col1:
        app_title = get_app_title()
        st.markdown(f"<h2 style='margin:0; font-size: 1.5rem; color:#F8FAFC;'>{app_title}</h2>", unsafe_allow_html=True)
        
    with p_col2:
        if projects:
            proj_dict = {f"{p['name']} (ក្បាលដី: {p['total_items']})": p for p in projects}
            selected_proj_label = st.selectbox("ជ្រើសរើសគម្រោង", list(proj_dict.keys()), label_visibility="collapsed")
            active_p = proj_dict[selected_proj_label]
            st.session_state["active_project"] = (active_p["id"], active_p["name"], active_p["total_items"])
            
    with p_col3:
        if st.button("🚪 ចាកចេញ", use_container_width=True):
            st.session_state["authenticated"] = False
            st.session_state.pop("active_project", None)
            st.rerun()

    st.divider()

    # --- FALLBACK WHEN NO PROJECTS EXIST ---
    if "active_project" not in st.session_state or not projects:
        st.warning("⚠️ មិនទាន់មានគម្រោងនៅក្នុងប្រព័ន្ធទេ។ សូមបង្កើតគម្រោងដំបូងរបស់អ្នកខាងក្រោម៖")
        with st.form("first_project_creation_form"):
            st.subheader("➕ បង្កើតគម្រោងដំបូង")
            init_p_name = st.text_input("ឈ្មោះគម្រោង", value="គម្រោងទី១")
            init_p_items = st.number_input("ចំនួនក្បាលដីសរុប", min_value=1, value=100)
            submit_init_p = st.form_submit_button("បង្កើតគម្រោង", use_container_width=True)
            
            if submit_init_p:
                if init_p_name.strip():
                    pid, pname, pitems = create_new_project(init_p_name.strip(), int(init_p_items))
                    st.session_state["active_project"] = (pid, pname, pitems)
                    st.success(f"បានបង្កើតគម្រោង {pname} ជោគជ័យ!")
                    st.rerun()
                else:
                    st.error("សូមបញ្ចូលឈ្មោះគម្រោង!")
        return

    # --- MAIN PROJECT DASHBOARD ---
    project_id, project_name, total_items = st.session_state["active_project"]
    items = get_project_items(project_id)
    
    # Metrics calculations
    checked_count = sum(1 for item in items if item["checked"] == 1)
    unchecked_count = total_items - checked_count
    
    m1, m2, m3 = st.columns(3)
    m1.metric("ក្បាលដីសរុប", total_items)
    m2.metric("បានពិនិត្យរួច", checked_count)
    m3.metric("នៅសល់", unchecked_count)

    st.subheader(f"ទិន្នន័យគម្រោង៖ {project_name}")
    
    # Sidebar: Admin Panel & Project Creation
    with st.sidebar:
        st.write(f"👤 គណនី: **{st.session_state['username']}** ({st.session_state['role']})")
        st.divider()
        st.subheader("➕ បង្កើតគម្រោងថ្មី")
        with st.form("new_project_sidebar_form"):
            new_p_name = st.text_input("ឈ្មោះគម្រោងថ្មី")
            new_p_items = st.number_input("ចំនួនក្បាលដី", min_value=1, value=100)
            if st.form_submit_button("បង្កើត"):
                if new_p_name.strip():
                    pid, pname, pitems = create_new_project(new_p_name.strip(), int(new_p_items))
                    st.session_state["active_project"] = (pid, pname, pitems)
                    st.success("បានបង្កើតជោគជ័យ!")
                    st.rerun()
                else:
                    st.error("សូមបញ្ចូលឈ្មោះ!")

if __name__ == "__main__":
    main()
()
