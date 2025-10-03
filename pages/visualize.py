import streamlit as st
import os
from menu import menu
import pandas as pd
from lida import Manager, TextGenerationConfig, llm
from PIL import Image
from io import BytesIO
import base64
import matplotlib.pyplot as plt
from llama_index.core.query_pipeline import (
    QueryPipeline as QP,
    Link,
    InputComponent,
)
from llama_index.experimental.query_engine.pandas import (
    PandasInstructionParser,
)
from llama_index.llms.openai import OpenAI
from llama_index.core import PromptTemplate


st.set_page_config(page_title="DORA", page_icon="🦙")
st.markdown(f"""<style>
        .st-emotion-cache-79elbk{{
            display: none;}}
            </style>""", unsafe_allow_html=True)
menu()


if "messages" not in st.session_state:
    st.session_state.messages = []

# Define base64_to_image function before it's used
def base64_to_image(base64_string):
    """Convert a base64 string to a PIL image object"""
    try:
        # Check if the string starts with data URI scheme and extract only the base64 part if needed
        if isinstance(base64_string, str) and base64_string.startswith('data:image'):
            base64_string = base64_string.split(',')[1]
            
        image_data = base64.b64decode(base64_string)
        return Image.open(BytesIO(image_data))
    except Exception as e:
        st.error(f"Error converting base64 to image: {e}")
        return None

# Add this to your existing code after the imports
def handle_image_placeholder(message):
    """Handle image placeholder messages"""
    st.markdown("*Image visualization from previous chat*")
    st.info("Visualizations from saved chats cannot be redisplayed. Please recreate the visualization if needed.")


# Display chat history properly
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("is_image", False):
            # Check if it's a placeholder from loaded chat history
            if message["content"] == "[Image visualization]":
                handle_image_placeholder(message)
            else:
                # For image messages, display the image from base64 data
                image_data = message.get("content", "")
                try:
                    # If it's a LIDA chart object with raster attribute
                    if hasattr(image_data, 'raster'):
                        st.image(base64_to_image(image_data.raster), caption='Visualization')
                    # If it's a base64 string
                    else:
                        image = base64_to_image(image_data)
                        if image:
                            st.image(image, caption='Visualization')
                        else:
                            st.write("Image could not be displayed - format issue")
                except Exception as e:
                    st.write(f"Image could not be displayed: {str(e)}")
        else:
            # For text messages
            st.markdown(message["content"])

instruction_str = (
    "1. Convert the query to executable Python code using Pandas.\n"
    "2. The final line of code should be a Python expression that can be called with the `eval()` function.\n"
    "3. The code should represent a solution to the query.\n"
    "4. PRINT ONLY THE EXPRESSION.\n"
    "5. Do not quote the expression.\n"
)

pandas_prompt_str = (
    "You are working with a pandas dataframe in Python.\n"
    "The name of the dataframe is `df`.\n"
    "This is the result of `print(df.head())`:\n"
    "{df_str}\n\n"
    "Follow these instructions:\n"
    "{instruction_str}\n"
    "Query: {query_str}\n\n"
    "Expression:"
)
response_synthesis_prompt_str = (
    "Given an input question, synthesize a response from the query results.\n"
    "Query: {query_str}\n\n"
    "Pandas Instructions (optional):\n{pandas_instructions}\n\n"
    "Pandas Output: {pandas_output}\n\n"
    "Response: "
)

def image_to_base64(image):
    """Convert PIL image to base64 string"""
    buffered = BytesIO()
    if isinstance(image, Image.Image):
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    else:
        # If it's already a base64 string or other format, return as is
        return image

# Initialize LIDA manager
lida = Manager(text_gen=llm("openai"))
text_gen_config = TextGenerationConfig(n=1, temperature=0.1, model="gpt-4o-mini", use_cache=False)

try: 
    project_name = st.sidebar.selectbox("Select Project:", options=st.session_state.projects)
    st.sidebar.write(f"Selected Project: {project_name}")
    if os.path.exists(f"{st.session_state.role}/{project_name}"):
        files = os.listdir(f"{st.session_state.role}/{project_name}")
        if files:
            csv_files = [file for file in files if file.endswith('.csv')]
            if csv_files:
                for file in csv_files:
                    st.sidebar.write(file)
                filename = csv_files[0]  # Default to first CSV file
            else:
                st.sidebar.write("No CSV files found.")
                st.stop()
        else:
            st.sidebar.write("The project is empty.")
            st.stop()

except Exception as e:
    st.write(f"No Dataset Found: {str(e)}")
    st.stop()

llm = OpenAI(model="gpt-4o-mini")




def visualize():

        
    query = st.chat_input(f"Enter Query:")
    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)
            
        # Find a CSV file in the project directory
        csv_files = [file for file in files if file.endswith('.csv')]
        if not csv_files:
            st.error("No CSV files found in the project directory")
            return
            
        filename = csv_files[0]  # Use the first CSV file
        file_path = f"{st.session_state.role}/{project_name}/{filename}"
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing data..."):
                if any(keyword in query.lower() for keyword in ['plot', 'graph', 'chart', 'visual', 'visualization']):
                    # Generate visualization
                    try:
                        summary = lida.summarize(file_path, summary_method="default", textgen_config=text_gen_config)
                        charts = lida.visualize(summary=summary, goal=query, textgen_config=text_gen_config)
                        
                        if charts and len(charts) > 0:
                            # Get the first chart
                            chart = charts[0]
                            
                            # Display the chart directly
                            st.image(base64_to_image(chart.raster), caption='Visualization')
                            
                            # Store the entire chart object for later retrieval
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": chart.raster,
                                "is_image": True,
                                "image_type": "lida_chart"  # Add this to indicate the type of image
                            })
                        else:
                            st.warning("No visualizations could be generated")
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": "I couldn't generate a visualization for this query. Could you provide more specific instructions?",
                            })
                    except Exception as e:
                        st.error(f"Error generating visualization: {str(e)}")
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": f"Sorry, I encountered an error while generating the visualization: {str(e)}",
                        })
                else:
                    # Handle regular data queries
                    try:
                        df = pd.read_csv(file_path)
                        pandas_prompt = PromptTemplate(pandas_prompt_str).partial_format(
                            instruction_str=instruction_str, df_str=df.head(5)
                        )
                        pandas_output_parser = PandasInstructionParser(df)
                        response_synthesis_prompt = PromptTemplate(response_synthesis_prompt_str)

                        qp = QP(
                            modules={
                                "input": InputComponent(),
                                "pandas_prompt": pandas_prompt,
                                "llm1": llm,
                                "pandas_output_parser": pandas_output_parser,
                                "response_synthesis_prompt": response_synthesis_prompt,
                                "llm2": llm,
                            },
                            verbose=True,
                        )
                        qp.add_chain(["input", "pandas_prompt", "llm1", "pandas_output_parser"])
                        qp.add_links(
                            [
                                Link("input", "response_synthesis_prompt", dest_key="query_str"),
                                Link("llm1", "response_synthesis_prompt", dest_key="pandas_instructions"),
                                Link("pandas_output_parser", "response_synthesis_prompt", dest_key="pandas_output"),
                            ]
                        )
                        qp.add_link("response_synthesis_prompt", "llm2")
                        
                        response = qp.run(query_str=query)
                        st.markdown(response.message.content)
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": response.message.content
                        })
                    except Exception as e:
                        st.error(f"Error analyzing data: {str(e)}")
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": f"Sorry, I encountered an error while analyzing the data: {str(e)}",
                        })

if __name__ == "__main__":
    visualize()