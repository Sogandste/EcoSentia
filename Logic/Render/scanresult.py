import streamlit as st
from typing import Dict, Any
from UI.Model.Theme import ThemeDict
from .notebox import render_note_box
from ..render import html_safe
from .supportbar import render_support_bar_html


def render_scan_results(snapshot: Dict[str, Any], theme: ThemeDict) -> None:
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Records", snapshot.get("combined_count", 0))
    m2.metric("Direct Matches", snapshot.get("direct_hits", 0))
    m3.metric("Support Level", str(snapshot.get("support_level", "—")).title())

    st.markdown(
        render_support_bar_html(
            str(snapshot.get("support_level", "none")),
            theme["text"],
            theme["border"],
            theme["accent"],
        ),
        unsafe_allow_html=True,
    )

    render_note_box(
        "Evidence Snapshot",
        str(snapshot.get("summary", "No summary available.")),
    )

    top_records = snapshot.get("top_records") if isinstance(snapshot.get("top_records"), list) else []
    top_titles = snapshot.get("top_titles") if isinstance(snapshot.get("top_titles"), list) else []

    if top_records:
        with st.expander("Top Retrieved Titles"):
            for record in top_records:
                record_dict = record if isinstance(record, dict) else {}
                title = str(record_dict.get("title", "Untitled"))
                url = str(record_dict.get("url", ""))
                src = str(record_dict.get("source", "")).title()
                score = record_dict.get("score", "")
                meta = src + (f" · Score: {score}" if score != "" else "")

                if url:
                    st.markdown(f"- [{html_safe(title)}]({url})")
                else:
                    st.write(f"- {title}")
                matched_terms = record_dict.get("matched_terms") if isinstance(record_dict.get("matched_terms"),
                                                                               list) else []
                if matched_terms:
                    st.caption(f"{meta} · Matched: {', '.join(map(str, matched_terms[:4]))}")
    elif top_titles:
        with st.expander("Top Retrieved Titles"):
            for title in top_titles:
                st.write(f"- {title}")
