from monarch_agent import MonarchAgent
from semantic_scholar_agent import SemanticScholarAgent
from monarch_assistant_2 import MonarchAssistant2
from trafil_agent import TrafilAgent
import agent_smith_ai.streamlit_server as sv
import streamlit as st
import os
import dotenv
dotenv.load_dotenv()          # load env variables defined in .env file (if any)
import plotly.io

### You may wish to create a .streamlit/config.toml file in the same directory as this script
### with contents to adjust the theme:
# [theme]
# base = "light"
# primaryColor = "#4bbdff"



# Render chat message
def _render_message(message):
    current_agent_avatar = st.session_state.agents[st.session_state.current_agent_name].get("avatar", None)
    current_user_avatar = st.session_state.agents[st.session_state.current_agent_name].get("user_avatar", None)

    if message.role == "user":
        with st.chat_message("user", avatar = current_user_avatar):
            st.write(message.content)

    elif message.role == "system":
        with st.chat_message("assistant", avatar="ℹ️"):
            st.write(message.content)

    elif message.role == "assistant" and not message.is_function_call:
        with st.chat_message("assistant", avatar=current_agent_avatar):
            st.write(message.content)

    elif message.role == "streamlit-display":
        with st.chat_message("assistant", avatar="📊"):
            st.write(message.data)

    if st.session_state.show_function_calls:
        if message.is_function_call:
            with st.chat_message("assistant", avatar="🛠️"):
                st.text(f"{message.func_name}(params = {message.func_arguments})")

        elif message.role == "function":
            with st.chat_message("assistant", avatar="✔️"):
                st.text(message.content)


    current_action = "*Thinking...*"

    if message.is_function_call:
        current_action = f"*Checking source ({message.func_name})...*"
    elif message.role == "function":
        current_action = f"*Evaluating result ({message.func_name})...*"

    return current_action
    
sv._render_message = _render_message



# initialize the application and set some page settings
# parameters here are passed to streamlit.set_page_config, see more at https://docs.streamlit.io/library/api-reference/utilities/st.set_page_config
# this function must be run first
sv.initialize_app_config(
    page_title = "Agents",
    #page_icon = "https://avatars.githubusercontent.com/u/5161984?s=200&v=4",
    initial_sidebar_state = "expanded", # or "expanded"
    menu_items = {
            "Get Help": "https://github.com/monarch-initiative/agent-smith-ai/issues",
            "Report a Bug": "https://github.com/monarch-initiative/agent-smith-ai/issues",
            "About": "Agent Smith (AI) is a framework for developing tool-using AI-based chatbots.",
        }
)

# define a function that returns a dictionary of agents to serve
def get_agents():
    return {
        "Monarch Assistant 2": {
            "agent": MonarchAssistant2("Monarch Assistant", model="gpt-4-0613"),
            "greeting": "Hello, I'm the Monarch Assistant.",
            "avatar": "https://avatars.githubusercontent.com/u/5161984?s=200&v=4",
            "user_avatar": "👤",
        },

        "Web Agent": {
            "agent": TrafilAgent("Web Agent", model="gpt-3.5-turbo-16k-0613"),
            "greeting": "Hello, I'm an assistant that can read web pages. My functionality is currently limited to short web pages only.",
            "avatar": "🧑🏻‍💻",
            "user_avatar": "👤",
        },

        # "Monarch Assistant (GPT-4)": {
        #     "agent": MonarchAgent("Monarch Assistant (GPT-4)", model="gpt-4-0613"),
        #     "greeting": "Hello, I'm the Monarch Assistant, based on GPT-4.",
        #     "avatar": "https://avatars.githubusercontent.com/u/5161984?s=200&v=4",
        #     "user_avatar": "👤",
        # }
    }

# tell the app to use that function to create agents when needed
sv.set_app_agents(get_agents)

# set a default API key from an env var; if not set the user will have to input one to chat
#   - users can input their own in the UI to override the default as well
sv.set_app_default_api_key(os.environ["OPENAI_API_KEY"])

# start the app
sv.serve_app()
