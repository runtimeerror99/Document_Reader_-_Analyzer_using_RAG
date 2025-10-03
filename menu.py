import streamlit as st
import pyrebase
import json
from datetime import datetime
import uuid

# Initialize Firebase once at the module level 
def get_firebase():
    if 'firebase' not in st.session_state:
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
        st.session_state.firebase = pyrebase.initialize_app(firebaseConfig)
    return st.session_state.firebase

# Generate a unique chat ID
def generate_chat_id():
    return f"chat_{uuid.uuid4().hex[:10]}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

def authmenu():
    st.sidebar.page_link("./pages/project.py",label="Projects")
    st.sidebar.page_link("./pages/query.py",label="Query")
    st.sidebar.page_link("./pages/visualize.py",label="Data Analysis")
    
    # Chat management section in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Chat Management")
    
    # Display existing chats if available
    if "chat_list" in st.session_state and len(st.session_state.chat_list) > 0:
        chat_options = ["New Chat"] + [f"Chat {idx+1}: {chat['title'][:20]}..." 
                                      for idx, chat in enumerate(st.session_state.chat_list)]
        selected_chat = st.sidebar.selectbox("Select Chat:", options=chat_options)
        
        if selected_chat != "New Chat":
            chat_idx = int(selected_chat.split(":")[0].replace("Chat ", "")) - 1
            col1, col2 = st.sidebar.columns([1, 1])
            with col1:
                load_chat_button = st.button("Load Chat", key="load_chat")
                if load_chat_button:
                    load_chat(chat_idx)
            with col2:
                delete_chat_button = st.button("Delete Chat", key="delete_chat")
                if delete_chat_button:
                    delete_chat(chat_idx)
    
    # Create new chat button
    st.sidebar.button("Create New Chat", on_click=clear_chat, key="clear_button", type="primary")
    
    # Save current chat button
    if "messages" in st.session_state and len(st.session_state.messages) > 0:
        st.sidebar.button("Save Current Chat", on_click=save_current_chat, key="save_button")

def unauthmenu():
    st.sidebar.page_link("./pages/authenticate.py",label="Login/Signup")

# Function to clear chat history and start a new chat
def clear_chat():
    # Save the current chat if it has messages
    if "messages" in st.session_state and len(st.session_state.messages) > 0:
        save_chat_to_firebase()
    
    # Clear current messages
    st.session_state.messages = []
    st.session_state.current_chat_id = generate_chat_id()
    st.session_state.current_chat_title = "New Chat"
    # st.experimental_rerun()

# Function to save current chat
def save_current_chat():
    if save_chat_to_firebase():
        st.sidebar.success("Chat saved successfully!")
    else:
        st.sidebar.error("Failed to save chat.")

# Function to load a saved chat
def load_chat(chat_index):
    chat_data = st.session_state.chat_list[chat_index]
    st.session_state.messages = chat_data['messages']
    st.session_state.current_chat_id = chat_data['chat_id']
    st.session_state.current_chat_title = chat_data['title']
    st.session_state.curr = chat_data.get('project', "")  # Also restore project context
    st.experimental_rerun()

# Function to delete a chat
def delete_chat(chat_index):
    chat_data = st.session_state.chat_list[chat_index]
    chat_id = chat_data['chat_id']
    user_id = st.session_state.role.replace(".", "_").replace("@", "_at_")
    
    try:
        firebase = get_firebase()
        db = firebase.database()
        
        # Make sure we have a valid auth token
        if "user" in st.session_state and "idToken" in st.session_state.user:
            db.child("users").child(user_id).child("chats").child(chat_id).remove(st.session_state.user["idToken"])
        else:
            db.child("users").child(user_id).child("chats").child(chat_id).remove()
        
        # Update local chat list
        st.session_state.chat_list.pop(chat_index)
        st.success("Chat deleted successfully!")
        st.experimental_rerun()
    except Exception as e:
        st.error(f"Failed to delete chat: {str(e)}")

# Save current chat to Firebase
def save_chat_to_firebase():
    if "role" not in st.session_state or st.session_state.role is None:
        st.warning("You must be logged in to save chats")
        return False
    
    if "messages" not in st.session_state or len(st.session_state.messages) == 0:
        st.warning("No messages to save")
        return False
    
    try:
        # Get the first user message as the chat title (or truncated version)
        first_user_msg = next((msg["content"] for msg in st.session_state.messages 
                            if msg["role"] == "user"), "New Chat")
        title = first_user_msg[:30] + "..." if len(first_user_msg) > 30 else first_user_msg
        
        # Get current chat ID or generate a new one
        if "current_chat_id" not in st.session_state:
            st.session_state.current_chat_id = generate_chat_id()
        
        # Get user ID (email or hash)
        user_id = st.session_state.role.replace(".", "_").replace("@", "_at_")
        
        # Handle images and special objects in messages
        sanitized_messages = []
        for msg in st.session_state.messages:
            # Create a clean copy of the message
            clean_msg = {"role": msg["role"]}
            
            # If it's an image message, only store a marker
            if msg.get("is_image", False):
                clean_msg["content"] = "[Image visualization]"
                clean_msg["is_image"] = True
            else:
                clean_msg["content"] = msg["content"]
                
            sanitized_messages.append(clean_msg)
        
        # Create chat data object
        chat_data = {
            "chat_id": st.session_state.current_chat_id,
            "title": title,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "messages": sanitized_messages,
            "project": st.session_state.get("curr", "")
        }
        
        # Save to Firebase with auth token if available
        firebase = get_firebase()
        db = firebase.database()
        
        # Use authentication token if available
        if "user" in st.session_state and "idToken" in st.session_state.user:
            db.child("users").child(user_id).child("chats").child(st.session_state.current_chat_id).set(chat_data, st.session_state.user["idToken"])
        else:
            # Try to use a simpler path approach if no token
            db.child("users").child(user_id).child("chats").child(st.session_state.current_chat_id).set(chat_data)
        
        # Check if chat exists in chat_list and update it
        updated = False
        if "chat_list" in st.session_state:
            for i, chat in enumerate(st.session_state.chat_list):
                if chat.get("chat_id", "") == st.session_state.current_chat_id:
                    st.session_state.chat_list[i] = chat_data
                    updated = True
                    break
                    
            # If not found in list, add it
            if not updated:
                st.session_state.chat_list.insert(0, chat_data)
        else:
            # Initialize chat_list if not exists
            st.session_state.chat_list = [chat_data]
                
        return True
    except Exception as e:
        st.warning(f"Failed to save chat: {str(e)}")
        return False

# Load all chats for the current user from Firebase
def load_chats_from_firebase():
    if "role" not in st.session_state or st.session_state.role is None:
        return []
    
    user_id = st.session_state.role.replace(".", "_").replace("@", "_at_")
    
    try:
        firebase = get_firebase()
        db = firebase.database()
        
        # Use authentication token if available
        if "user" in st.session_state and "idToken" in st.session_state.user:
            chats = db.child("users").child(user_id).child("chats").get(st.session_state.user["idToken"]).val()
        else:
            chats = db.child("users").child(user_id).child("chats").get().val()
        
        if chats:
            chat_list = list(chats.values())
            # Sort by timestamp (newest first)
            chat_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return chat_list
        return []
    except Exception as e:
        st.warning(f"Failed to load chats: {str(e)}")
        return []

def menu():
    # Initialize chat ID if not present
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id = generate_chat_id()
    
    # Initialize current_chat_title if not present
    if "current_chat_title" not in st.session_state:
        st.session_state.current_chat_title = "New Chat"
    
    if "role" not in st.session_state or st.session_state.role is None:
        unauthmenu()
    else:
        # Load chats when user is authenticated
        if "chat_list" not in st.session_state:
            st.session_state.chat_list = load_chats_from_firebase()
        
        authmenu()
        
        # Move logout button to bottom of sidebar
        st.sidebar.markdown("---")
        logout = st.sidebar.button("Logout")
        if logout:
            # Save current chat before logging out
            if "messages" in st.session_state and len(st.session_state.messages) > 0:
                save_chat_to_firebase()
                
            st.session_state.role = None
            st.session_state.projects = []
            st.session_state.curr = None
            st.session_state.messages = []
            st.session_state.chat_list = []
            st.session_state.current_chat_id = None
            st.session_state.current_chat_title = None
            if "user" in st.session_state:
                del st.session_state.user
            st.session_state.clear()
            st.switch_page("./pages/authenticate.py")


