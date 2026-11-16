
import streamlit as st
from UI.Model.Theme import ThemeDict
from ..session import ensure_session_defaults
import json
from ..state import invalidate_panel_state
from Logic.api import api_post, add_history_entry
from Logic.Render.notebox import render_note_box
from .scanresult import render_scan_results
from Logic.Builder.basePayload import build_base_payload
from .promptResult import render_prompt_results
from ..Render.reportExport import render_report_exports
from ..Extracter.refinedQuery import extract_refined_query
from ..Extracter.scanPayload import extract_scan_payload
from ..Render.matrixTable import render_matrix_table
from ..Builder.matrixDataFrame import build_matrix_dataframe
from ..Extracter.promptPayLoad import extract_prompts_payload
from ..Extracter.lensMatrix import extract_lens_matrix


def render_panel(
        pid: str,
        claim_text: str,
        domain_mode: str,
        lens_ui: str,
        source: str,
        max_results: int,
        bio_model: str,
        trg_func: str,
        app_ctx: str,
        mech_kw: str,
        excl_kw: str,
        theme: ThemeDict,
        comparison_layout: bool = False,
) -> None:
    ensure_session_defaults()
    keys = invalidate_panel_state(pid, claim_text, st.session_state)

    payload_base = build_base_payload(
        pid=pid,
        claim_text=claim_text,
        domain_mode=domain_mode,
        lens_ui=lens_ui,
        source=source,
        max_results=max_results,
        bio_model=bio_model,
        trg_func=trg_func,
        app_ctx=app_ctx,
        mech_kw=mech_kw,
        excl_kw=excl_kw,
    )

    st.divider()

    st.markdown("### Step 1: Refine Search Query")
    st.caption("Builds a literature-oriented query from the current claim and configuration.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button(
                "Refine Query",
                key=f"refine_btn_{pid}",
                use_container_width=True,
        ):
            with st.spinner("Refining query..."):
                try:
                    response = api_post("/evidence/refine-query", payload_base)
                    refined_query = extract_refined_query(response, claim_text)
                    st.session_state[keys["refined_query"]] = refined_query
                    st.session_state[keys["active_query"]] = refined_query
                except Exception as exc:
                    render_note_box("Refine Query Error", str(exc))

    with c2:
        if st.button(
                "Use Claim As Query",
                key=f"use_claim_btn_{pid}",
                use_container_width=True,
        ):
            st.session_state[keys["refined_query"]] = claim_text
            st.session_state[keys["active_query"]] = claim_text

    if keys["active_query"] not in st.session_state:
        st.session_state[keys["active_query"]] = st.session_state.get(keys["refined_query"], claim_text)

    st.text_area(
        "Active Query",
        key=keys["active_query"],
        height=100,
    )
    q_text = str(st.session_state.get(keys["active_query"], claim_text))

    st.divider()

    st.markdown("### Step 2: Run Evidence Scan")
    st.caption("Queries the selected literature source and builds an evidence snapshot.")

    if st.button(
            "Execute Scan",
            key=f"scan_btn_{pid}",
            use_container_width=True,
    ):
        with st.spinner("Querying scientific literature..."):
            try:
                response = api_post("/evidence/scan", {**payload_base, "query_text": q_text})
                snapshot, query_used = extract_scan_payload(response, q_text)

                st.session_state[keys["scan"]] = {
                    "raw": response,
                    "snapshot": snapshot,
                    "query_text": query_used,
                }

                add_history_entry(
                    claim=claim_text,
                    lens=lens_ui,
                    support_level=str(snapshot.get("support_level", "none")),
                )
            except Exception as exc:
                render_note_box("Scan Error", str(exc))

    if keys["scan"] in st.session_state:
        scan_state = st.session_state[keys["scan"]] if isinstance(st.session_state[keys["scan"]], dict) else {}
        snapshot = scan_state.get("snapshot") if isinstance(scan_state.get("snapshot"), dict) else {}

        if comparison_layout:
            with st.container(height=360):
                render_scan_results(snapshot, theme)
        else:
            render_scan_results(snapshot, theme)

    st.divider()

    st.markdown("### Step 3: Generate Evidence-Aware Prompts")
    st.caption("Turns the current evidence state into reusable LLM prompts.")

    if keys["scan"] not in st.session_state:
        render_note_box("Step Incomplete", "Please complete Step 2 before generating prompts.")
    else:
        if st.button(
                "Generate Prompts",
                key=f"prompts_btn_{pid}",
                use_container_width=True,
        ):
            with st.spinner("Generating prompts..."):
                try:
                    scan_state = st.session_state[keys["scan"]] if isinstance(st.session_state[keys["scan"]], dict) else {}
                    payload_prompts = {
                        "preset": domain_mode.lower(),
                        "lens": lens_ui.lower(),
                        "claim": claim_text,
                        "query_text": str(scan_state.get("query_text", q_text)),
                        "snapshot": scan_state.get("snapshot") if isinstance(scan_state.get("snapshot"),
                                                                                     dict) else {},
                    }
                    response = api_post("/evidence/prompts", payload_prompts)
                    prompts = extract_prompts_payload(response)
                    st.session_state[keys["prompts"]] = prompts
                except Exception as exc:
                    render_note_box("Prompt Generation Error", str(exc))

        if keys["prompts"] in st.session_state:
            prompts = st.session_state[keys["prompts"]] if isinstance(st.session_state[keys["prompts"]], dict) else {}

            if comparison_layout:
                with st.container(height=620):
                    render_prompt_results(prompts, theme)
            else:
                render_prompt_results(prompts, theme)

    st.divider()

    st.markdown("### Step 4: Full Multi-Lens Audit")
    st.caption("Produces a multi-lens summary suitable for export and reporting.")

    if st.button(
            "Execute Full Audit",
            key=f"audit_btn_{pid}",
            use_container_width=True,
    ):
        with st.spinner("Scanning all lenses..."):
            try:
                response = api_post(
                    "/evidence/scan-all-lenses",
                    {**payload_base, "query_text": q_text},
                )
                matrix = extract_lens_matrix(response)
                st.session_state[keys["matrix"]] = matrix
            except Exception as exc:
                render_note_box("Audit Error", str(exc))

    if keys["matrix"] in st.session_state:
        matrix = st.session_state[keys["matrix"]] if isinstance(st.session_state[keys["matrix"]], dict) else {}
        df, _ = build_matrix_dataframe(matrix)

        def render_matrix_block() -> None:
            st.markdown("#### Analytical Lens Matrix")
            render_matrix_table(df, theme)

            d1, d2 = st.columns(2)

            with d1:
                st.download_button(
                    "Download CSV",
                    df.to_csv(index=False).encode("utf-8"),
                    f"ecosentia_matrix_{pid}.csv",
                    "text/csv",
                    key=f"csv_btn_{pid}",
                    use_container_width=True,
                )

            with d2:
                st.download_button(
                    "Download JSON",
                    json.dumps(
                        [
                            {
                                "lens": row["Lens"],
                                "support": row["Support"],
                                "risks": row["Risks"],
                            }
                            for _, row in df.iterrows()
                        ],
                        indent=2,
                        ensure_ascii=False,
                    ).encode("utf-8"),
                    f"ecosentia_matrix_{pid}.json",
                    "application/json",
                    key=f"json_btn_{pid}",
                    use_container_width=True,
                )

        if comparison_layout:
            with st.container(height=360):
                render_matrix_block()
        else:
            render_matrix_block()

    st.divider()

    if comparison_layout:
        with st.container(height=180):
            render_report_exports(pid)
    else:
        render_report_exports(pid)