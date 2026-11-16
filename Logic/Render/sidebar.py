
import streamlit as st
from UI.Model.Theme import ThemeDict
from typing import cast, List
from UI.Model.History import HistoryEntry
from ..render import html_safe


def render_sidebar(api_health: str, theme: ThemeDict) -> None:
    with st.sidebar:
        st.markdown("## Appearance")
        theme_mode = st.selectbox(
            "Theme",
            ["Dark", "Light"],
            index=0 if st.session_state.dark_mode else 1,
        )
        desired_dark = theme_mode == "Dark"
        if desired_dark != st.session_state.dark_mode:
            st.session_state.dark_mode = desired_dark
            st.rerun()

        st.divider()

        st.markdown("## Tools")
        compare_toggle = st.toggle(
            "Claim Comparison Mode",
            value=st.session_state.compare_mode,
        )
        if compare_toggle != st.session_state.compare_mode:
            st.session_state.compare_mode = compare_toggle
            st.rerun()

        st.divider()

        st.markdown("## Recent Scans")
        history = cast(List[HistoryEntry], st.session_state["history"])
        if history:
            for h in history:
                st.markdown(
                    f"""
                    <div style="padding:9px 11px;margin-bottom:8px;border-radius:10px;
                                border:1px solid {theme['accent']};background:{theme['panel']};">
                      <div style="font-size:11px;font-weight:600;color:{theme['text_muted']};">
                        {html_safe(h['time'])} · {html_safe(h['lens']).title()}
                      </div>
                      <div style="font-size:12px;margin-top:4px;color:{theme['text']};line-height:1.45;">
                        {html_safe(h['claim'])}
                      </div>
                      <div style="margin-top:7px;">
                        <span style="font-size:10px;padding:2px 8px;border-radius:999px;
                                     color:{theme['accent']};border:1px solid {theme['accent']};
                                     background:{theme['accent_bg']};">
                          {html_safe(h['support']).title()}
                        </span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No scans recorded yet.")

        st.divider()
        st.markdown(
            "## About\n"
            "EcoSentia evaluates biomimetic design claims against peer-reviewed "
            "literature, surfaces translation risks, and generates evidence-aware prompts."
        )
        st.caption(api_health)
