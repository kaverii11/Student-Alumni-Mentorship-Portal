import streamlit as st
import mysql.connector
from mysql.connector import Error
import pandas as pd
from datetime import datetime
import random
import string

def generate_meeting_id():
    """Generates a mock meeting link"""
    code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"https://meet.example.com/{code[:4]}-{code[4:8]}-{code[8:]}"

# Page configuration
st.set_page_config(
    page_title="Student-Alumni Mentorship Portal",
    page_icon="🎓",
    layout="wide"
)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'AlumniMentorshipDB',  
    'user': 'root',  
    'password': '12345',  
}

def get_db_connection():
    """Create and return a database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        st.error(f"Error connecting to MySQL: {e}")
        return None

def execute_query(query, params=None, fetch=True):
    """Execute a SQL query and return results"""
    connection = get_db_connection()
    if connection is None:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params)
        
        if fetch:
            result = cursor.fetchall()
        else:
            connection.commit()
            result = cursor.rowcount
        
        cursor.close()
        connection.close()
        return result
    except Error as e:
        # Avoid showing duplicate errors if register_user handles it
        if "Duplicate entry" not in str(e):
            st.error(f"Database error: {e}")
        if connection:
            connection.close()
        return None

# In app1.py, replace the current login_user function entirely:

def login_user(email, password, role):
    """Authenticate user login, explicitly handling empty string passwords for existing users."""
    table_name = ""
    id_column = ""

    # Determine table and columns
    if role == 'Student':
        table_name = "Student"
        id_column = "Student_ID"
        email_column = "College_Email"
        # Query checks for: 1. Password matches OR 2. DB password is blank AND user provided blank password
        # Note: We must check for both NULL and '' since the user's DB has NOT NULL but existing records are ''
        query = f"SELECT {id_column} as user_id, Name FROM {table_name} WHERE {email_column} = %s AND (Password = %s OR Password = '')"
    elif role == 'Alumni':
        table_name = "Alumni"
        id_column = "Alumni_ID"
        email_column = "Email"
        query = f"SELECT {id_column} as user_id, Name FROM {table_name} WHERE {email_column} = %s AND (Password = %s OR Password = '') AND Approved = TRUE"
    elif role == 'Administrator':  # Admin login with simple password
        table_name = "Admin"
        id_column = "Admin_ID"
        email_column = "Email"
        # Admin must always use a password
        query = f"SELECT {id_column} as user_id, Name FROM {table_name} WHERE {email_column} = %s AND Password = %s"
    else:
        return None

    # For Student/Alumni, we pass the user input password once.
    if role in ['Student', 'Alumni']:
        result = execute_query(query, (email, password))
    
    # For Admin, we pass it twice for the specific admin query
    elif role == 'Administrator':
        result = execute_query(query, (email, password))
        
    # Handle Admin fallback (existing logic)
    if role == 'Administrator' and password == 'admin':
        if not result or len(result) == 0:
            return {'user_id': 1, 'Name': 'Administrator'}

    # Check for pending alumni approval
    if role == 'Alumni' and (not result or len(result) == 0):
        pending_query = f"SELECT {id_column} FROM {table_name} WHERE {email_column} = %s AND (Password = %s OR Password = '') AND Approved = FALSE"
        pending_result = execute_query(pending_query, (email, password))
        if pending_result and len(pending_result) > 0:
            st.error("Login failed: Your account is pending administrator approval.")
            return None
            
    if result and len(result) > 0:
        return result[0]
    
    return None

def register_user(email, password, name, role, **kwargs):
    """Register a new user"""
    try:
        connection = get_db_connection()
        if connection is None:
            return False
        
        cursor = connection.cursor()
        
        if role == 'Student':
            # Assumes Student table has: Name, College_Email, Password, Semester, Department, PhoneNumber
            query = """
            INSERT INTO Student (Name, College_Email, Password, Semester, Department, PhoneNumber) 
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            values = (name, email, password, kwargs.get('semester'), 
                     kwargs.get('department'), kwargs.get('phone_number'))
        else:  # Alumni
            # Assumes Alumni table has: Name, Email, Password, Graduating_Year, Industry_ID, PhoneNumber, Current_Designation, years_of_experience, Approved
            query = """
            INSERT INTO Alumni (Name, Email, Password, Graduating_Year, Industry_ID, PhoneNumber, Current_Designation, years_of_experience, Approved) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (name, email, password, kwargs.get('graduating_year'), 
                     kwargs.get('industry_id'), kwargs.get('phone_number'),
                     kwargs.get('current_designation'), kwargs.get('years_of_experience'), False) # Not approved by default
        
        cursor.execute(query, values)
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Error as e:
        if e.errno == 1062: # Duplicate entry
            st.error(f"Registration error: An account with the email '{email}' already exists.")
        else:
            st.error(f"Registration error: {e}")
        return False

def get_student_sessions(student_id):
    """Call the updated GetStudentMentorshipDetails procedure"""
    query = "CALL proc_GetStudentMentorshipDetails(%s)"  # Calling procedure: proc_GetStudentMentorshipDetails
    return execute_query(query, (student_id,))

def get_alumni_rating(alumni_id):
    """Call the GetAlumniAverageRating function"""
    # Assuming function exists: fn_CalculateAlumniRating(alumni_id)
    query = "SELECT fn_CalculateAlumniRating(%s) as rating"  # Calling function: fn_CalculateAlumniRating
    result = execute_query(query, (alumni_id,))
    if result and len(result) > 0 and result[0]['rating'] is not None:
        return result[0]['rating']
    return 0.0 # Return 0.0 if no ratings yet

def get_industries():
    """Get all industries"""
    query = "SELECT Industry_ID, Name FROM Industry ORDER BY Name"
    return execute_query(query)

def get_alumni_with_industry(filters=None):
    """Get alumni with industry information and skills"""
    query = """
    SELECT DISTINCT a.Alumni_ID, a.Name, a.Current_Designation, a.years_of_experience,
           i.Name as Industry_Name 
    FROM Alumni a 
    LEFT JOIN Industry i ON a.Industry_ID = i.Industry_ID 
    LEFT JOIN Alumni_Skills als ON a.Alumni_ID = als.Alumni_ID
    LEFT JOIN Skills s ON als.Skill_ID = s.Skill_ID
    WHERE a.Approved = TRUE
    """
    params = []
    
    if filters:
        if 'name' in filters and filters['name']:
            query += " AND a.Name LIKE %s"
            params.append(f"%{filters['name']}%")
        
        if 'industry_id' in filters and filters['industry_id']:
            query += " AND a.Industry_ID = %s"
            params.append(filters['industry_id'])
        
        if 'skill' in filters and filters['skill']:
            # Assumes Skills table has Skill_Name
            query += " AND s.Skill_Name LIKE %s"
            params.append(f"%{filters['skill']}%")
    
    return execute_query(query, tuple(params) if params else None)

def get_skills():
    """Get all distinct skills"""
    # Assumes Skills table has Skill_Name
    query = "SELECT DISTINCT Skill_Name FROM Skills ORDER BY Skill_Name"
    result = execute_query(query)
    if result:
        return [row['Skill_Name'] for row in result]
    return []

def get_alumni_info(alumni_id):
    """Get alumni information"""
    query = """
    SELECT a.*, i.Name as Industry_Name 
    FROM Alumni a 
    LEFT JOIN Industry i ON a.Industry_ID = i.Industry_ID 
    WHERE a.Alumni_ID = %s
    """
    result = execute_query(query, (alumni_id,))
    return result[0] if result else None

def get_alumni_skills(alumni_id):
    """Get skills for an alumni"""
    query = """
    SELECT s.Skill_Name 
    FROM Alumni_Skills als
    JOIN Skills s ON als.Skill_ID = s.Skill_ID
    WHERE als.Alumni_ID = %s
    """
    result = execute_query(query, (alumni_id,))
    return [row['Skill_Name'] for row in result] if result else []

def get_alumni_achievements(alumni_id):
    """Get achievements for an alumni"""
    try:
        query = "SELECT * FROM Achievements WHERE Alumni_ID = %s"
        return execute_query(query, (alumni_id,))
    except Error as e:
        if e.errno == 1146:  # Table doesn't exist
            st.warning("Achievements table is missing. Please contact the administrator.")
            return []
        else:
            st.error(f"Error fetching achievements: {e}")
            return []

def update_alumni_profile(alumni_id, **kwargs):
    """Update alumni profile information"""
    connection = get_db_connection()
    if connection is None:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Update Alumni table
        update_fields = []
        update_values = []
        
        if 'name' in kwargs:
            update_fields.append("Name = %s")
            update_values.append(kwargs['name'])
        if 'email' in kwargs:
            update_fields.append("Email = %s")
            update_values.append(kwargs['email'])
        if 'phone_number' in kwargs:
            update_fields.append("PhoneNumber = %s")
            update_values.append(kwargs['phone_number'])
        if 'current_designation' in kwargs:
            update_fields.append("Current_Designation = %s")
            update_values.append(kwargs['current_designation'])
        if 'years_of_experience' in kwargs:
            update_fields.append("years_of_experience = %s")
            update_values.append(kwargs['years_of_experience'])
        if 'industry_id' in kwargs:
            update_fields.append("Industry_ID = %s")
            update_values.append(kwargs['industry_id'])
        
        if update_fields:
            update_values.append(alumni_id)
            query = f"UPDATE Alumni SET {', '.join(update_fields)} WHERE Alumni_ID = %s"
            cursor.execute(query, tuple(update_values))
        
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Error as e:
        st.error(f"Error updating profile: {e}")
        if connection:
            connection.close()
        return False

def update_alumni_skills(alumni_id, skills):
    """Update alumni skills"""
    connection = get_db_connection()
    if connection is None:
        return False
    
    try:
        cursor = connection.cursor(dictionary=True)  # Ensure rows are returned as dictionaries
        
        # Delete existing skills
        cursor.execute("DELETE FROM Alumni_Skills WHERE Alumni_ID = %s", (alumni_id,))
        
        # Get Skill_IDs for skill names
        if skills:
            format_strings = ','.join(['%s'] * len(skills))
            cursor.execute(f"SELECT Skill_ID, Skill_Name FROM Skills WHERE Skill_Name IN ({format_strings})", tuple(skills))
            skill_map = {row['Skill_Name']: row['Skill_ID'] for row in cursor.fetchall()}
            
            # Insert new skills
            for skill_name in skills:
                if skill_name in skill_map:
                    cursor.execute(
                        "INSERT INTO Alumni_Skills (Alumni_ID, Skill_ID) VALUES (%s, %s)",
                        (alumni_id, skill_map[skill_name])
                    )
        
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Error as e:
        st.error(f"Error updating skills: {e}")
        if connection:
            connection.close()
        return False

def get_student_info(student_id):
    """Get student information"""
    query = "SELECT * FROM Student WHERE Student_ID = %s"
    result = execute_query(query, (student_id,))
    return result[0] if result else None

def submit_feedback(student_id, alumni_id, rating, comments):
    """Submit feedback"""
    query = """
    INSERT INTO Feedback (Student_ID, Alumni_ID, Rating, Comments, Date) 
    VALUES (%s, %s, %s, %s, %s)
    """
    return execute_query(query, (student_id, alumni_id, rating, comments, datetime.now().date()), fetch=False)

def get_student_feedback(student_id):
    """Get student's past sessions"""
    query = """
    SELECT DISTINCT a.Alumni_ID, a.Name 
    FROM Mentorship_Session ms 
    JOIN Alumni a ON ms.Alumni_ID = a.Alumni_ID 
    WHERE ms.Student_ID = %s
    """
    return execute_query(query, (student_id,))

def get_alumni_feedback(alumni_id):
    """Get feedback received by an alumni"""
    query = """
    SELECT f.Rating, f.Comments, f.Date, s.Name as Student_Name 
    FROM Feedback f 
    JOIN Student s ON f.Student_ID = s.Student_ID 
    WHERE f.Alumni_ID = %s 
    ORDER BY f.Date DESC
    """
    return execute_query(query, (alumni_id,))

def get_site_statistics():
    """Get overall site statistics"""
    stats = {}
    
    queries = {
        'total_students': "SELECT COUNT(*) as count FROM Student",
        'total_alumni': "SELECT COUNT(*) as count FROM Alumni WHERE Approved = TRUE",
        'total_placements': "SELECT COUNT(*) as count FROM Placement WHERE Is_Placed = TRUE"
    }
    
    for key, query in queries.items():
        result = execute_query(query)
        stats[key] = result[0]['count'] if result else 0
    
    return stats

def get_placement_trends():
    """Get placement trends for charts"""
    query = """
    SELECT DATE(Placement_Date) as date, COUNT(*) as count 
    FROM Placement 
    WHERE Is_Placed = TRUE 
    GROUP BY DATE(Placement_Date) 
    ORDER BY date
    """
    return execute_query(query)

def get_placement_log():
    """Get placement log entries"""
    # Assumes Placement_Log table has Log_Timestamp
    query = "SELECT * FROM Placement_Log ORDER BY Log_Timestamp DESC"
    return execute_query(query)

def get_pending_alumni():
    """Get alumni pending approval"""
    query = """
    SELECT a.Alumni_ID, a.Name, a.Email, a.Graduating_Year, i.Name as Industry_Name, a.Approved 
    FROM Alumni a 
    LEFT JOIN Industry i ON a.Industry_ID = i.Industry_ID 
    WHERE a.Approved = FALSE
    """
    return execute_query(query)

def approve_alumni(alumni_id):
    """Approve an alumni"""
    query = "UPDATE Alumni SET Approved = TRUE WHERE Alumni_ID = %s"
    return execute_query(query, (alumni_id,), fetch=False)

def get_placement_status(student_id):
    """Get student placement status"""
    query = "SELECT * FROM Placement WHERE Student_ID = %s"
    result = execute_query(query, (student_id,))
    return result[0] if result else None
    
def update_placement(student_id, is_placed, company_name, placement_date):
    """Update student placement status"""
    # Check if placement record exists
    check_query = "SELECT * FROM Placement WHERE Student_ID = %s"
    existing = execute_query(check_query, (student_id,))

    connection = get_db_connection()
    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        if existing and len(existing) > 0:
            # Update existing - This may trigger the placement_log trigger
            query = """
            UPDATE Placement
            SET Is_Placed = %s, Company_Name = %s, Placement_Date = %s
            WHERE Student_ID = %s
            """  # This UPDATE may trigger: placement_log trigger
            cursor.execute(query, (is_placed, company_name, placement_date, student_id))
        else:
            # Insert new
            query = """
            INSERT INTO Placement (Student_ID, Is_Placed, Company_Name, Placement_Date)
            VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (student_id, is_placed, company_name, placement_date))

        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Error as e:
        st.error(f"Error updating placement: {e}")
        if connection:
            connection.close()
        return False

# Main App
def main():
    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['role'] = None
        st.session_state['user_id'] = None
        st.session_state['name'] = None
    
    # Navigation
    if not st.session_state['logged_in']:
        show_login_page()
    else:
        show_main_app()

# ==================================================================
# ==================  FIXED LOGIN/REGISTER PAGE  ===================
# ==================================================================

def show_login_page():
    """Display login/register page"""
    st.title("🎓 Student-Alumni Mentorship Portal")
    
    # Apply custom dark theme CSS to match screenshot
    st.markdown("""
    <style>
    /* Target the main app container */
    .stApp {
        background-color: #1a1a1a;
        color: #ffffff;
    }
    /* Target Streamlit's containers/tabs */
    [data-baseweb="tab-list"] {
        background-color: #262626;
    }
    [data-baseweb="tab"] {
        background-color: #262626;
        color: #aaaaaa;
    }
    [data-baseweb="tab"][aria-selected="true"] {
        color: #ffffff;
        border-bottom-color: #007bff; /* Blue underline for active tab */
    }
    /* Target form background */
    .stForm {
        background-color: #262626;
        border-radius: 8px;
        padding: 20px;
    }
    /* Style input labels */
    .st-emotion-cache-16txtl3 {
        color: #ffffff !important;
    }
    /* Style input boxes */
    .stTextInput input, .stNumberInput input {
        background-color: #333333;
        color: #ffffff;
        border-radius: 6px;
        border: 1px solid #555555;
    }
    /* Style radio buttons */
    .stRadio label {
        color: #ffffff;
    }
    </style>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            role = st.radio("Login as", ["Student", "Alumni", "Administrator"])
            
            submit_button = st.form_submit_button("Login")
            
            if submit_button:
                if email and password:
                    user = login_user(email, password, role)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['role'] = role
                        st.session_state['user_id'] = user['user_id']
                        st.session_state['name'] = user['Name']
                        st.success("Login successful!")
                        st.rerun()
                    # Error messages (Invalid credentials, Pending approval) are now handled inside login_user()
                else:
                    st.error("Please fill in all fields")
    
    with tab2:
        st.subheader("Register")
        
        # --- FIX: MOVE ROLE SELECTION OUTSIDE THE FORM ---
        # This allows the page to rerun and display the correct fields
        # when the radio button is changed.
        user_role = st.radio("I am a...", ["Student", "Alumni"], key="register_role_select")

        with st.form("register_form"):
            
            # --- COMMON FIELDS ---
            st.info(f"Please fill in the details for a new {user_role}.")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            name = st.text_input("Full Name")
            phone_number = st.text_input("Phone Number") # <-- COMMON FIELD
            
            # The user_role radio button was here, but has been moved up.
            
            # --- ROLE-SPECIFIC FIELDS ---
            if user_role == 'Student':
                st.write("--- Student Details ---")
                semester = st.number_input("Semester", min_value=1, max_value=10, step=1)
                department = st.text_input("Department")
                # phone_number was removed from here
            
            else:  # Alumni
                st.write("--- Alumni Details ---")
                graduating_year = st.number_input("Graduating Year", min_value=1980, max_value=datetime.now().year, step=1)
                current_designation = st.text_input("Current Designation")
                years_of_experience = st.number_input("Years of Experience", min_value=0, step=1)
                
                industries = get_industries()
                industry_id = None # Default
                if industries:
                    industry_options = {ind['Name']: ind['Industry_ID'] for ind in industries}
                    # Add a placeholder
                    industry_options_list = ["--- Select an Industry ---"] + list(industry_options.keys())
                    selected_industry = st.selectbox("Industry", industry_options_list)
                    if selected_industry != "--- Select an Industry ---":
                        industry_id = industry_options[selected_industry]
                else:
                    st.warning("Could not load industries. Please contact admin.")
            
            submit_button = st.form_submit_button("Register")
            
            if submit_button:
                # --- NEW VALIDATION LOGIC ---
                success = False
                
                # 1. Validate common fields
                if not email or not password or not name or not phone_number:
                    st.error("Please fill in all common fields: Email, Password, Name, and Phone Number.")
                else:
                    # 2. Validate role-specific fields and register
                    if user_role == 'Student':
                        if not department:
                            st.error("Please provide your Department.")
                        else:
                            success = register_user(email, password, name, user_role, 
                                                   semester=semester, department=department, 
                                                   phone_number=phone_number)
                    
                    else:  # Alumni
                        if not current_designation or not industry_id:
                            st.error("Please provide your Current Designation and select an Industry.")
                        else:
                            success = register_user(email, password, name, user_role, 
                                                   graduating_year=graduating_year, industry_id=industry_id,
                                                   phone_number=phone_number, current_designation=current_designation,
                                                   years_of_experience=years_of_experience)
                    
                    # 3. Handle success/failure
                    if success:
                        if user_role == 'Student':
                            st.success("Registration successful! Please login.")
                        else:
                            st.success("Registration successful! Please wait for admin approval before logging in.")
                    # else:
                        # Error is now handled inside register_user()

# ==================================================================
# ================== END OF FIXED SECTION ==========================
# ==================================================================


def show_main_app():
    """Show main application based on user role"""
    # Sidebar navigation
    with st.sidebar:
        st.title("Navigation")
        st.info(f"Logged in as {st.session_state['role']}: {st.session_state['name']}")

        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.session_state['role'] = None
            st.session_state['user_id'] = None
            st.session_state['name'] = None
            st.rerun()

    # Top navigation with enhanced styling
    st.markdown("""
    <div style='text-align: center; margin: 30px 0 40px 0;'>
        <div style='display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;'>
    """, unsafe_allow_html=True)

    if st.session_state['role'] == 'Administrator':
        # Admin navigation
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            if st.button("📊 Analytics Dashboard", use_container_width=True):
                st.session_state['page'] = "Analytics Dashboard"
        with col2:
            if st.button("📋 Placement Log", use_container_width=True):
                st.session_state['page'] = "Placement Log"
        with col3:
            if st.button("👥 User Management", use_container_width=True):
                st.session_state['page'] = "User Management"
    else:
        # Student/Alumni navigation
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            if st.button("🏠 My Dashboard", use_container_width=True):
                st.session_state['page'] = "My Dashboard"
        with col2:
            # Changed label for student to point towards the main goal (Find a Mentor)
            if st.button("📅 Find a Mentor / Sessions", use_container_width=True):
                # Students should land on a page that lets them search/request, or manage sessions
                if st.session_state['role'] == 'Student':
                     st.session_state['page'] = "Find a Mentor / Sessions" 
                else: # Alumni
                    st.session_state['page'] = "Requests & Sessions" 
        with col3:
            if st.button("✏️ Edit Profile", use_container_width=True):
                st.session_state['page'] = "Edit Profile"

    st.markdown("</div>", unsafe_allow_html=True)

    # Display selected page
    page = st.session_state.get('page', None)
    if st.session_state['role'] == 'Student':
        if page == "My Dashboard" or page is None: # Default to dashboard
            home_page()
        elif page == "Find a Mentor / Sessions":
            # Direct the student to the most useful page first
            st.session_state['sub_page'] = "Find a Mentor" # Set sub-page for this new page
            st.title("🤝 Mentorship Hub")
            tab_mentor, tab_sessions = st.tabs(["🔎 Find a Mentor", "📅 My Requests & Sessions"])
            with tab_mentor:
                find_a_mentor()
            with tab_sessions:
                my_sessions_page()
        elif page == "Edit Profile":
            my_profile_page()

    elif st.session_state['role'] == 'Alumni':
        if page == "My Dashboard" or page is None: # Default to dashboard
            alumni_dashboard()
        elif page == "Requests & Sessions":
            requests_and_sessions_page()
        elif page == "Edit Profile":
            edit_profile()

    else:  # Admin
        if page == "Analytics Dashboard" or page is None: # Default to dashboard
            analytics_dashboard()
        elif page == "Placement Log":
            placement_log_page()
        elif page == "User Management":
            user_management()

# Add a section for storing session content

def store_session_content(session_id, content):
    """Store content for a session"""
    query = "UPDATE Mentorship_Session SET Content = %s WHERE Session_ID = %s"
    return execute_query(query, (content, session_id), fetch=False)

def view_session_content(session_id):
    """View content for a session"""
    query = "SELECT Content FROM Mentorship_Session WHERE Session_ID = %s"
    result = execute_query(query, (session_id,))
    return result[0]['Content'] if result else None

def student_dashboard():
    """Student Dashboard Page"""
    # This function is deprecated in favor of home_page()
    pass


# ===================== NEW STUDENT PAGES =====================

def get_student_stats(student_id):
    """Return total completed sessions and pending requests counts"""
    completed_q = "SELECT COUNT(*) AS cnt FROM Mentorship_Session WHERE Student_ID = %s AND Status = 'Completed'"
    pending_q = "SELECT COUNT(*) AS cnt FROM Mentorship_Request WHERE Student_ID = %s AND Status = 'Pending'"
    completed = execute_query(completed_q, (student_id,))
    pending = execute_query(pending_q, (student_id,))
    return (
        (completed[0]['cnt'] if completed else 0),
        (pending[0]['cnt'] if pending else 0)
    )

def home_page():
    """Student Home landing page with stats and placement form"""
    st.markdown(f"<h1 style='text-align: center; color: #00d4ff; margin-bottom: 30px;'>Welcome, {st.session_state['name']}!</h1>", unsafe_allow_html=True)

    # Stats cards with better layout
    total_completed, pending_requests = get_student_stats(st.session_state['user_id'])
    st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>📊 Your Statistics</h2>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Sessions Completed", total_completed)
    with col2:
        # CORRECTED: This metric should reflect requests *sent* by the student, which is what the query is for.
        st.metric("Pending Sent Requests", pending_requests) 
    with col3:
        st.metric("Profile Completion", "85%")  # Placeholder

    st.markdown("<hr style='border: 1px solid #00d4ff; margin: 40px 0;'>", unsafe_allow_html=True)

    # Available Alumni Mentors Section
    st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>🎓 Available Alumni Mentors (Quick Request)</h2>", unsafe_allow_html=True)
    st.info("💡 For a detailed search with skills and industry filters, use the 'Find a Mentor / Sessions' tab.")

    # Get all approved alumni with their info
    mentors = get_alumni_with_industry({})  # Get all mentors without filters

    if mentors:
        # Remove duplicates (from JOIN)
        seen = set()
        unique_mentors = []
        for mentor in mentors:
            mentor_id = mentor['Alumni_ID']
            if mentor_id not in seen:
                seen.add(mentor_id)
                unique_mentors.append(mentor)

        st.markdown(f"<p style='color: #00d4ff; margin-bottom: 15px;'>Found {len(unique_mentors)} available mentors</p>", unsafe_allow_html=True)

        # Display mentors in a grid
        for i in range(0, len(unique_mentors), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                if i + j < len(unique_mentors):
                    mentor = unique_mentors[i + j]
                    with col:
                        with st.container(border=True):
                            st.markdown(f"<h4 style='color: #00d4ff; margin-bottom: 10px;'>👤 {mentor['Name']}</h4>", unsafe_allow_html=True)
                            st.write(f"💼 Designation: {mentor.get('Current_Designation', 'N/A')}")
                            st.write(f"🏢 Industry: {mentor.get('Industry_Name', 'N/A')}")
                            if mentor.get('years_of_experience') is not None:
                                st.write(f"📈 Experience: {mentor['years_of_experience']} years")

                            # Get rating
                            rating = get_alumni_rating(mentor['Alumni_ID'])
                            st.metric(label="⭐ Average Rating", value=f"{rating:.1f} / 5.0")
                            
                            # --- FIXED: Quick request button with default message ---
                            if st.button(f"📨 Quick Request Mentorship", key=f"quick_request_{mentor['Alumni_ID']}", use_container_width=True):
                                default_msg = f"Hi {mentor['Name']}, I am interested in mentorship with you. Please consider my request."
                                if create_mentorship_request(st.session_state['user_id'], mentor['Alumni_ID'], default_msg):
                                    st.success(f"✅ Quick request sent to {mentor['Name']}! You can track it in 'Find a Mentor / Sessions'.")
                                    st.rerun() # Rerun to update the dashboard stats and button state
                                else:
                                    st.error("❌ Failed to send request. You may have a pending one already.")
                                    # st.rerun() # Rerun to clear the button press state

    else:
        st.info("📭 No mentors available at the moment.")

    st.markdown("<hr style='border: 1px solid #00d4ff; margin: 40px 0;'>", unsafe_allow_html=True)

    st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>💼 My Placement Status</h2>", unsafe_allow_html=True)

    # Enhanced placement form with better styling
    current_placement = get_placement_status(st.session_state['user_id'])
    default_placed = current_placement.get('Is_Placed', False) if current_placement else False
    default_company = current_placement.get('Company_Name', '') if current_placement else ''
    default_date = current_placement.get('Placement_Date', datetime.now().date()) if current_placement and current_placement.get('Placement_Date') else datetime.now().date()

    with st.container(border=True):
        st.markdown("<h4 style='color: #00d4ff; margin-bottom: 15px;'>Update Your Placement Information</h4>", unsafe_allow_html=True)
        with st.form("placement_form_home"):
            col1, col2 = st.columns([1, 2])
            with col1:
                is_placed = st.checkbox("✅ I am Placed!", value=default_placed)
            with col2:
                company_name = st.text_input("🏢 Company Name", value=default_company, disabled=not is_placed)

            placement_date = st.date_input("📅 Placement Date", value=default_date, disabled=not is_placed)

            submit_button = st.form_submit_button("💾 Update Placement Status", use_container_width=True)
            if submit_button:
                if is_placed and not company_name:
                    st.warning("⚠️ Please provide company name if placed")
                else:
                    final_company = company_name if is_placed else None
                    final_date = placement_date if is_placed else None
                    if update_placement(st.session_state['user_id'], is_placed, final_company, final_date):
                        st.success("✅ Placement status updated successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to update placement status")

def get_student_profile(student_id):
    return get_student_info(student_id)

def update_student_profile(student_id, department, semester):
    q = "UPDATE Student SET Department = %s, Semester = %s WHERE Student_ID = %s"
    return execute_query(q, (department, semester, student_id), fetch=False)

def get_all_skills():
    # Uses Skills table
    res = execute_query("SELECT Skill_ID, Skill_Name FROM Skills ORDER BY Skill_Name")
    return res or []

def get_student_skills(student_id):
    q = """
    SELECT s.Skill_Name
    FROM Student_Skills ss
    JOIN Skills s ON ss.Skill_ID = s.Skill_ID
    WHERE ss.Student_ID = %s
    """
    res = execute_query(q, (student_id,))
    return [r['Skill_Name'] for r in res] if res else []

def update_student_skills(student_id, skill_names):
    connection = get_db_connection()
    if connection is None:
        return False
    try:
        cursor = connection.cursor(dictionary=True)
        # Clear existing
        cursor.execute("DELETE FROM Student_Skills WHERE Student_ID = %s", (student_id,))
        if skill_names:
            # Map names to IDs
            format_strings = ','.join(['%s'] * len(skill_names))
            cursor.execute(
                f"SELECT Skill_ID, Skill_Name FROM Skills WHERE Skill_Name IN ({format_strings})",
                tuple(skill_names)
            )
            rows = cursor.fetchall()
            name_to_id = {r['Skill_Name']: r['Skill_ID'] for r in rows}
            for name in skill_names:
                if name in name_to_id:
                    cursor.execute(
                        "INSERT INTO Student_Skills (Student_ID, Skill_ID) VALUES (%s, %s)",
                        (student_id, name_to_id[name])
                    )
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Error as e:
        st.error(f"Error updating student skills: {e}")
        if connection:
            connection.close()
        return False

def my_profile_page():
    """Student profile with info and skills editing"""
    st.markdown("<h1 style='text-align: center; color: #00d4ff; margin-bottom: 30px;'>👤 My Profile</h1>", unsafe_allow_html=True)

    profile = get_student_profile(st.session_state['user_id'])
    if not profile:
        st.error("❌ Could not load your profile.")
        return

    # Profile info cards
    st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>📋 Personal Information</h2>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown(f"<h4 style='color: #00d4ff;'>👤 Name</h4><p>{profile.get('Name', 'N/A')}</p>", unsafe_allow_html=True)
            st.markdown(f"<h4 style='color: #00d4ff;'>📧 Email</h4><p>{profile.get('College_Email', profile.get('Email', 'N/A'))}</p>", unsafe_allow_html=True)
    with col2:
        with st.container(border=True):
            st.markdown(f"<h4 style='color: #00d4ff;'>🏫 Department</h4><p>{profile.get('Department', 'N/A')}</p>", unsafe_allow_html=True)
            st.markdown(f"<h4 style='color: #00d4ff;'>📚 Semester</h4><p>{profile.get('Semester', 'N/A')}</p>", unsafe_allow_html=True)

    st.markdown("<hr style='border: 1px solid #00d4ff; margin: 40px 0;'>", unsafe_allow_html=True)

    # Edit Academic Details
    st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>🎓 Edit Academic Details</h2>", unsafe_allow_html=True)
    with st.container(border=True):
        with st.form("edit_student_profile"):
            col1, col2 = st.columns(2)
            with col1:
                new_department = st.text_input("🏫 Department", value=profile.get('Department', ''))
            with col2:
                # Ensure value is converted to int for number_input
                sem_val = int(profile.get('Semester', 1) or 1)
                new_semester = st.number_input("📚 Semester", min_value=1, max_value=10, step=1, value=sem_val)

            submit_profile = st.form_submit_button("💾 Save Academic Changes", use_container_width=True)
            if submit_profile:
                if update_student_profile(st.session_state['user_id'], new_department, new_semester):
                    st.success("✅ Profile updated successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to update profile")

    st.markdown("<hr style='border: 1px solid #00d4ff; margin: 40px 0;'>", unsafe_allow_html=True)

    # Edit Skills
    st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>🛠️ Edit Skills</h2>", unsafe_allow_html=True)
    all_skills = get_all_skills()
    current = get_student_skills(st.session_state['user_id'])

    with st.container(border=True):
        with st.form("edit_student_skills"):
            selected = st.multiselect("🎯 Select your skills", [s['Skill_Name'] for s in all_skills], default=current)
            submit_sk = st.form_submit_button("💾 Update Skills", use_container_width=True)
            if submit_sk:
                if update_student_skills(st.session_state['user_id'], selected):
                    st.success("✅ Skills updated successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to update skills")

def get_industry_description(industry_id):
    res = execute_query("SELECT Description FROM Industry WHERE Industry_ID = %s", (industry_id,))
    return res[0]['Description'] if res and 'Description' in res[0] else ""

def get_industry_skills(industry_id):
    """Get skills associated with an industry"""
    try:
        query = """
        SELECT s.Skill_Name
        FROM Industry_Skills isx
        JOIN Skills s ON isx.Skill_ID = s.Skill_ID
        WHERE isx.Industry_ID = %s
        ORDER BY s.Skill_Name
        """
        res = execute_query(query, (industry_id,))
        return [r['Skill_Name'] for r in res] if res else []
    except Error as e:
        if e.errno == 1146:  # Table doesn't exist
            st.warning("Industry_Skills table is missing. Please contact the administrator.")
            return []
        else:
            st.error(f"Error fetching industry skills: {e}")
            return []

def get_mentors_by_industry(industry_id):
    q = """
    SELECT a.Alumni_ID, a.Name, a.Current_Designation
    FROM Alumni a
    WHERE a.Industry_ID = %s AND a.Approved = TRUE
    ORDER BY a.Name
    """
    return execute_query(q, (industry_id,))

def explore_industries_page():
    st.title("Explore Industries")
    inds = get_industries()
    if not inds:
        st.info("No industries found.")
        return
    name_to_id = {i['Name']: i['Industry_ID'] for i in inds}
    selected = st.selectbox("Select an Industry", list(name_to_id.keys()))
    industry_id = name_to_id[selected]
    desc = get_industry_description(industry_id)
    if desc:
        st.write(desc)
    st.subheader("Key Skills")
    skills = get_industry_skills(industry_id)
    if skills:
        st.write(", ".join(skills))
    else:
        st.write("No skills listed.")
    st.subheader("Mentors in this Industry")
    mentors = get_mentors_by_industry(industry_id)
    if mentors:
        st.dataframe(pd.DataFrame(mentors), use_container_width=True)
    else:
        st.info("No mentors found for this industry.")

def filter_mentors_using_procedure(industry_keyword, min_rating):
    """
    Calls stored procedure:
    proc_FilterMentors(industry_keyword, min_rating)
    """
    query = "CALL proc_FilterMentors(%s, %s)"
    return execute_query(query, (industry_keyword, min_rating))

def find_a_mentor():
    """Find a Mentor Page (Normal Search + Stored Procedure Search)"""

    st.markdown(
        "<h2 style='color: #00d4ff; margin-bottom: 20px;'>🔎 Search & Request Mentors</h2>",
        unsafe_allow_html=True
    )

    # =====================================================
    # 🔍 STORED PROCEDURE BASED SEARCH (ADVANCED)
    # =====================================================
    st.subheader("🔍 Smart Mentor Search (Stored Procedure)")

    col1, col2 = st.columns(2)
    with col1:
        search_industry = st.text_input(
            "Filter by Industry (via Stored Procedure)",
            placeholder="e.g., Software"
        )
    with col2:
        min_rating = st.slider(
            "Minimum Rating",
            0.0, 5.0, 3.0, 0.5
        )

    if st.button("🔍 Find Mentors (Procedure)", use_container_width=True):
        industry_param = search_industry.strip() or None

        results = filter_mentors_using_procedure(
            industry_param,
            min_rating
        )

        if results:
            st.success(f"✅ Found {len(results)} mentor(s).")

            for mentor in results:
                # Stored procedure is expected to return dictionary rows
                name = mentor.get("Name")
                designation = mentor.get("Current_Designation")
                industry = mentor.get("Industry_Name")
                rating = mentor.get("Rating", 0)

                with st.expander(f"👤 {name} | ⭐ {rating}"):
                    st.write(f"🏢 **Industry:** {industry}")
                    st.write(f"💼 **Role:** {designation}")
        else:
            st.warning("No mentors found matching the criteria.")

    st.markdown("---")

    # =====================================================
    # 🔎 NORMAL SEARCH (FILTERS USING SELECT QUERIES)
    # =====================================================
    st.subheader("🔎 Standard Mentor Search")

    with st.container(border=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            search_name = st.text_input("Search by Name")

        with col2:
            industries = get_industries()
            industry_filter = None
            if industries:
                industry_options = ["All"] + [ind["Name"] for ind in industries]
                selected_industry = st.selectbox("Filter by Industry", industry_options)
                if selected_industry != "All":
                    industry_filter = next(
                        ind["Industry_ID"]
                        for ind in industries
                        if ind["Name"] == selected_industry
                    )

        with col3:
            skills_list = get_skills()
            skill_filter = None
            if skills_list:
                skill_options = ["All"] + skills_list
                selected_skill = st.selectbox("Filter by Skills", skill_options)
                if selected_skill != "All":
                    skill_filter = selected_skill

    # Build filters
    filters = {}
    if search_name:
        filters["name"] = search_name
    if industry_filter:
        filters["industry_id"] = industry_filter
    if skill_filter:
        filters["skill"] = skill_filter

    mentors = get_alumni_with_industry(filters)

    if mentors:
        seen = set()
        unique_mentors = []
        for mentor in mentors:
            if mentor["Alumni_ID"] not in seen:
                seen.add(mentor["Alumni_ID"])
                unique_mentors.append(mentor)

        for i in range(0, len(unique_mentors), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                if i + j < len(unique_mentors):
                    mentor = unique_mentors[i + j]
                    with col:
                        with st.container(border=True):
                            st.subheader(mentor["Name"])
                            st.write(f"💼 Designation: {mentor.get('Current_Designation', 'N/A')}")
                            st.write(f"🏢 Industry: {mentor.get('Industry_Name', 'N/A')}")

                            rating = get_alumni_rating(mentor["Alumni_ID"])
                            st.metric("⭐ Average Rating", f"{rating:.1f} / 5.0")

                            with st.expander("Request Mentorship"):
                                with st.form(f"request_form_{mentor['Alumni_ID']}"):
                                    req_msg = st.text_area(
                                        "Request Message",
                                        placeholder="Briefly describe what you want help with"
                                    )
                                    submit_req = st.form_submit_button("Send Request")

                                    if submit_req:
                                        if create_mentorship_request(
                                            st.session_state["user_id"],
                                            mentor["Alumni_ID"],
                                            req_msg or ""
                                        ):
                                            st.success(
                                                f"✅ Request sent to {mentor['Name']}!"
                                            )
                                            st.rerun()
                                        else:
                                            st.error(
                                                "❌ You already have a pending or accepted request."
                                            )
    else:
        st.info("No mentors found matching your criteria.")


def create_mentorship_request(student_id, alumni_id, message):
    q = """
    INSERT INTO Mentorship_Request (Student_ID, Alumni_ID, Request_Message, Status, Request_Date)
    VALUES (%s, %s, %s, 'Pending', %s)
    """
    # Use a separate query to check for existing pending/accepted requests to avoid duplicates
    check_q = "SELECT Request_ID FROM Mentorship_Request WHERE Student_ID = %s AND Alumni_ID = %s AND Status IN ('Pending', 'Accepted')"
    existing = execute_query(check_q, (student_id, alumni_id))
    
    if existing:
        st.warning("You already have a pending or accepted request with this mentor.")
        return False
        
    return execute_query(q, (student_id, alumni_id, message, datetime.now().date()), fetch=False)

def get_requests_by_status(user_id, role, status):
    """
    Gets requests for a user based on role and status.
    For Student: requests they SENT.
    For Alumni: requests they RECEIVED.
    """
    if role == 'Student':
        q = """
        SELECT mr.Request_ID, mr.Request_Message, mr.Request_Date, mr.Status, a.Name AS Mentor_Name
        FROM Mentorship_Request mr
        JOIN Alumni a ON mr.Alumni_ID = a.Alumni_ID
        WHERE mr.Student_ID = %s AND mr.Status = %s
        ORDER BY mr.Request_Date DESC
        """
        return execute_query(q, (user_id, status))
    elif role == 'Alumni':
        q = """
        SELECT mr.Request_ID, mr.Request_Message, mr.Request_Date, mr.Status, s.Name AS Student_Name
        FROM Mentorship_Request mr
        JOIN Student s ON mr.Student_ID = s.Student_ID
        WHERE mr.Alumni_ID = %s AND mr.Status = %s
        ORDER BY mr.Request_Date DESC
        """
        return execute_query(q, (user_id, status))
    return []

def get_student_sessions_by_status(student_id):
    """Gets all sessions for a student, grouped by status"""
    # Get accepted requests that don't have a session yet (Ready to Propose)
    q_new = """
        SELECT mr.Request_ID, mr.Alumni_ID, a.Name AS Mentor_Name
        FROM Mentorship_Request mr
        JOIN Alumni a ON mr.Alumni_ID = a.Alumni_ID
        WHERE mr.Student_ID = %s AND mr.Status = 'Accepted'
        AND mr.Request_ID NOT IN (SELECT Request_ID FROM Mentorship_Session WHERE Request_ID IS NOT NULL)
    """
    new_requests = execute_query(q_new, (student_id,))

    # Get sessions that are pending, confirmed, or completed
    q_sessions = """
        SELECT ms.Session_ID, a.Name AS Mentor_Name, ms.Date, ms.Mode, ms.Topics_Discussed, ms.Status, ms.Meeting_Link, ms.Proposed_By
        FROM Mentorship_Session ms
        JOIN Alumni a ON ms.Alumni_ID = a.Alumni_ID
        WHERE ms.Student_ID = %s
        ORDER BY ms.Date DESC
    """
    sessions = execute_query(q_sessions, (student_id,))

    return new_requests, sessions

def propose_session(request_id, student_id, alumni_id, date, mode, topics):
    q = """
    INSERT INTO Mentorship_Session (Request_ID, Student_ID, Alumni_ID, Date, Mode, Topics_Discussed, Status, Proposed_By)
    VALUES (%s, %s, %s, %s, %s, %s, 'Pending_Confirmation', 'Student')
    """
    return execute_query(q, (request_id, student_id, alumni_id, date, mode, topics), fetch=False)

def confirm_session(session_id):
    meeting_link = generate_meeting_id()
    q = "UPDATE Mentorship_Session SET Status = 'Confirmed', Meeting_Link = %s WHERE Session_ID = %s"
    return execute_query(q, (meeting_link, session_id), fetch=False)

def mark_session_completed(session_id):
    q = "UPDATE Mentorship_Session SET Status = 'Completed' WHERE Session_ID = %s"
    return execute_query(q, (session_id,), fetch=False)

def my_sessions_page():
    # Split the main tab content into sections
    st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>📅 My Requests & Sessions</h2>", unsafe_allow_html=True)

    # --- FIXED: Added a tab for Pending Requests (Sent by Student) ---
    tab_pending_sent, tab_accepted, tab_scheduled, tab_completed = st.tabs([
        "⏳ Pending (Sent)", "🎉 Accepted (Ready to Schedule)", "⚙️ Scheduled Sessions", "🏁 Completed Sessions"
    ])

    # 1. Pending Requests (Sent by Student)
    with tab_pending_sent:
        st.subheader("Your Pending Requests")
        pending_sent_requests = get_requests_by_status(st.session_state['user_id'], 'Student', 'Pending')
        if not pending_sent_requests:
            st.info("📭 You have no pending requests. Find a mentor to send one!")
        else:
            for req in pending_sent_requests:
                with st.container(border=True):
                    st.markdown(f"<h5 style='color: #00d4ff;'>👤 Sent to: {req['Mentor_Name']}</h5>", unsafe_allow_html=True)
                    st.write(f"📅 Date Sent: {req['Request_Date']}")
                    st.write(f"💬 Message: {req['Request_Message']}")
                    st.warning("Status: Awaiting Mentor Approval...")
    
    # Get accepted requests and sessions
    new_requests, sessions = get_student_sessions_by_status(st.session_state['user_id'])
    
    # 2. New Accepted Requests (Ready to Propose)
    with tab_accepted:
        st.subheader("New Accepted Requests - Propose a Session Time!")
        if not new_requests:
            st.write("📭 No new accepted requests. Waiting for your mentors to respond.")
        else:
            for req in new_requests:
                with st.container(border=True):
                    st.markdown(f"<h4 style='color: #00d4ff;'>🎓 Propose Session with {req['Mentor_Name']}</h4>", unsafe_allow_html=True)
                    alumni_id = req['Alumni_ID'] # Already fetched
                    with st.form(f"propose_form_{req['Request_ID']}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            prop_date = st.date_input("📅 Proposed Date")
                        with col2:
                            prop_mode = st.selectbox("💻 Mode", ["Online", "In-person"])

                        prop_topics = st.text_area("💬 Topics you'd like to discuss")
                        if st.form_submit_button("📤 Send Proposal", use_container_width=True):
                            if propose_session(req['Request_ID'], st.session_state['user_id'], alumni_id, prop_date, prop_mode, prop_topics):
                                st.success("✅ Proposal sent to mentor! Check the 'Scheduled Sessions' tab.")
                                st.rerun()

    # 3. Manage Scheduled Sessions
    with tab_scheduled:
        st.subheader("Manage Scheduled Sessions")
        pending_mentor, pending_you, confirmed = [], [], []
        if sessions:
            for s in sessions:
                if s['Status'] == 'Pending_Confirmation':
                    if s['Proposed_By'] == 'Alumni':
                        pending_you.append(s)
                    else:
                        pending_mentor.append(s)
                elif s['Status'] == 'Confirmed':
                    confirmed.append(s)

        st.markdown("<h5 style='color: #00d4ff;'>⏳ Pending My Approval (Mentor Proposed)</h5>", unsafe_allow_html=True)
        if not pending_you:
            st.info("📭 No sessions pending your approval.")
        else:
            for s in pending_you:
                with st.container(border=True):
                    st.write(f"🎓 Mentor: **{s['Mentor_Name']}** | 📅 Date: **{s['Date']}** | 💻 Mode: **{s['Mode']}**")
                    st.write(f"💬 Topics: {s['Topics_Discussed']}")
                    if st.button("✅ Confirm This Session", key=f"confirm_{s['Session_ID']}", use_container_width=True):
                        if confirm_session(s['Session_ID']):
                            st.success("🎉 Session Confirmed! A meeting link is generated.")
                            st.rerun()
                            
        st.markdown("<h5 style='color: #00d4ff;'>⏳ Pending Mentor Approval (You Proposed)</h5>", unsafe_allow_html=True)
        if not pending_mentor:
            st.info("📭 No sessions pending mentor approval.")
        else:
            for s in pending_mentor:
                with st.container(border=True):
                    st.write(f"🎓 Mentor: **{s['Mentor_Name']}** | 📅 Date: **{s['Date']}** | 📊 Status: **{s['Status']}**")


        st.markdown("<h5 style='color: #00d4ff;'>✅ Confirmed & Upcoming</h5>", unsafe_allow_html=True)
        if not confirmed:
            st.info("📭 No confirmed sessions.")
        else:
            for s in confirmed:
                with st.container(border=True):
                    st.markdown(f"<h5 style='color: #00d4ff;'>🎓 Mentor: {s['Mentor_Name']}</h5>", unsafe_allow_html=True)
                    st.write(f"📅 Date: {s['Date']} | 💻 Mode: {s['Mode']}")
                    st.success(f"🔗 Meeting Link: {s['Meeting_Link']}")
                    st.write(f"💬 Topics: {s['Topics_Discussed']}")
                    if st.button("🏁 Mark as Completed", key=f"complete_{s['Session_ID']}", use_container_width=True):
                        if mark_session_completed(s['Session_ID']):
                            st.success("✅ Session marked as complete. Check 'Completed Sessions' to leave feedback.")
                            st.rerun()

    # 4. Completed Sessions
    with tab_completed:
        st.subheader("Completed Sessions")

        completed_sessions = [s for s in sessions if s["Status"] == "Completed"]

        if not completed_sessions:
            st.info("📭 No sessions marked as completed yet.")
        else:
            for session in completed_sessions:
                with st.expander(
                    f"🎓 Session with {session['Mentor_Name']} – {session['Date']}"
                ):
                    st.write(
                        f"💬 Topics: {session.get('Topics_Discussed', 'N/A')}"
                    )

                    # Read-only session content
                    current_content = (
                        view_session_content(session["Session_ID"]) or ""
                    )

                    st.text_area(
                        "📝 Session Content & Discussions (Read-only for Student)",
                        value=current_content,
                        height=150,
                        disabled=True,
                        key=f"readonly_content_{session['Session_ID']}",
                    )

                    st.info("💡 Session Content is managed by the mentor.")
                    st.markdown("---")

                    # Feedback form
                    with st.form(
                        f"feedback_form_student_{session['Session_ID']}"
                    ):
                        st.markdown(
                            "<h5 style='color:#00d4ff;'>⭐ Submit Feedback</h5>",
                            unsafe_allow_html=True,
                        )

                        rating = st.slider(
                            "Rating (1–5)",
                            1,
                            5,
                            key=f"rating_{session['Session_ID']}",
                        )

                        comments = st.text_area(
                            "Comments",
                            key=f"comments_{session['Session_ID']}",
                        )

                        submit_button = st.form_submit_button(
                            "Submit Feedback"
                        )

                        if submit_button:
                            row = execute_query(
                                """
                                SELECT Alumni_ID
                                FROM Mentorship_Session
                                WHERE Session_ID = %s
                                """,
                                (session["Session_ID"],),
                            )

                            if row:
                                alumni_id = row[0]["Alumni_ID"]

                                if submit_feedback(
                                    st.session_state["user_id"],
                                    alumni_id,
                                    rating,
                                    comments,
                                ):
                                    st.success(
                                        "✅ Feedback submitted successfully!"
                                    )
                                    st.rerun()
                                else:
                                    st.error(
                                        "❌ Failed to submit feedback"
                                    )
                            else:
                                st.error(
                                    "❌ Mentor not found for this session"
                                )


def submit_feedback_page():
    """Submit Feedback Page - Replaced by logic in my_sessions_page, keeping the stub in case it's used elsewhere."""
    st.title("Submit Feedback (Placeholder)")
    st.info("Please use the 'Completed Sessions' tab on the 'My Requests & Sessions' page to submit feedback.")


def alumni_dashboard():
    """Alumni Dashboard Page"""
    st.markdown(f"<h1 style='text-align: center; color: #00d4ff; margin-bottom: 30px;'>Welcome, {st.session_state['name']}!</h1>", unsafe_allow_html=True)

    # Display alumni info
    alumni_info = get_alumni_info(st.session_state['user_id'])
    if alumni_info:
        st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>📋 My Profile Summary</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"🏢 Industry: {alumni_info.get('Industry_Name', 'N/A')}")
        with col2:
            st.info(f"💼 Designation: {alumni_info.get('Current_Designation', 'N/A')}")
        with col3:
            st.info(f"📈 Experience: {alumni_info.get('years_of_experience', 0)} years")

        if alumni_info.get('Graduating_Year'):
            st.info(f"🎓 Graduating Year: {alumni_info['Graduating_Year']}")

    # Display rating
    rating = get_alumni_rating(st.session_state['user_id'])
    st.metric(label="⭐ My Average Rating", value=f"{rating:.1f} / 5.0")

    st.markdown("<hr style='border: 1px solid #00d4ff; margin: 40px 0;'>", unsafe_allow_html=True)

    # Immediately show new requests section
    st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>📨 New Mentorship Requests</h2>", unsafe_allow_html=True)

    # --- FIXED: Use the dedicated function to get pending requests ---
    pending_requests = get_pending_requests_for_alumni(st.session_state['user_id'])

    if pending_requests:
        st.markdown(f"<p style='color: #00d4ff; margin-bottom: 15px;'>You have **{len(pending_requests)}** new request(s) to review</p>", unsafe_allow_html=True)

        for req in pending_requests:
            with st.container(border=True):
                st.markdown(f"<h4 style='color: #00d4ff;'>👨‍🎓 Request from: {req['Student_Name']}</h4>", unsafe_allow_html=True)
                st.write(f"📅 Date: {req['Request_Date']}")
                st.write(f"💬 Message: {req['Request_Message']}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Accept", key=f"acc_{req['Request_ID']}", use_container_width=True):
                        if update_request_status(req['Request_ID'], 'Accepted'):
                            # FIXED: Added message about next step
                            st.success("🎉 Request Accepted! Student will be notified to propose a time.")
                            st.rerun()
                with c2:
                    if st.button("❌ Decline", key=f"dec_{req['Request_ID']}", use_container_width=True):
                        if update_request_status(req['Request_ID'], 'Declined'):
                            st.warning("📝 Request Declined.")
                            st.rerun()
    else:
        st.info("📭 No new mentorship requests at this time.")

    st.markdown("<hr style='border: 1px solid #00d4ff; margin: 40px 0;'>", unsafe_allow_html=True)

    st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>💬 My Feedback</h2>", unsafe_allow_html=True)
    feedback = get_alumni_feedback(st.session_state['user_id'])

    if feedback:
        df = pd.DataFrame(feedback)
        # Reorder columns for better display
        df = df[['Date', 'Student_Name', 'Rating', 'Comments']]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("📭 No feedback received yet.")

def get_pending_requests_for_alumni(alumni_id):
    # This function is now the dedicated getter for pending requests.
    q = """
    SELECT mr.Request_ID, mr.Student_ID, s.Name AS Student_Name, mr.Request_Message, mr.Request_Date
    FROM Mentorship_Request mr
    JOIN Student s ON mr.Student_ID = s.Student_ID
    WHERE mr.Alumni_ID = %s AND mr.Status = 'Pending'
    ORDER BY mr.Request_Date DESC
    """
    return execute_query(q, (alumni_id,))

def update_request_status(request_id, new_status):
    q = "UPDATE Mentorship_Request SET Status = %s, Decision_Date = %s WHERE Request_ID = %s"
    return execute_query(q, (new_status, datetime.now().date(), request_id), fetch=False)

def get_alumni_sessions_by_status(alumni_id):
    # Get pending requests
    q_req = """
        SELECT mr.Request_ID, s.Name AS Student_Name, mr.Request_Message, mr.Request_Date
        FROM Mentorship_Request mr
        JOIN Student s ON mr.Student_ID = s.Student_ID
        WHERE mr.Alumni_ID = %s AND mr.Status = 'Pending'
        ORDER BY mr.Request_Date DESC
    """
    pending_requests = execute_query(q_req, (alumni_id,))

    # Get sessions
    q_sessions = """
        SELECT ms.Session_ID, s.Name AS Student_Name, ms.Date, ms.Mode, ms.Topics_Discussed, ms.Status, ms.Meeting_Link, ms.Proposed_By
        FROM Mentorship_Session ms
        JOIN Student s ON ms.Student_ID = s.Student_ID
        WHERE ms.Alumni_ID = %s
        ORDER BY ms.Date DESC
    """
    sessions = execute_query(q_sessions, (alumni_id,))

    return pending_requests, sessions

def requests_and_sessions_page():
    st.markdown("<h1 style='text-align: center; color: #00d4ff; margin-bottom: 30px;'>Manage Requests & Sessions</h1>", unsafe_allow_html=True)
    pending_requests, sessions = get_alumni_sessions_by_status(st.session_state['user_id'])

    if sessions is None:
        st.error("❌ Failed to fetch sessions. Please try again later.")
        return

    tab1, tab2, tab3 = st.tabs(["📨 New Mentorship Requests", "⚙️ Manage Scheduled Sessions", "🏁 Completed Sessions"])

    with tab1: # New Mentorship Requests
        st.subheader("New Requests to Review")
        st.info("💡 Accepting a request allows the student to propose a session time.")
        
        # --- FIXED: Use the main list of pending requests for the display and actions ---
        if not pending_requests:
            st.info("📭 No new mentorship requests.")
        for req in pending_requests:
            with st.container(border=True):
                st.markdown(f"<h4 style='color: #00d4ff;'>👨‍🎓 Request from: {req['Student_Name']}</h4>", unsafe_allow_html=True)
                st.write(f"📅 Date: {req['Request_Date']}")
                st.write(f"💬 Message: {req['Request_Message']}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Accept", key=f"acc_{req['Request_ID']}"):
                        if update_request_status(req['Request_ID'], 'Accepted'):
                            st.success("🎉 Request Accepted! Student will propose a time.")
                            st.rerun()
                with c2:
                    if st.button("❌ Decline", key=f"dec_{req['Request_ID']}"):
                        if update_request_status(req['Request_ID'], 'Declined'):
                            st.warning("📝 Request Declined.")
                            st.rerun()

    with tab2: # Manage Scheduled Sessions
        st.subheader("Scheduled Sessions")
        pending_you, pending_student, confirmed = [], [], []
        if sessions:
            for s in sessions:
                if s['Status'] == 'Pending_Confirmation':
                    if s['Proposed_By'] == 'Student':
                        pending_you.append(s)
                    else:
                        pending_student.append(s)
                elif s['Status'] == 'Confirmed':
                    confirmed.append(s)

        st.markdown("---")
        st.markdown("<h5 style='color: #00d4ff;'>⏳ Pending My Approval (Student Proposed)</h5>", unsafe_allow_html=True)
        if not pending_you:
            st.info("📭 No sessions pending your approval.")
        for s in pending_you:
            with st.container(border=True):
                st.write(f"👨‍🎓 Student: **{s['Student_Name']}** | 📅 Date: **{s['Date']}** | 💻 Mode: **{s['Mode']}**")
                st.write(f"💬 Topics: {s['Topics_Discussed']}")
                if st.button("✅ Confirm This Session", key=f"confirm_alum_{s['Session_ID']}"):
                    if confirm_session(s['Session_ID']):
                        st.success("🎉 Session Confirmed! Meeting link is generated.")
                        st.rerun()

        st.markdown("---")
        st.markdown("<h5 style='color: #00d4ff;'>⏳ Pending Student Approval (You Proposed)</h5>", unsafe_allow_html=True)
        if not pending_student:
            st.info("📭 No sessions pending student approval.")
        for s in pending_student:
            with st.container(border=True):
                st.write(f"👨‍🎓 Student: **{s['Student_Name']}** | 📅 Date: **{s['Date']}** | 📊 Status: **{s['Status']}**")

        st.markdown("---")
        st.markdown("<h5 style='color: #00d4ff;'>✅ Confirmed & Upcoming</h5>", unsafe_allow_html=True)
        if not confirmed:
            st.info("📭 No confirmed sessions.")
        for s in confirmed:
            with st.container(border=True):
                st.write(f"👨‍🎓 Student: **{s['Student_Name']}** | 📅 Date: **{s['Date']}** | 💻 Mode: **{s['Mode']}**")
                st.success(f"🔗 Meeting Link: {s['Meeting_Link']}")
                if st.button("🏁 Mark as Completed", key=f"complete_alum_{s['Session_ID']}"):
                    if mark_session_completed(s['Session_ID']):
                        st.success("✅ Session marked as complete.")
                        st.rerun()

    with tab3: # Completed Sessions
        st.subheader("Completed Sessions")
        completed = [s for s in sessions if s['Status'] == 'Completed']
        if completed:
            for session in completed:
                with st.expander(f"Session with {session['Student_Name']} - {session['Date']}"):
                    st.write(f"Topics: {session.get('Topics_Discussed', 'N/A')}")
                    # View/Edit Session Content (Alumni should manage content)
                    current_content = view_session_content(session['Session_ID']) or ""
                    with st.form(f"content_form_alumni_{session['Session_ID']}"):
                        content = st.text_area("📝 Session Content & Key Takeaways", value=current_content, height=150)
                        if st.form_submit_button("💾 Save Content", use_container_width=True):
                            if store_session_content(session['Session_ID'], content):
                                st.success("✅ Content saved successfully!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to save content")
        else:
            st.info("📭 No sessions marked as completed yet.")


def edit_profile():
    """Edit Profile Page"""
    st.title("Edit My Profile")
    
    # Get current profile data
    alumni_info = get_alumni_info(st.session_state['user_id'])
    current_skills = get_alumni_skills(st.session_state['user_id'])
    current_achievements = get_alumni_achievements(st.session_state['user_id'])
    
    if not alumni_info:
        st.error("Could not load profile information.")
        return
    
    # Edit Alumni Information
    st.header("Personal Information")
    with st.form("edit_profile_form"):
        name = st.text_input("Full Name", value=alumni_info.get('Name', ''))
        email = st.text_input("Email", value=alumni_info.get('Email', ''))
        phone_number = st.text_input("Phone Number", value=alumni_info.get('PhoneNumber', ''))
        current_designation = st.text_input("Current Designation", value=alumni_info.get('Current_Designation', ''))
        years_of_experience = st.number_input("Years of Experience", min_value=0, step=1, 
                                             value=int(alumni_info.get('years_of_experience', 0) or 0))
        
        industries = get_industries()
        industry_id = None
        if industries:
            industry_options = {ind['Name']: ind['Industry_ID'] for ind in industries}
            current_industry_name = alumni_info.get('Industry_Name')
            
            # Find the index of the current industry
            try:
                # Add a 'Select' option to handle cases where the current industry might be None
                keys = list(industry_options.keys())
                try:
                    default_index = keys.index(current_industry_name)
                except ValueError:
                    default_index = 0 # Default to first if not found (or 'Select' if added)

            except ValueError:
                 # No current industry name or list is empty
                 default_index = 0
                
            selected_industry = st.selectbox("Industry", list(industry_options.keys()), index=default_index)
            industry_id = industry_options[selected_industry]
        else:
            st.warning("Could not load industries")
        
        submit_profile = st.form_submit_button("Update Profile")
        
        if submit_profile:
            if update_alumni_profile(st.session_state['user_id'], name=name, email=email, 
                                   phone_number=phone_number, current_designation=current_designation,
                                   years_of_experience=years_of_experience, industry_id=industry_id):
                st.success("Profile updated successfully!")
                st.session_state['name'] = name # Update name in session state
                st.rerun()
            else:
                st.error("Failed to update profile")
    
    # Edit Skills
    st.header("Skills")
    all_skills = get_skills()
    with st.form("edit_skills_form"):
        selected_skills = st.multiselect("Select Skills", all_skills, default=current_skills)
        submit_skills = st.form_submit_button("Update Skills")
        
        if submit_skills:
            if update_alumni_skills(st.session_state['user_id'], selected_skills):
                st.success("Skills updated successfully!")
                st.rerun()
            else:
                st.error("Failed to update skills")
    
    # Edit Achievements
    st.header("Achievements")
    if current_achievements:
        st.write("Current Achievements:")
        for achievement in current_achievements:
            # Assumes Achievement table has Title and Year
            with st.expander(f"{achievement.get('Title', 'Achievement')} - {achievement.get('Year', 'N/A')}"):
                st.write(f"Description: {achievement.get('Description', 'N/A')}")
    
    # Note: Adding new achievements would require additional implementation
    st.info("To add or remove achievements, please contact the administrator.")

def analytics_dashboard():
    """Analytics Dashboard Page"""
    st.markdown("<h1 style='text-align: center; color: #00d4ff; margin-bottom: 30px;'>📊 Analytics Dashboard</h1>", unsafe_allow_html=True)

    # Get statistics
    stats = get_site_statistics()

    st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>📈 Key Metrics</h2>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("👨‍🎓 Total Students", stats.get('total_students', 0))
    with col2:
        st.metric("👨‍💼 Total Alumni (Approved)", stats.get('total_alumni', 0))
    with col3:
        st.metric("💼 Total Placements", stats.get('total_placements', 0))

    st.markdown("<hr style='border: 1px solid #00d4ff; margin: 40px 0;'>", unsafe_allow_html=True)

    # Placement trends chart
    st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>📊 Placement Trends</h2>", unsafe_allow_html=True)
    trends = get_placement_trends()
    if trends:
        df = pd.DataFrame(trends)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        st.bar_chart(df)
    else:
        st.info("📭 No placement data to display.")

def placement_log_page():
    """Placement Log Page"""
    st.markdown("<h1 style='text-align: center; color: #00d4ff; margin-bottom: 30px;'>📋 Placement Log</h1>", unsafe_allow_html=True)
    st.info("⚡ This log is automatically updated by a database trigger when a student's placement status is set to 'Placed'.")

    log_entries = get_placement_log()

    if log_entries:
        df = pd.DataFrame(log_entries)
        # Reorder for clarity
        df = df[['Log_Timestamp', 'Student_ID', 'Company_Name', 'Placement_Date', 'Log_ID']]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("📭 No placement log entries found.")

def user_management():
    """User Management Page"""
    st.markdown("<h1 style='text-align: center; color: #00d4ff; margin-bottom: 30px;'>👥 User Management</h1>", unsafe_allow_html=True)
    st.write("⚙️ Manage users and approve pending alumni registrations.")

    # Pending Alumni Approvals Section
    st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>⏳ Pending Alumni Approvals</h2>", unsafe_allow_html=True)

    try:
        pending_alumni = get_pending_alumni()

        if pending_alumni and len(pending_alumni) > 0:
            st.write(f"📋 Found {len(pending_alumni)} pending alumni registration(s).")

            # Display pending alumni in a table
            df = pd.DataFrame(pending_alumni)
            st.dataframe(df, use_container_width=True)

            # Approval section
            st.markdown("<h3 style='color: #00d4ff; margin-bottom: 15px;'>✅ Approve Alumni</h3>", unsafe_allow_html=True)
            with st.container(border=True):
                with st.form("approval_form"):
                    alumni_options = {f"{row['Name']} (ID: {row['Alumni_ID']})": row['Alumni_ID']
                                     for row in pending_alumni}
                    if alumni_options:
                        selected = st.selectbox("👤 Select Alumni to Approve", list(alumni_options.keys()))
                        submit_button = st.form_submit_button("✅ Approve Selected Alumni", use_container_width=True)

                        if submit_button:
                            alumni_id = alumni_options[selected]
                            if approve_alumni(alumni_id):
                                st.success(f"🎉 Alumni approved successfully!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to approve alumni. Please try again.")
                    else:
                        st.info("📭 No alumni to select.")
        else:
            st.info("✅ No pending alumni registrations. All alumni accounts are approved.")

    except Exception as e:
        st.error(f"❌ Error loading pending alumni: {e}")
        st.info("🔍 Please check your database connection and ensure the Alumni table exists.")

    st.markdown("<hr style='border: 1px solid #00d4ff; margin: 40px 0;'>", unsafe_allow_html=True)

    # Additional user management features
    st.markdown("<h2 style='color: #00d4ff; margin-bottom: 20px;'>📊 All Users Overview</h2>", unsafe_allow_html=True)

    try:
        # Get all students
        all_students = execute_query("SELECT Student_ID, Name, College_Email, Department, Semester FROM Student LIMIT 50")
        all_alumni = execute_query("SELECT Alumni_ID, Name, Email, Current_Designation, Approved FROM Alumni LIMIT 50")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("<h3 style='color: #00d4ff;'>👨‍🎓 Students</h3>", unsafe_allow_html=True)
            if all_students:
                st.write(f"📈 Total: {len(all_students)} students (showing first 50)")
                st.dataframe(pd.DataFrame(all_students), use_container_width=True)
            else:
                st.info("📭 No students found.")

        with col2:
            st.markdown("<h3 style='color: #00d4ff;'>👨‍💼 Alumni</h3>", unsafe_allow_html=True)
            if all_alumni:
                st.write(f"📈 Total: {len(all_alumni)} alumni (showing first 50)")
                st.dataframe(pd.DataFrame(all_alumni), use_container_width=True)
            else:
                st.info("📭 No alumni found.")

    except Exception as e:
        st.warning(f"⚠️ Could not load user overview: {e}")

if __name__ == "__main__":
    main()

# Update the design to implement a futuristic UI with dynamic styling
st.markdown(
    """
    <style>
    /* Apply a futuristic theme */
    .stApp {
        background: linear-gradient(135deg, #0a0a0a, #1a1a1a, #2a2a2a); /* Deeper gradient background */
        color: #00d4ff; /* Neon blue text */
        font-family: 'Roboto', sans-serif; /* Modern font */
        animation: backgroundShift 10s ease-in-out infinite; /* Subtle background animation */
    }
    @keyframes backgroundShift {
        0%, 100% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
    }
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        background-color: #333333; /* Dark input background */
        color: #00d4ff; /* Neon blue text */
        border: 1px solid #00d4ff; /* Neon blue border */
        border-radius: 8px; /* Rounded corners */
        padding: 10px;
        font-size: 16px;
    }
    .stButton button {
        background: linear-gradient(135deg, #00d4ff, #007bff); /* Gradient button */
        color: #ffffff; /* White text */
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-size: 16px;
        font-weight: bold;
        box-shadow: 0 4px 15px rgba(0, 212, 255, 0.5); /* Glow effect */
        transition: all 0.3s ease;
        width: 100%; /* Full width by default */
    }
    .stButton button:hover {
        transform: translateY(-2px) scale(1.02); /* Lift and slight zoom on hover */
        box-shadow: 0 8px 25px rgba(0, 212, 255, 0.8); /* Stronger glow */
    }
    .stButton button:active {
        transform: translateY(0) scale(0.98); /* Press effect */
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #2a2a2a; /* Dark gray tabs */
        color: #00d4ff; /* Neon blue text */
        border-radius: 8px 8px 0 0; /* Rounded top corners */
        padding: 10px;
        font-size: 16px;
        font-weight: bold;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #00d4ff, #007bff); /* Gradient for active tab */
        color: #ffffff; /* White text */
        box-shadow: 0 4px 10px rgba(0, 212, 255, 0.5); /* Glow effect */
    }
    .stMetric {
        background: linear-gradient(135deg, #333333, #444444); /* Gradient background */
        color: #00d4ff; /* Neon blue text */
        border-radius: 12px; /* More rounded corners */
        padding: 15px;
        box-shadow: 0 6px 20px rgba(0, 212, 255, 0.4); /* Enhanced glow effect */
        border: 1px solid #00d4ff; /* Neon border */
        transition: transform 0.3s ease;
    }
    .stMetric:hover {
        transform: translateY(-3px); /* Lift on hover */
        box-shadow: 0 10px 30px rgba(0, 212, 255, 0.6); /* Stronger glow */
    }
    .stDataFrame {
        background-color: #1a1a1a; /* Dark background */
        color: #00d4ff; /* Neon blue text */
        border: 2px solid #00d4ff; /* Thicker neon blue border */
        border-radius: 12px; /* More rounded corners */
        box-shadow: 0 6px 20px rgba(0, 212, 255, 0.4); /* Enhanced glow effect */
        overflow: hidden; /* Clean edges */
    }
    .stDataFrame thead th {
        background: linear-gradient(135deg, #00d4ff, #007bff); /* Gradient header */
        color: #ffffff; /* White text */
        font-weight: bold;
        padding: 12px;
    }
    .stDataFrame tbody td {
        padding: 10px;
        border-bottom: 1px solid #333333;
    }
    .stDataFrame tbody tr:hover {
        background-color: #2a2a2a; /* Highlight row on hover */
    }
    </style>
    """,
    unsafe_allow_html=True
)