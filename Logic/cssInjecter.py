
import streamlit as st
import os

DARK_THEME_PATH = os.getenv("DARK_THEME_PATH")
LIGHT_THEME_PATH = os.getenv("LIGHT_THEME_PATH")
BASE_THEME_PATH = os.getenv("BASE_THEME_PATH")


def inject_css(is_dark: bool) -> None:

    themePath = DARK_THEME_PATH if is_dark else LIGHT_THEME_PATH

    with open(themePath, "r", encoding="utf-8") as file:
        css = file.read()
    with open(BASE_THEME_PATH, "r", encoding="utf-8") as file:
        base = file.read()

    st.markdown(
        f"""
        <style>
            {css}
            {base}
        </style>
        """,
        unsafe_allow_html=True
    )