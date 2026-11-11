import streamlit as st
import requests
from typing import cast
from .sessionConfig import defaults


def get_http_session() -> requests.Session:
    if "_http_session" not in st.session_state:
        st.session_state["_http_session"] = requests.Session()
    return cast(requests.Session, st.session_state["_http_session"])


def ensure_session_defaults() -> None:
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

