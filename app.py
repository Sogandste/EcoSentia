# app.py
"""
EcoSentia Evidence Studio - Streamlit frontend.
Fixes applied in this version:
- PDF generation cached in session_state to prevent re-execution on every rerun
- Health check cached in session_state to prevent a network call on every rerun
- preset_ui redundant variable removed; domain_mode used directly
- q_text state conflict resolved: value no longer written back manually to session_state
- pdf_cache_k added to the claim-change reset list
- compare_mode uses st.toggle with key to avoid manual sync
"""

import os
import requests
import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF

API_BASE = os.getenv("ECOSENTIA_API_URL", "https://ecosentia.onrender.com")


# ---------------------------------------------------------------------------
# API communication
# ---------------------------------------------------------------------------

def api_post(path: str, payload: dict) -> dict:
    """
    POST to the backend API.
    Parses structured error details from FastAPI HTTPException responses.
    Raises RuntimeError with a readable message for the UI layer to display.
    """
    try:
        resp = requests.post(f"{API_BASE}{path}", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text if e.response is not None else str(e)
        raise RuntimeError(f"API error at {path}: {detail}")
    except requests.RequestException as e:
        raise RuntimeError(f"Connection error at {path}: {e}")


# ---------------------------------------------------------------------------
# PDF utilities
# ---------------------------------------------------------------------------

def pdf_safe(text) -> str:
    """
    Sanitize a string for fpdf2 latin-1 output.
    Replaces common Unicode typographic characters with ASCII equivalents
    to prevent encoding errors during PDF generation.
    """
    if not text:
        return ""
    replacements = {
        "\u2014": "-", "\u2013": "-",
        "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'",
        "\u2022": "-", "\u2026": "...",
        "\u00a0": " ",
    }
    s = str(text)
    for bad, good in replacements.items():
        s = s.replace(bad, good)
    return s.encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf(claim, lens, preset, snap, prompts, mx) -> bytes:
    """
    Produce a structured PDF evidence report.
    Handles both old (dest='S') and new (no argument) fpdf2 output signatures.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=12)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, pdf_safe("EcoSentia - Evidence Report"), ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0, 6,
        pdf_safe(
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')} "
            f"| Domain: {preset} | Lens: {lens}"
        ),
        ln=True,
    )
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, pdf_safe("Design Claim"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, pdf_safe(claim))
    pdf.ln(4)

    if snap:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, pdf_safe("Evidence Scan Snapshot"), ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(
            0, 6,
            pdf_safe(
                f"Records: {snap.get('combined_count', 0)} | "
                f"Direct Matches: {snap.get('direct_hits', 0)} | "
                f"Support: {snap.get('support_level', 'none').title()}"
            ),
            ln=True,
        )
        pdf.multi_cell(0, 6, pdf_safe(f"Summary: {snap.get('summary', '')}"))
        pdf.ln(4)

    if prompts:
        for title, key in [
            ("Master Prompt", "master_prompt"),
            ("Counter Prompt", "counter_prompt"),
            ("Uncertainty Mapping", "uncertainty_prompt"),
            ("Redesign Prompt", "redesign_prompt"),
        ]:
            val = prompts.get(key, "")
            if val:
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(0, 6, pdf_safe(title), ln=True)
                pdf.set_font("Courier", "", 8)
                pdf.multi_cell(0, 5, pdf_safe(val))
                pdf.ln(3)

    if mx:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, pdf_safe("Multi-Lens Audit"), ln=True)
        pdf.set_font("Helvetica", "", 10)
        for lens_name, result in mx.items():
            if "error" in result:
                line = f"{lens_name.title()}: Error - {result['error']}"
            else:
                risks = result.get("detected_biases", [])
                risk_str = (
                    ", ".join(
                        b.get("bias", "") if isinstance(b, dict) else str(b)
                        for b in risks
                    )
                    if risks
                    else "None"
                )
                line = (
                    f"{lens_name.title()}: "
                    f"{result.get('support_level', 'none').title()} "
                    f"| Risks: {risk_str}"
                )
            pdf.multi_cell(0, 6, pdf_safe(line))

    try:
        raw = pdf.output()
    except TypeError:
        raw = pdf.output(dest="S")
    return bytes(raw) if not isinstance(raw, bytes) else raw


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="EcoSentia", layout="wide", page_icon="▪")


# ---------------------------------------------------------------------------
# 1. Theme state and sidebar
# ---------------------------------------------------------------------------

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "compare_mode" not in st.session_state:
    st.session_state.compare_mode = False

with st.sidebar:
    st.markdown("## ◒ Appearance")
    is_dark = st.toggle("Dark Mode", value=st.session_state.dark_mode)
    if is_dark != st.session_state.dark_mode:
        st.session_state.dark_mode = is_dark
        st.rerun()

    st.markdown("## ◫ Layout")
    st.toggle(
        "Compare Mode",
        key="compare_mode",
        help="Evaluate two claims side-by-side.",
    )

    st.divider()
    st.markdown(
        "## ⌗ About\nEcoSentia evaluates biomimetic design claims against literature."
    )

dm = st.session_state.dark_mode


# ---------------------------------------------------------------------------
# 2. Symmetrical palette
# ---------------------------------------------------------------------------

if dm:
    T = {
        "bg":     "#0f172a",
        "panel":  "#1e293b",
        "text":   "#f8fafc",
        "border": "#334155",
        "hover":  "#475569",
        "icon":   "#f8fafc",
    }
else:
    T = {
        "bg":     "#f8fafc",
        "panel":  "#ffffff",
        "text":   "#0f172a",
        "border": "#cbd5e1",
        "hover":  "#f1f5f9",
        "icon":   "#0f172a",
    }


# ---------------------------------------------------------------------------
# 3. Deep CSS architecture
# ---------------------------------------------------------------------------

st.markdown(f"""
<style>
/* Base */
.stApp, .main {{ background-color: {T['bg']} !important; }}
[data-testid="stSidebar"] {{
    background-color: {T['panel']} !important;
    border-right: 1px solid {T['border']};
}}
p, span, h1, h2, h3, h4, label, div {{ color: {T['text']} !important; }}

/* Inputs */
input, textarea, div[data-baseweb="select"] > div {{
    background-color: {T['panel']} !important;
    color: {T['text']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 6px !important;
}}

/* Dropdown caret fix */
div[data-baseweb="select"] svg {{
    fill: {T['icon']} !important;
    color: {T['icon']} !important;
}}

/* Dropdown list */
div[data-baseweb="popover"],
div[data-baseweb="popover"] > div {{
    background-color: {T['panel']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 6px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
}}
ul[data-baseweb="menu"],
ul[role="listbox"] {{ background-color: {T['panel']} !important; }}
li[role="option"] {{
    background-color: {T['panel']} !important;
    color: {T['text']} !important;
}}
li[role="option"]:hover,
li[aria-selected="true"] {{ background-color: {T['hover']} !important; }}

/* Tooltips - always dark for maximum readability */
[data-testid="stTooltipContent"],
div[role="tooltip"],
div[data-baseweb="tooltip"] > div {{
    background-color: #111827 !important;
    color: #ffffff !important;
    border: 1px solid #374151 !important;
    border-radius: 6px !important;
    padding: 8px 12px !important;
}}
[data-testid="stTooltipContent"] * {{
    color: #ffffff !important;
    font-size: 13px !important;
}}

/* Panels, expanders, metrics */
[data-testid="metric-container"], details, .stCodeBlock {{
    background-color: {T['panel']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 6px !important;
}}
details summary, details div {{ background-color: {T['panel']} !important; }}
code, pre {{ background-color: {T['hover']} !important; border: none !important; }}
hr {{ border-color: {T['border']} !important; opacity: 0.6; }}

/* Alert boxes */
[data-testid="stAlert"] {{
    background-color: {T['panel']} !important;
    border: 1px solid {T['border']} !important;
}}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 4. Dynamic vector logo
# ---------------------------------------------------------------------------

st.markdown(f"""
<div style="display:flex; align-items:center; gap:15px; margin-bottom:20px;">
  <svg width="65" height="65" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <radialGradient id="g" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="rgba(99,102,241,0.4)"/>
        <stop offset="100%" stop-color="rgba(99,102,241,0)"/>
      </radialGradient>
      <style>
        .aura {{
            animation: p 3.5s infinite alternate ease-in-out;
            transform-origin: center;
        }}
        @keyframes p {{
            0%   {{ transform: scale(0.8); opacity: 0.4; }}
            100% {{ transform: scale(1.1); opacity: 1;   }}
        }}
        .hm {{
            fill: none;
            stroke: {T['text']};
            stroke-width: 3.5;
            stroke-linecap: round;
            stroke-linejoin: round;
        }}
        .lf {{
            fill: none;
            stroke: #10b981;
            stroke-width: 3;
            stroke-linecap: round;
            stroke-linejoin: round;
        }}
      </style>
    </defs>
    <circle class="aura" cx="50" cy="45" r="35" fill="url(#g)"/>
    <path  class="lf" d="M50 85 C80 80, 85 45, 50 15 C65 40, 65 65, 50 85 Z"/>
    <line  class="hm" x1="50" y1="35" x2="50" y2="85"/>
    <path  class="hm" d="M30 25 L70 25 L60 35 L40 35 Z"/>
    <circle cx="50" cy="15" r="3.5" fill="#6366f1"/>
  </svg>
  <div>
    <div style="font-size:30px; font-weight:300; letter-spacing:2px;
                color:{T['text']}; line-height:1.1;">EcoSentia</div>
    <div style="font-size:11.5px; letter-spacing:1px; opacity:0.65;
                color:{T['text']}; margin-top:4px;">EVIDENCE STUDIO · V0.3</div>
  </div>
</div>
""", unsafe_allow_html=True)
st.divider()


# ---------------------------------------------------------------------------
# API health check — cached for the lifetime of the session.
# Previously this fired a network request on every single rerun
# (theme toggle, slider move, etc.), which added latency to every interaction.
# ---------------------------------------------------------------------------

if "api_health" not in st.session_state:
    try:
        h = requests.get(f"{API_BASE}/health", timeout=10).json()
        st.session_state["api_health"] = (
            f"API Connected · {h.get('service', 'EcoSentia API')} "
            f"· v{h.get('version', '')}"
        )
    except Exception:
        st.session_state["api_health"] = f"API Not Reachable · {API_BASE}"

st.caption(st.session_state["api_health"])


# ---------------------------------------------------------------------------
# 5. Global configuration
# ---------------------------------------------------------------------------

st.markdown("#### Configuration")
c1, c2 = st.columns(2)
with c1:
    domain_mode = st.selectbox(
        "Preset",
        ["Fog", "EV", "Custom"],
        help="Select a domain logic preset.",
    )
with c2:
    lens_ui = st.selectbox(
        "Evaluation Lens",
        ["Mechanism", "Context", "Scale", "Manufacturability", "Safety"],
        help="Choose analytical perspective.",
    )

c3, c4 = st.columns(2)
with c3:
    source = st.selectbox(
        "Literature Source",
        ["Both", "PubMed", "OpenAlex"],
        help="Databases to search.",
    )
with c4:
    max_results = st.slider(
        "Max Results Per Source", 1, 10, 5,
        help="Limit to avoid API timeouts.",
    )

# Custom guidance fields — only shown when Custom preset is selected
bio_model = trg_func = app_ctx = mech_kw = excl_kw = ""
if domain_mode == "Custom":
    with st.expander("◧ Custom Guidance (Optional but Recommended)", expanded=True):
        xc1, xc2 = st.columns(2)
        with xc1:
            bio_model = st.text_input("Biological Model",       placeholder="e.g., Gecko, Mussel")
            app_ctx   = st.text_input("Application Context",    placeholder="e.g., Wet biomedical surfaces")
        with xc2:
            trg_func  = st.text_input("Target Function",        placeholder="e.g., Reversible adhesion")
            mech_kw   = st.text_input("Mechanism Keywords",     placeholder="e.g., microstructure")
        excl_kw = st.text_input("Exclude Terms",                placeholder="e.g., vaccine, remote sensing")

st.divider()


# ---------------------------------------------------------------------------
# Panel renderer
# ---------------------------------------------------------------------------

def render_panel(pid: str, claim_text: str):
    """
    Render a complete four-step evaluation workflow for a single claim.
    pid (Panel ID) namespaces all session_state keys so that two panels
    (compare mode) operate independently with no state bleed between them.
    """
    qk           = f"refined_query_{pid}"
    scan_k       = f"scan_{pid}"
    prompts_k    = f"prompts_{pid}"
    matrix_k     = f"lens_matrix_{pid}"
    claim_cache_k = f"claim_cache_{pid}"
    pdf_cache_k  = f"pdf_cache_{pid}"

    # Invalidate downstream results whenever the claim text changes.
    # pdf_cache_k is included so a stale PDF is never served for a new claim.
    if st.session_state.get(claim_cache_k) != claim_text:
        st.session_state[claim_cache_k] = claim_text
        for k in [scan_k, prompts_k, matrix_k, pdf_cache_k]:
            if k in st.session_state:
                del st.session_state[k]

    # Base payload shared by all API calls in this panel
    pld = {
        "session_id":          f"main_session_{pid}",
        "preset":              domain_mode.lower(),
        "domain_mode":         domain_mode,
        "project":             "",
        "claim":               claim_text,
        "lens":                lens_ui.lower(),
        "source":              source,
        "max_results":         max_results,
        "biological_model":    bio_model,
        "target_function":     trg_func,
        "application_context": app_ctx,
        "mechanism_keywords":  mech_kw,
        "exclude_terms":       excl_kw,
    }

    # ── Step 1 : Refine Search Query ──────────────────────────────────────────
    st.subheader(
        "Step 1: Refine Search Query",
        help="Translates the design claim into Boolean operators.",
    )
    b1, b2 = st.columns(2)

    with b1:
        if st.button("Refine Query", key=f"ref_btn_{pid}", use_container_width=True):
            with st.spinner("Refining..."):
                try:
                    st.session_state[qk] = api_post(
                        "/evidence/refine-query", pld
                    )["refined_query"]
                    st.success("Query Refined.", icon="✓")
                except Exception as e:
                    st.error(f"Error: {e}", icon="✕")

    with b2:
        if st.button("Use Claim", key=f"use_claim_{pid}", use_container_width=True):
            st.session_state[qk] = claim_text

    # q_text state management:
    # Using only `key` (not `value`) lets Streamlit own the widget state.
    # We seed the key once from qk if it has not been set yet,
    # then read back from the widget's own key to avoid the
    # dual-write conflict that caused StreamlitAPIException in 1.30+.
    if f"active_query_{pid}" not in st.session_state:
        st.session_state[f"active_query_{pid}"] = st.session_state.get(qk, "")

    st.text_area(
        "Active Query",
        height=80,
        help="Editable Boolean query.",
        key=f"active_query_{pid}",
    )
    q_text = st.session_state[f"active_query_{pid}"]
    st.divider()

    # ── Step 2 : Run Evidence Scan ────────────────────────────────────────────
    st.subheader(
        "Step 2: Run Evidence Scan",
        help="Searches databases using the Active Query.",
    )
    if st.button("Execute Scan", key=f"scan_btn_{pid}"):
        with st.spinner("Querying..."):
            try:
                data = api_post("/evidence/scan", {**pld, "query_text": q_text})
                st.session_state[scan_k] = data
                # Invalidate PDF cache when a new scan arrives
                if pdf_cache_k in st.session_state:
                    del st.session_state[pdf_cache_k]
                st.success("Scan Complete.", icon="✓")
            except Exception as e:
                st.error(f"Error: {e}", icon="✕")

    if scan_k in st.session_state:
        snap = st.session_state[scan_k]["snapshot"]

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Records",  snap.get("combined_count", 0))
        m2.metric("Direct Matches", snap.get("direct_hits", 0))
        m3.metric("Support Level",  snap.get("support_level", "—").title())

        st.info(snap.get("summary", "No summary available."), icon="▪")

        if snap.get("top_records"):
            with st.expander("Top Retrieved Titles"):
                for r in snap["top_records"]:
                    t_title = r.get("title", "Untitled")
                    t_url   = r.get("url", "")
                    t_src   = r.get("source", "").title()
                    t_score = r.get("score", "")
                    meta = t_src + (f" · Score: {t_score}" if t_score != "" else "")
                    if t_url:
                        st.markdown(f"- [{t_title}]({t_url})")
                    else:
                        st.write(f"- {t_title}")
                    if r.get("matched_terms"):
                        st.caption(f"{meta} · Matched: {', '.join(r['matched_terms'][:4])}")
        elif snap.get("top_titles"):
            with st.expander("Top Retrieved Titles"):
                for t in snap["top_titles"]:
                    st.write(f"- {t}")

    st.divider()

    # ── Step 3 : Generate Evidence-Aware Prompts ──────────────────────────────
    st.subheader(
        "Step 3: Generate Evidence-Aware Prompts",
        help="Builds structured LLM prompts based on the retrieved evidence.",
    )
    if scan_k not in st.session_state:
        st.warning("Please complete Step 2 first.", icon="⚠")
    else:
        if st.button("Generate Prompts", key=f"prompts_btn_{pid}"):
            with st.spinner("Generating..."):
                try:
                    payload_prompts = {
                        "preset":     domain_mode.lower(),
                        "lens":       lens_ui.lower(),
                        "claim":      claim_text,
                        "query_text": st.session_state[scan_k]["query_text"],
                        "snapshot":   st.session_state[scan_k]["snapshot"],
                    }
                    st.session_state[prompts_k] = api_post(
                        "/evidence/prompts", payload_prompts
                    )["prompts"]
                    # Invalidate PDF cache when prompts are regenerated
                    if pdf_cache_k in st.session_state:
                        del st.session_state[pdf_cache_k]
                except Exception as e:
                    st.error(f"Error: {e}", icon="✕")

        if prompts_k in st.session_state:
            p   = st.session_state[prompts_k]
            lvl = p.get("support_level", "none")

            if lvl == "none":
                st.error(
                    f"**Support: {lvl.title()}**\n\n{p.get('evidence_note', '')}",
                    icon="✕",
                )
            elif lvl in ["limited", "indirect"]:
                st.warning(
                    f"**Support: {lvl.title()}**\n\n{p.get('evidence_note', '')}",
                    icon="⚠",
                )
            elif lvl == "moderate":
                st.info(
                    f"**Support: {lvl.title()}**\n\n{p.get('evidence_note', '')}",
                    icon="▪",
                )
            else:
                st.success(
                    f"**Support: {lvl.title()}**\n\n{p.get('evidence_note', '')}",
                    icon="✓",
                )

            if p.get("detected_biases"):
                with st.expander("Translation Risks", expanded=True):
                    for b in p["detected_biases"]:
                        b_name = b.get("bias", "")        if isinstance(b, dict) else str(b)
                        b_exp  = b.get("explanation", "") if isinstance(b, dict) else ""
                        st.warning(f"**{b_name}**: {b_exp}", icon="⚠")
            else:
                st.success("No Risk Patterns Detected.", icon="✓")

            st.markdown("#### Prompts")
            with st.expander("Master Prompt", expanded=True):
                st.code(p.get("master_prompt", ""))
            with st.expander("Counter Prompt"):
                st.code(p.get("counter_prompt", ""))
            with st.expander("Uncertainty Mapping"):
                st.code(p.get("uncertainty_prompt", ""))
            with st.expander("Redesign Prompt"):
                st.code(p.get("redesign_prompt", ""))

    st.divider()

    # ── Step 4 : Full Multi-Lens Audit ────────────────────────────────────────
    st.subheader(
        "Step 4: Full Multi-Lens Audit",
        help="Runs the evaluation across all 5 lenses automatically.",
    )
    if st.button("Execute Full Audit", key=f"audit_btn_{pid}"):
        with st.spinner("Scanning all lenses..."):
            try:
                st.session_state[matrix_k] = api_post(
                    "/evidence/scan-all-lenses", pld
                )["lens_matrix"]
                # Invalidate PDF cache when matrix is refreshed
                if pdf_cache_k in st.session_state:
                    del st.session_state[pdf_cache_k]
            except Exception as e:
                st.error(f"Error: {e}", icon="✕")

    if matrix_k in st.session_state:
        mx   = st.session_state[matrix_k]
        rows = []

        for k, v in mx.items():
            if "error" in v:
                rows.append({
                    "Lens":    k.capitalize(),
                    "Support": "Error",
                    "Risks":   v["error"],
                })
            else:
                biases = v.get("detected_biases", [])
                risk_str = (
                    ", ".join(
                        b.get("bias", "") if isinstance(b, dict) else str(b)
                        for b in biases
                    )
                    if biases
                    else "None"
                )
                rows.append({
                    "Lens":    k.capitalize(),
                    "Support": v.get("support_level", "none").capitalize(),
                    "Risks":   risk_str,
                })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        d1, d2 = st.columns(2)

        with d1:
            st.download_button(
                "Download CSV",
                df.to_csv(index=False).encode("utf-8"),
                f"ecosentia_matrix_{pid}.csv",
                "text/csv",
                key=f"csv_btn_{pid}",
            )

        with d2:
            # PDF is generated once and cached in session_state.
            # Re-generation only happens when scan, prompts, or matrix
            # are updated, or when the claim itself changes.
            if pdf_cache_k not in st.session_state:
                st.session_state[pdf_cache_k] = generate_pdf(
                    claim_text,
                    lens_ui,
                    domain_mode,
                    st.session_state.get(scan_k, {}).get("snapshot"),
                    st.session_state.get(prompts_k),
                    mx,
                )
            st.download_button(
                "Download PDF",
                st.session_state[pdf_cache_k],
                f"ecosentia_report_{pid}.pdf",
                "application/pdf",
                key=f"pdf_btn_{pid}",
            )


# ---------------------------------------------------------------------------
# 6. Layout execution
# ---------------------------------------------------------------------------

_DEFAULT_CLAIMS = {
    "Fog":    "A surface structure inspired by the Namib desert beetle for passive water collection and harvesting.",
    "EV":     "An extracellular vesicle-inspired nanoparticle for targeted drug delivery in inflammatory disease.",
    "Custom": "A painless transdermal drug delivery patch utilizing microneedles that mimic the geometry and vibrational insertion mechanism of a mosquito proboscis.",
}

if not st.session_state.compare_mode:
    claim_main = st.text_area(
        "Design Claim",
        value=_DEFAULT_CLAIMS.get(domain_mode, ""),
        height=90,
    )
    render_panel("main", claim_main)

else:
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### ◧ Panel A")
        claim_a = st.text_area(
            "Design Claim A",
            value="A painless transdermal drug delivery patch inspired by mosquito proboscis.",
            height=90,
            key="claim_a",
        )
        render_panel("A", claim_a)

    with col_b:
        st.markdown("### ◨ Panel B")
        claim_b = st.text_area(
            "Design Claim B",
            value="A painless transdermal drug delivery patch inspired by porcupine quills.",
            height=90,
            key="claim_b",
        )
        render_panel("B", claim_b)