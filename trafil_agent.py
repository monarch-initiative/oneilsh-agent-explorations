from agent_smith_ai.utility_agent import UtilityAgent
from agent_smith_ai.models import Message

import streamlit as st
import textwrap
import os
from typing import Any, Dict
import trafilatura
import pandas as pd
from tabulate import tabulate
import plotly.io
import json


class StreamlitMessage(Message):
    data: Any = None


## A UtilityAgent can call API endpoints and local methods
class TrafilAgent(UtilityAgent):

    def __init__(self, name, model = "gpt-3.5-turbo-16k-0613", openai_api_key = None):
        
        ## define a system message
        system_message = textwrap.dedent(f"""You are able to read and parse web pages.""").strip()
        
        super().__init__(name,                                             # Name of the agent
                         system_message,                                   # Openai system message
                         model = model,                     # Openai model name
                         openai_api_key = openai_api_key,    # API key; will default to OPENAI_API_KEY env variable
                         auto_summarize_buffer_tokens = 500,               # Summarize and clear the history when fewer than this many tokens remains in the context window. Checked prior to each message sent to the model.
                         summarize_quietly = False,                        # If True, do not alert the user when a summarization occurs
                         max_tokens = None,                                # maximum number of tokens this agent can bank (default: None, no limit)
                         token_refill_rate = 50000.0 / 3600.0)             # number of tokens to add to the bank per second


    ## define a local method
        self.register_callable_functions({"parse_url": self.parse_url, "plotly_from_json": self.plotly_from_json})


    def parse_url(self, url: str) -> str:
        """Parse a URL into a string of text.
        
        Args:
            url (str): URL to parse.
            
        Returns:
            str: Parsed text.
        """
        result = trafilatura.fetch_url(url)
        return trafilatura.extract(result)

    def send_to_ui(self, data: Any) -> None:
        """Send data to the UI, rending it in the chat stream with st.write(). 
        This could be a plotly plot, a pandas dataframe, etc. It does not get appended
        to the agent's history, and is only visible to the user.

        Args:
            data (Any): Data to send to the UI.
        
        Returns:
            None
        """
        st.session_state.agents[st.session_state.current_agent_name]["messages"].append(StreamlitMessage(role = "streamlit-display", data = data))


    def plotly_from_json(self, json_data: str) -> str:
        """Render a plotly figure from a JSON string.
        
        Args:
            json_data: JSON data to render using plotly's from_json method, provided as a string.
            
        Returns:
            str: Success or failure message and further instructions.
        """
        fig = plotly.io.from_json(json_data)
        self.send_to_ui(fig)
        return "Success. The user has been shown the plot, be sure to describe what they are seeing."

