from monarch_agent import MonarchAgent
from semantic_scholar_agent import SemanticScholarAgent
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
        "Semantic Scholar": {
            "agent": SemanticScholarAgent("Semantic Scholar", model="gpt-3.5-turbo-16k-0613"),
            "greeting": "Hello, I'm the Semantic Scholar Assistant.",
            "avatar": "data:image/png;base64,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",
            "user_avatar": "👤",
        },
        "Monarch Assistant (GPT-4)": {
            "agent": MonarchAgent("Monarch Assistant (GPT-4)", model="gpt-4-0613"),
            "greeting": "Hello, I'm the Monarch Assistant, based on GPT-4.",
            "avatar": "https://avatars.githubusercontent.com/u/5161984?s=200&v=4",
            "user_avatar": "👤",
        }
    }

# tell the app to use that function to create agents when needed
sv.set_app_agents(get_agents)

# set a default API key from an env var; if not set the user will have to input one to chat
#   - users can input their own in the UI to override the default as well
sv.set_app_default_api_key(os.environ["OPENAI_API_KEY"])

# start the app
sv.serve_app()
