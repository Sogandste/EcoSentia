import streamlit as st
from html import escape


def render_note_box(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="note-box">
          <div class="note-title">{escape("" if title is None else str(title))}</div>
          <div class="note-body">{escape("" if body is None else str(body))}</div>
        </div>
        """,
        unsafe_allow_html=True,

    )
