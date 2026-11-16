
import pandas as pd
from UI.Model.Theme import ThemeDict
from ..render import html_safe
import streamlit as st


def render_matrix_table(df: pd.DataFrame, theme: ThemeDict) -> None:
    rows_html = ""
    for _, row in df.iterrows():
        rows_html += f"""
        <tr>
          <td style="font-weight:600;color:{theme['text']};">{html_safe(row['Lens'])}</td>
          <td><span class="badge">{html_safe(row['Support'])}</span></td>
          <td style="color:{theme['text_muted']};font-size:13px;">{html_safe(row['Risks'])}</td>
        </tr>
        """

    st.markdown(
        f"""
        <table class="matrix-table">
          <thead>
            <tr>
              <th style="width:16%;">Lens</th>
              <th style="width:20%;">Support</th>
              <th>Risk Patterns</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table><br>
        """,
        unsafe_allow_html=True,
    )
