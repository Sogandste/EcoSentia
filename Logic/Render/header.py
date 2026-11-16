import streamlit as st
import os

HTML_DARK_HEADER_PATH = os.getenv("HTML_DARK_HEADER_PATH")
HTML_LIGHT_HEADER_PATH = os.getenv("HTML_LIGHT_HEADER_PATH")


def render_header(is_dark: bool) -> None:
    themePath = HTML_DARK_HEADER_PATH if is_dark else HTML_LIGHT_HEADER_PATH

    with open(themePath, "r", encoding="utf-8") as file:
        darkHeader = file.read()

    st.markdown(
        darkHeader,
        unsafe_allow_html=True
    )