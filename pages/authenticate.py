import streamlit as st
import os
import re
from menu import menu, load_chats_from_firebase, generate_chat_id, save_chat_to_firebase
from PIL import Image
import pyrebase
from datetime import datetime

def show_logo():
    try:
        logo = Image.open("logo.png")
        st.image(logo, width=200)
    except:
        st.title("DORA")

if "role" not in st.session_state:
    st.session_state.role = None

st.set_page_config(page_title="DORA", page_icon="🦙")
st.markdown(f"""<style>
        .st-emotion-cache-79elbk{{
            display: none;}}
            </style>""", unsafe_allow_html=True)
menu()

show_logo()
st.header("Welcome to DORA")

# Use correct Firebase configuration
firebaseConfig = {
  'apiKey': st.secrets["apiKey"],
  'authDomain': st.secrets["authDomain"],
  'projectId': st.secrets["projectId"],
  'storageBucket': st.secrets["storageBucket"],
  'messagingSenderId': st.secrets["messagingSenderId"],
  'appId': st.secrets["appId"],
  'measurementId': st.secrets["measurementId"],
  'databaseURL': st.secrets["databaseURL"]
}

# Make sure we're using HTTPS for the database URL
if not firebaseConfig['databaseURL'].startswith('https://'):
    firebaseConfig['databaseURL'] = 'https://' + firebaseConfig['databaseURL']

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
db = firebase.database()
st.session_state.firebase = firebase

# Custom login form with email validation
def custom_login_form():
    with st.form("login_form"):
        email = st.text_input("Email", key="login_email", placeholder="Enter your email")
        password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if not email or not password:
                st.error("Please enter both email and password")
                return None, None
            
            # Basic email validation
            email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
            if not re.match(email_pattern, email):
                st.error("Please enter a valid email address")
                return None, None
                
            return email, password
    
    return None, None

# Custom signup form with validation
def custom_signup_form():
    with st.form("signup_form"):
        email = st.text_input("Email", key="signup_email", placeholder="Enter your email")
        password = st.text_input("Password", type="password", key="signup_password", placeholder="Enter your password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password", placeholder="Confirm your password")
        submit = st.form_submit_button("Sign Up")
        
        if submit:
            if not email or not password or not confirm_password:
                st.error("Please fill all fields")
                return None, None
                
            # Email validation
            email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
            if not re.match(email_pattern, email):
                st.error("Please enter a valid email address")
                return None, None
                
            # Password matching
            if password != confirm_password:
                st.error("Passwords do not match")
                return None, None
                
            # Password strength
            if len(password) < 6:
                st.error("Password must be at least 6 characters")
                return None, None
                
            return email, password
    
    return None, None

tab1, tab2 = st.tabs(["Login", "Sign Up"])

with tab1:
    st.subheader("Login")
    email, password = custom_login_form()
    
    if email and password:
        with st.spinner("Logging in..."):
            try:
                # Authenticate with Firebase
                user = auth.sign_in_with_email_and_password(email, password)
                
                # Store the user object with ID token for database operations
                st.session_state.user = user
                
                # Set session state
                st.session_state.role = email
                
                # Initialize user directory if it doesn't exist
                if not os.path.exists(f"{email}"):
                    os.makedirs(f"{email}")
                    os.makedirs(f"{email}/index", exist_ok=True)
                    os.makedirs(f"{email}/summary", exist_ok=True)
                
                # Load projects
                st.session_state.projects = []
                if os.path.exists(f"{email}"):
                    projects = [p for p in os.listdir(f"{email}") 
                              if p != 'index' and p != 'summary' and 
                              os.path.isdir(f"{email}/{p}")]
                    st.session_state.projects = projects
                
                # Initialize chat state
                try:
                    st.session_state.chat_list = load_chats_from_firebase()
                except Exception as e:
                    st.session_state.chat_list = []
                    st.warning(f"Could not load chats: {str(e)}")
                    
                st.session_state.current_chat_id = generate_chat_id()
                st.session_state.current_chat_title = "New Chat"
                st.session_state.messages = []
                
                # Navigate to projects page
                st.success("Login successful!")
                st.switch_page("./pages/project.py")
                
            except Exception as e:
                # Print detailed error for debugging
                st.error(f"Login failed: {str(e)}")

with tab2:
    st.subheader("Sign Up")
    email, password = custom_signup_form()
    
    if email and password:
        with st.spinner("Creating account..."):
            try:
                # Create user with Firebase Authentication
                user = auth.create_user_with_email_and_password(email, password)
                
                # Save auth token
                st.session_state.user = user
                
                # Create sanitized user ID for database path
                user_id = email.replace(".", "_").replace("@", "_at_")
                
                try:
                    # Store user data in Firebase with token
                    user_data = {
                        "email": email,
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    # Use authentication token for write operation
                    db.child("users").child(user_id).set(user_data, user['idToken'])
                    
                    # Create user directory structure
                    os.makedirs(f"{email}", exist_ok=True)
                    os.makedirs(f"{email}/index", exist_ok=True)
                    os.makedirs(f"{email}/summary", exist_ok=True)
                    
                    st.success("Account created successfully! Please login.")
                    
                except Exception as db_error:
                    st.warning(f"User created but additional setup failed: {db_error}")
                    st.info("You can still login with your new account.")
                
            except Exception as e:
                error_message = str(e)
                if "EMAIL_EXISTS" in error_message:
                    st.error("Email already exists. Please try with a different email or login.")
                else:
                    st.error(f"Failed to create account: {error_message}")

# Add debug expander to help troubleshooting
# with st.expander("Debug Information"):
#     st.write("Firebase Config (API Key hidden):")
#     safe_config = dict(firebaseConfig)
#     safe_config['apiKey'] = "******"
#     st.write(safe_config)
    
#     if "user" in st.session_state:
#         st.write("User authenticated: Yes")
#     else:
#         st.write("User authenticated: No")










