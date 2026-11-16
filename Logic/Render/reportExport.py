import streamlit as st
import json
from Logic.state import get_panel_state
from ..Builder.reportHTML import build_report_html


def render_report_exports(pid: str) -> None:
    """
    Render complete report export controls for the current panel.
    """
    report = get_panel_state(pid, st.session_state)
    report_html = build_report_html(report)
    report_json = json.dumps(report, indent=2, ensure_ascii=False)

    st.markdown("### Export Complete Report")
    st.caption(
        "Exports all available outputs from this panel, including claim, query, evidence snapshot, prompts, risks, and multi-lens audit."
    )

    e1, e2, e3 = st.columns(3)

    with e1:
        st.download_button(
            "Download Complete HTML Report",
            data=report_html.encode("utf-8"),
            file_name=f"ecosentia_checkpoint_report_{pid}.html",
            mime="text/html",
            key=f"html_report_btn_{pid}",
            use_container_width=True,
        )

    with e2:
        st.download_button(
            "Download Complete JSON Report",
            data=report_json.encode("utf-8"),
            file_name=f"ecosentia_checkpoint_report_{pid}.json",
            mime="application/json",
            key=f"json_report_btn_{pid}",
            use_container_width=True,
        )