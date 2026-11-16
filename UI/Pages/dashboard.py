import streamlit as st
from ..Claim.Compare import DEFAULT_COMPARE_CLAIMS
from ..Claim.Default import DEFAULT_CLAIMS
from Logic.api import get_api_health
from ..Style.darkTheme import darkDict
from ..Style.lightTheme import lightDict
from ..Model.Theme import ThemeDict
from Logic.cssInjecter import inject_css
from Logic.Render.sidebar import render_sidebar
from Logic.Render.header import render_header
from Logic.Render.panel import render_panel


def get_theme(dark_mode: bool) -> ThemeDict:
    return darkDict if dark_mode else lightDict


def dashboard():
    if st.session_state.guide_completed:
        api_health = get_api_health()
        theme = get_theme(st.session_state.dark_mode)

        inject_css(st.session_state.dark_mode)
        render_sidebar(api_health, theme)
        render_header(st.session_state.dark_mode)

        st.markdown("### Configuration")

        c1, c2 = st.columns(2)
        with c1:
            domain_mode = st.radio(
                "Preset",
                ["Fog", "EV", "Custom"],
                horizontal=True,
            )
        with c2:
            lens_ui = st.selectbox(
                "Evaluation Lens",
                ["Mechanism", "Context", "Scale", "Manufacturability", "Safety"],
            )

        c3, c4 = st.columns(2)
        with c3:
            source = st.radio(
                "Literature Source",
                ["Both", "PubMed", "OpenAlex"],
                horizontal=True,
            )
        with c4:
            max_results = st.slider(
                "Max Results Per Source",
                1,
                10,
                5,
            )

        bio_model = ""
        trg_func = ""
        app_ctx = ""
        mech_kw = ""
        excl_kw = ""

        if domain_mode == "Custom":
            with st.expander("Custom Guidance", expanded=True):
                x1, x2 = st.columns(2)
                with x1:
                    bio_model = st.text_input(
                        "Biological Model",
                        placeholder="e.g., Gecko, Mussel",
                    )
                    app_ctx = st.text_input(
                        "Application Context",
                        placeholder="e.g., Wet biomedical surfaces",
                    )
                with x2:
                    trg_func = st.text_input(
                        "Target Function",
                        placeholder="e.g., Reversible adhesion",
                    )
                    mech_kw = st.text_input(
                        "Mechanism Keywords",
                        placeholder="e.g., microstructure, van der Waals",
                    )
                excl_kw = st.text_input(
                    "Exclude Terms",
                    placeholder="e.g., vaccine, remote sensing",
                )

        if not st.session_state.compare_mode:
            claim_main = st.text_area(
                "Design Claim",
                value=DEFAULT_CLAIMS.get(domain_mode, ""),
                height=120,
            )
            render_panel(
                pid="main",
                claim_text=claim_main,
                domain_mode=domain_mode,
                lens_ui=lens_ui,
                source=source,
                max_results=max_results,
                bio_model=bio_model,
                trg_func=trg_func,
                app_ctx=app_ctx,
                mech_kw=mech_kw,
                excl_kw=excl_kw,
                theme=theme,
            )
        else:
            left, right = st.columns(2)

            default_a, default_b = DEFAULT_COMPARE_CLAIMS.get(
                domain_mode,
                DEFAULT_COMPARE_CLAIMS["Custom"],
            )

            with left:
                st.markdown("### Panel A")
                claim_a = st.text_area(
                    "Design Claim A",
                    value=default_a,
                    height=120,
                    key=f"claim_a_{domain_mode}",
                )
                render_panel(
                    pid="A",
                    claim_text=claim_a,
                    domain_mode=domain_mode,
                    lens_ui=lens_ui,
                    source=source,
                    max_results=max_results,
                    bio_model=bio_model,
                    trg_func=trg_func,
                    app_ctx=app_ctx,
                    mech_kw=mech_kw,
                    excl_kw=excl_kw,
                    theme=theme,
                    comparison_layout=True,
                )

            with right:
                st.markdown("### Panel B")
                claim_b = st.text_area(
                    "Design Claim B",
                    value=default_b,
                    height=120,
                    key=f"claim_b_{domain_mode}",
                )
                render_panel(
                    pid="B",
                    claim_text=claim_b,
                    domain_mode=domain_mode,
                    lens_ui=lens_ui,
                    source=source,
                    max_results=max_results,
                    bio_model=bio_model,
                    trg_func=trg_func,
                    app_ctx=app_ctx,
                    mech_kw=mech_kw,
                    excl_kw=excl_kw,
                    theme=theme,
                    comparison_layout=True,
                )

