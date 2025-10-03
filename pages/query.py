import streamlit as st
import os
from menu import menu, save_chat_to_firebase
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, SummaryIndex, StorageContext, load_index_from_storage
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.chat_engine.context import ContextChatEngine
from llama_index.llms.openai import OpenAI
from llama_index.core.base.llms.types import ChatMessage
from llama_index.core.prompts import PromptTemplate
from typing import List

st.set_page_config(page_title="DORA", page_icon="🦙")
st.markdown(f"""<style>
        .st-emotion-cache-79elbk{{
            display: none;}}
        .main-content {{
            min-height: 80vh;
        }}
            .clear-button {{
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        border: none;
        background-color: #ff5555;
        color: white;
        font-weight: bold;
        cursor: pointer;
        transition: background-color 0.2s;
        margin-bottom: 10px;
    }}
    
    .clear-button:hover {{
        background-color: #ff3333;
    }}
            
            </style>""", unsafe_allow_html=True)
menu()

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat title if it exists
if "current_chat_title" in st.session_state and st.session_state.current_chat_title != "New Chat":
    st.subheader(f"Chat: {st.session_state.current_chat_title}")

# Add this function to handle image placeholder messages
def handle_image_placeholder(message):
    """Display a placeholder for saved image visualizations"""
    st.info("This is a visualization from a previous chat. Images are not saved in their original format.")

# Display the chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("is_image", False):
            # It's an image placeholder from chat history
            handle_image_placeholder(message)
        else:
            st.markdown(message["content"])

gen_prompt = "Leverage your chatbot abilities to answer in detail some given questions on a specific topic by only using the context provided, not using any prior knowledge, making sure to avoid repetitions in the informations and write the answers in such a way that all the answers must follow the flow and together can be used to form a report."

try: 
    projects_names = os.listdir(f"{st.session_state.role}/index")
    project_name = st.sidebar.selectbox("Select Project:", options=projects_names)
    st.sidebar.write(f"Selected Project: {project_name}")
    st.session_state.curr = project_name  # Save current project for chat history
    
    if os.path.exists(f'{st.session_state.role}/index/{project_name}'):
        if os.path.exists(f"{st.session_state.role}/{project_name}"):
            files = os.listdir(f"{st.session_state.role}/{project_name}")
            if files:
                for file in files:
                    st.sidebar.write(file)
            else:
                st.sidebar.write("The project is empty.")
    else:
        docs = SimpleDirectoryReader(f"{st.session_state.role}/{project_name}").load_data()
        index = VectorStoreIndex.from_documents(docs)
        summary = SummaryIndex.from_documents(docs)
        index.storage_context.persist(f'{st.session_state.role}/index/{project_name}')
        summary.storage_context.persist(f'{st.session_state.role}/summary/{project_name}')

except Exception as e:
    st.write("No Index Found.")
    st.stop()

def format_chat_history_for_display(messages: List[dict], max_history=4):
    """Format the chat history for display in the sidebar."""
    # Get the last N messages
    recent_messages = messages[-max_history:] if len(messages) > max_history else messages
    formatted_history = ""
    for msg in recent_messages:
        role = "Human" if msg["role"] == "user" else "Assistant"
        formatted_history += f"{role}: {msg['content']}\n\n"
    return formatted_history

def query():
    query = st.chat_input(f"Enter Query:")
    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)
        
        # Choose the right index based on the query
        if "summary" in query.lower() or "short note" in query.lower() or "tldr" in query.lower() or "tl;dr" in query.lower():
            storage_context = StorageContext.from_defaults(persist_dir=f'{st.session_state.role}/summary/{project_name}')
            index = load_index_from_storage(storage_context)
        else:
            storage_context = StorageContext.from_defaults(persist_dir=f'{st.session_state.role}/index/{project_name}')
            index = load_index_from_storage(storage_context)
        
        # Get recent chat history (last 4 conversations)
        recent_messages = st.session_state.messages[:-1]
        max_history = 4
        if len(recent_messages) > max_history:
            recent_messages = recent_messages[-max_history:]
        
        # Format chat history for display
        chat_history_display = format_chat_history_for_display(recent_messages)
        
        # Initialize the LLM with OpenAI
        llm = OpenAI(temperature=0.1)  # Lower temperature for more consistent responses
        
        # Create memory with recent chat history
        memory = ChatMemoryBuffer.from_defaults(token_limit=500000)
        
        # Add previous messages to memory using ChatMessage
        for msg in recent_messages:
            if msg["role"] == "user":
                memory.put(ChatMessage(role="user", content=msg["content"]))
            elif msg["role"] == "assistant":
                memory.put(ChatMessage(role="assistant", content=msg["content"]))
        
        # Create a proper template object for text_qa_template with stronger emphasis on follow-up requests
        text_qa_template = PromptTemplate(
            template="""
            {gen_prompt}
            
            IMPORTANT: Pay close attention to any formatting, length, or style instructions in the question.
            If asked for a short answer, brief summary, or specific word count, strictly adhere to those requirements.
            
            Only use the given context, do not add any prior knowledge.
            Take into account our conversation history when answering.
            
            The given context: {context_str}
            
            Question: {query_str}
            """.format(gen_prompt=gen_prompt, context_str="{context_str}", query_str="{query_str}")
        )
        
        # Update the query engine with custom instructions using the proper template
        query_engine = index.as_query_engine(
            similarity_top_k=3,
            text_qa_template=text_qa_template
        )
                
        # Create a regular chat engine with memory instead of CondenseQuestionChatEngine
        chat_engine = ContextChatEngine.from_defaults(
            retriever=query_engine,
            chat_history=recent_messages,
            memory=memory,
            system_prompt=(
                f"{gen_prompt}\n"
                "IMPORTANT: Pay close attention to any formatting, length, or style instructions in the question.\n"
                "If asked for a short answer, brief summary, or specific word count, strictly adhere to those requirements.\n"
                "Only use the given context, do not add any prior knowledge.\n"
                "You are an AI assistant named DORA, not a person. If asked who you are, identify yourself as DORA, an AI assistant.\n"
                "Take into account our conversation history when answering."
            ),
            llm=llm,
            verbose=True  # Enable verbose mode for debugging
        )
        
        with st.chat_message("assistant"):
            with st.spinner("Grabbing the answers..."):
                response = chat_engine.chat(query)
                st.markdown(response.response)
                st.session_state.messages.append({"role": "assistant", "content": response.response})

if __name__ == "__main__":
    query()