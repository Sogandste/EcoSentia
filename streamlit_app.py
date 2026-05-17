# streamlit_app.py
import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import json
from fpdf import FPDF
from datetime import datetime

API_BASE = "https://ecosentia.onrender.com"

# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def api_post(path: str, payload: dict) -> dict:
    """POST to backend with frontend-level cache keyed by path + payload."""
    cache_key = f"cache_{path}_{json.dumps(payload, sort_keys=True)}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    resp = requests.post(f"{API_BASE}{path}", json=payload, timeout=20)
    resp.raise_for_status()
    result = resp.json()
    st.session_state[cache_key] = result
    return result


def add_to_history(claim: str, lens: str, support_level: str):
    """Maintain a capped list of the 5 most recent scans in session state."""
    if "history" not in st.session_state:
        st.session_state["history"] = []
    entry = {
        "time":    datetime.now().strftime("%H:%M"),
        "claim":   claim[:60] + "..." if len(claim) > 60 else claim,
        "lens":    lens,
        "support": support_level,
    }
    if not any(
        h["claim"] == entry["claim"] and h["lens"] == entry["lens"]
        for h in st.session_state["history"]
    ):
        st.session_state["history"].insert(0, entry)
        st.session_state["history"] = st.session_state["history"][:5]


# Evidence support tier configuration: percentage fill, accent color, label
SUPPORT_LEVELS = {
    "none":     {"pct": 5,   "color": "#ef4444", "label": "None"},
    "limited":  {"pct": 30,  "color": "#f59e0b", "label": "Limited"},
    "indirect": {"pct": 50,  "color": "#f59e0b", "label": "Indirect"},
    "moderate": {"pct": 70,  "color": "#3b82f6", "label": "Moderate"},
    "direct":   {"pct": 100, "color": "#10b981", "label": "Direct"},
}


def render_support_bar(level: str, text_color: str, border_color: str) -> str:
    """Return an HTML progress bar representing the evidence support level."""
    cfg = SUPPORT_LEVELS.get(
        level.lower(),
        {"pct": 0, "color": "#94a3b8", "label": level.title()}
    )
    return f"""
    <div style="margin:14px 0 6px 0;">
      <div style="display:flex; justify-content:space-between;
                  margin-bottom:7px; font-size:11px; font-weight:700;
                  color:{text_color}; letter-spacing:0.6px;
                  text-transform:uppercase; opacity:0.75;">
        <span>Evidence Support Level</span>
        <span style="color:{cfg['color']}; opacity:1;">{cfg['label']}</span>
      </div>
      <div style="width:100%; height:5px; background:{border_color};
                  border-radius:999px; overflow:hidden;">
        <div style="width:{cfg['pct']}%; height:100%;
                    background:{cfg['color']}; border-radius:999px;"></div>
      </div>
      <div style="display:flex; justify-content:space-between;
                  margin-top:5px; font-size:10px;
                  color:{text_color}; opacity:0.45;">
        <span>None</span><span>Limited</span>
        <span>Indirect</span><span>Moderate</span><span>Direct</span>
      </div>
    </div>"""


def copy_button(text: str, key: str, icon_color: str, border_color: str):
    """Render a JS-powered clipboard copy button via components.html."""
    escaped = (text.replace("\\", "\\\\")
                   .replace("`", "\\`")
                   .replace("\n", "\\n")
                   .replace("\r", ""))
    components.html(f"""
    <button onclick="navigator.clipboard.writeText(`{escaped}`)
        .then(() => {{
            this.innerText = 'Copied';
            this.style.borderColor = '#10b981';
            this.style.color = '#10b981';
            setTimeout(() => {{
                this.innerText = 'Copy to Clipboard';
                this.style.borderColor = '{border_color}';
                this.style.color = '{icon_color}';
            }}, 1800);
        }})"
        style="background:transparent; border:1px solid {border_color};
               color:{icon_color}; border-radius:6px; padding:5px 14px;
               font-size:12px; font-family:Inter,-apple-system,sans-serif;
               cursor:pointer; transition:all 0.2s; margin-bottom:8px;">
        Copy to Clipboard
    </button>""", height=42)


def generate_pdf_report(
    claim, lens, preset,
    scan_snapshot, prompts, lens_matrix
) -> bytes:
    """Build a structured PDF report covering all completed pipeline steps."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "EcoSentia - Evidence Report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
        f"Lens: {lens.title()}  |  Preset: {preset.upper()}", ln=True)
    pdf.set_text_color(15, 23, 42)
    pdf.ln(4)
    pdf.set_draw_color(203, 213, 225)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Design claim
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Design Claim", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, claim)
    pdf.ln(4)

    # Scan snapshot
    if scan_snapshot:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Evidence Scan Results", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Total Records: {scan_snapshot.get('combined_count','—')}", ln=True)
        pdf.cell(0, 6, f"Direct Matches: {scan_snapshot.get('direct_hits','—')}", ln=True)
        pdf.cell(0, 6, f"Support Level: {scan_snapshot.get('support_level','—').title()}", ln=True)
        pdf.multi_cell(0, 6, f"Summary: {scan_snapshot.get('summary','')}")
        pdf.ln(4)

    # Generated prompts
    if prompts:
        for title, key in [
            ("Master Prompt",            "master_prompt"),
            ("Counter-Challenge Prompt", "counter_prompt"),
            ("Uncertainty Mapping",      "uncertainty_prompt"),
            ("Redesign Prompt",          "redesign_prompt"),
        ]:
            if prompts.get(key):
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, title, ln=True)
                pdf.set_font("Courier", "", 8)
                pdf.set_fill_color(248, 250, 252)
                pdf.multi_cell(0, 5, prompts[key], fill=True)
                pdf.ln(3)

    # Lens matrix
    if lens_matrix:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Multi-Lens Audit Matrix", ln=True)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(241, 245, 249)
        pdf.cell(40,  7, "Lens",          border=1, fill=True)
        pdf.cell(35,  7, "Support Level", border=1, fill=True)
        pdf.cell(115, 7, "Risk Patterns", border=1, fill=True)
        pdf.ln()
        pdf.set_font("Helvetica", "", 9)
        for ln_name, result in lens_matrix.items():
            if "error" in result:
                pdf.cell(40,  7, ln_name.capitalize(), border=1)
                pdf.cell(35,  7, "Error",              border=1)
                pdf.cell(115, 7, result["error"][:80], border=1)
            else:
                biases = (", ".join(result["detected_biases"])
                          if result.get("detected_biases") else "None")
                pdf.cell(40,  7, ln_name.capitalize(),              border=1)
                pdf.cell(35,  7, result["support_level"].title(),   border=1)
                pdf.cell(115, 7, biases[:80],                       border=1)
            pdf.ln()

    return bytes(pdf.output())


# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG & SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="EcoSentia Evidence Layer", layout="centered")

if "dark_mode"    not in st.session_state: st.session_state.dark_mode    = False
if "compare_mode" not in st.session_state: st.session_state.compare_mode = False

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## Appearance")
    is_dark = st.toggle("Dark Mode", value=st.session_state.dark_mode)
    if is_dark != st.session_state.dark_mode:
        st.session_state.dark_mode = is_dark
        st.rerun()

    st.divider()
    st.markdown("## Tools")
    compare_toggle = st.toggle(
        "Claim Comparison Mode",
        value=st.session_state.compare_mode,
        help="Enable side-by-side evaluation of two design claims using identical configuration."
    )
    if compare_toggle != st.session_state.compare_mode:
        st.session_state.compare_mode = compare_toggle
        st.rerun()

    st.divider()
    st.markdown("## Recent Scans")
    dm_sb = st.session_state.dark_mode
    if "history" in st.session_state and st.session_state["history"]:
        for h in st.session_state["history"]:
            lc  = SUPPORT_LEVELS.get(h["support"].lower(), {"color": "#94a3b8"})
            # Sidebar history card colors adapt to current theme
            bg  = "#1e293b" if dm_sb else "#f1f5f9"
            br  = "#334155" if dm_sb else "#cbd5e1"
            tc  = "#f1f5f9" if dm_sb else "#0f172a"
            tc2 = "#94a3b8" if dm_sb else "#475569"
            st.markdown(f"""
            <div style="padding:8px 10px; margin-bottom:6px; border-radius:7px;
                        border:1px solid {br}; background:{bg};">
              <div style="font-size:11px; font-weight:600; color:{tc2};">
                {h['time']} · {h['lens'].title()}</div>
              <div style="font-size:12px; margin-top:2px; color:{tc};">
                {h['claim']}</div>
              <div style="margin-top:4px;">
                <span style="font-size:11px; padding:2px 8px; border-radius:999px;
                             color:{lc['color']}; border:1px solid {lc['color']};">
                  {h['support'].title()}</span>
              </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.caption("No scans recorded yet.")

    st.divider()
    st.markdown(
        "## About\n"
        "EcoSentia is a multi-lens evidence interrogation layer that evaluates "
        "biomimetic design claims against peer-reviewed literature, detects "
        "translation risk patterns, and generates structured prompts for "
        "LLM-assisted critical assessment."
    )

dm = st.session_state.dark_mode

# ══════════════════════════════════════════════════════════════════════════════
# PALETTE
# Dark:  text #f1f5f9 on panel #1e293b  → contrast ratio 13.9:1  (WCAG AAA)
# Light: text #0f172a on panel #ffffff  → contrast ratio 19.1:1  (WCAG AAA)
# ══════════════════════════════════════════════════════════════════════════════
if dm:
    T = {
        "bg":           "#0f172a",
        "panel":        "#1e293b",
        "text":         "#f1f5f9",
        "border":       "#334155",
        "hover":        "#2d3f55",
        "icon":         "#f1f5f9",
        "text_muted":   "#94a3b8",
        "shadow":       "rgba(0,0,0,0.40)",
        "tooltip_bg":   "#f8fafc",
        "tooltip_text": "#0f172a",
        "focus_ring":   "rgba(148,163,184,0.30)",
        "input_bg":     "#1e293b",
        "matrix_direct":   "rgba(16,185,129,0.18)",
        "matrix_moderate": "rgba(59,130,246,0.18)",
        "matrix_limited":  "rgba(245,158,11,0.18)",
        "matrix_none":     "rgba(239,68,68,0.18)",
        "matrix_error":    "rgba(239,68,68,0.10)",
        "badge_direct":    "#34d399",
        "badge_moderate":  "#60a5fa",
        "badge_limited":   "#fbbf24",
        "badge_none":      "#f87171",
    }
else:
    T = {
        "bg":           "#f8fafc",
        "panel":        "#ffffff",
        "text":         "#0f172a",
        "border":       "#94a3b8",
        "hover":        "#f1f5f9",
        "icon":         "#0f172a",
        "text_muted":   "#475569",
        "shadow":       "rgba(15,23,42,0.10)",
        "tooltip_bg":   "#0f172a",
        "tooltip_text": "#f8fafc",
        "focus_ring":   "rgba(15,23,42,0.12)",
        "input_bg":     "#ffffff",
        "matrix_direct":   "rgba(4,120,87,0.10)",
        "matrix_moderate": "rgba(29,78,216,0.10)",
        "matrix_limited":  "rgba(180,83,9,0.10)",
        "matrix_none":     "rgba(185,28,28,0.10)",
        "matrix_error":    "rgba(185,28,28,0.05)",
        "badge_direct":    "#065f46",
        "badge_moderate":  "#1e3a8a",
        "badge_limited":   "#92400e",
        "badge_none":      "#991b1b",
    }

# ══════════════════════════════════════════════════════════════════════════════
# CSS
# Strategy: NO universal asterisk rule.
# Each Streamlit component is targeted individually to prevent
# cross-component color bleed between dark panel and light bg.
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<style>

/* ── 1. CSS VARIABLES
   Streamlit reads these at runtime to paint its own internal components.
   Overriding them here ensures cascade into every shadow-DOM subtree.
────────────────────────────────────────────────────────────────────────────*/
:root {{
    --text-color:                 {T['text']}       !important;
    --background-color:           {T['bg']}         !important;
    --secondary-background-color: {T['panel']}      !important;
    --primary-color:              {T['text_muted']} !important;
}}

/* ── 2. APP SHELL ────────────────────────────────────────────────────────────*/
html, body, #root,
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {{
    background-color: {T['bg']} !important;
    color: {T['text']} !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}}

/* ── 3. MARKDOWN & HEADINGS ──────────────────────────────────────────────────*/
.stMarkdown p,
.stMarkdown span,
.stMarkdown li,
.stMarkdown h1, .stMarkdown h2,
.stMarkdown h3, .stMarkdown h4 {{
    color: {T['text']} !important;
}}
h3 {{
    font-weight: 600 !important;
    font-size: 19px !important;
    color: {T['text']} !important;
}}
hr {{
    border-top: 1px solid {T['border']} !important;
    margin: 28px 0 !important;
    opacity: 1 !important;
}}

/* ── 4. WIDGET LABELS ────────────────────────────────────────────────────────*/
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span,
.stTextArea   label,
.stTextInput  label,
.stSelectbox  label,
.stSlider     label,
.stRadio      label,
.stToggle     label {{
    color: {T['text']} !important;
}}

/* ── 5. CAPTIONS ─────────────────────────────────────────────────────────────*/
[data-testid="stCaptionContainer"] p,
[data-testid="stCaptionContainer"] span,
.stCaption p, small {{
    color: {T['text_muted']} !important;
    font-size: 13px !important;
}}

/* ── 6. SIDEBAR ──────────────────────────────────────────────────────────────*/
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div {{
    background-color: {T['panel']} !important;
    border-right: 1.5px solid {T['border']} !important;
}}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown span,
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] label {{
    color: {T['text']} !important;
}}

/* ── 7. SIDEBAR COLLAPSE BUTTON
   Root cause in light mode: Streamlit renders this button with a
   transparent background, making the white SVG invisible on the
   white page background. Fix: explicit panel color + dark icon.
   Targets all selector variants across Streamlit versions.
────────────────────────────────────────────────────────────────────────────*/
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] {{
    background-color: {T['panel']} !important;
    border: 2px solid {T['border']} !important;
    border-radius: 9px !important;
    box-shadow: 0 3px 10px {T['shadow']} !important;
    opacity: 1 !important;
    visibility: visible !important;
}}
[data-testid="collapsedControl"] button,
[data-testid="stSidebarCollapseButton"] button,
button[data-testid="baseButton-headerNoPadding"],
button[kind="headerNoPadding"] {{
    background-color: {T['panel']} !important;
    border: 2px solid {T['border']} !important;
    border-radius: 9px !important;
    box-shadow: 0 3px 10px {T['shadow']} !important;
    opacity: 1 !important;
    visibility: visible !important;
    transition: background 0.2s, border-color 0.2s !important;
}}
[data-testid="collapsedControl"]:hover button,
[data-testid="stSidebarCollapseButton"]:hover button,
button[data-testid="baseButton-headerNoPadding"]:hover {{
    background-color: {T['hover']} !important;
    border-color: {T['text_muted']} !important;
}}
/* SVG chevron — painted explicitly in both modes */
[data-testid="collapsedControl"] svg,
[data-testid="collapsedControl"] button svg,
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stSidebarCollapseButton"] button svg,
button[data-testid="baseButton-headerNoPadding"] svg,
button[kind="headerNoPadding"] svg {{
    fill:    {T['icon']} !important;
    stroke:  {T['icon']} !important;
    color:   {T['icon']} !important;
    opacity: 1 !important;
    width:   18px !important;
    height:  18px !important;
}}

/* ── 8. EXPANDERS
   Each layer is painted individually:
   wrapper → summary header → summary text → chevron → body bg → body text.
   No shorthand selector is used to avoid bleed between panel and bg colors.
────────────────────────────────────────────────────────────────────────────*/
[data-testid="stExpander"] {{
    background-color: {T['panel']} !important;
    border: 1.5px solid {T['border']} !important;
    border-radius: 10px !important;
    box-shadow: 0 3px 10px {T['shadow']} !important;
    overflow: hidden !important;
    margin-bottom: 10px !important;
    transition: border-color 0.2s !important;
}}
[data-testid="stExpander"]:hover {{
    border-color: {T['text_muted']} !important;
}}
[data-testid="stExpander"] summary {{
    background-color: {T['panel']} !important;
    padding: 14px 18px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    border-bottom: 1px solid transparent !important;
    cursor: pointer !important;
    transition: background 0.15s !important;
}}
[data-testid="stExpander"] summary:hover {{
    background-color: {T['hover']} !important;
}}
[data-testid="stExpander"][open] summary {{
    border-bottom: 1px solid {T['border']} !important;
    background-color: {T['hover']} !important;
}}
/* Expander title text */
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary div,
[data-testid="stExpander"] summary [data-testid] {{
    color: {T['text']} !important;
    font-weight: 600 !important;
}}
/* Chevron icon */
[data-testid="stExpander"] summary svg {{
    fill:    {T['icon']} !important;
    stroke:  {T['icon']} !important;
    opacity: 1 !important;
}}
/* Body area background */
[data-testid="stExpander"] > div > div {{
    padding: 16px 18px !important;
    background-color: {T['bg']} !important;
}}
/* Body text — individually named, no asterisk */
[data-testid="stExpander"] > div .stMarkdown p,
[data-testid="stExpander"] > div .stMarkdown span,
[data-testid="stExpander"] > div .stMarkdown li,
[data-testid="stExpander"] > div .stMarkdown h4,
[data-testid="stExpander"] > div [data-testid="stWidgetLabel"] p,
[data-testid="stExpander"] > div label {{
    color: {T['text']} !important;
}}
[data-testid="stExpander"] > div [data-testid="stCaptionContainer"] p {{
    color: {T['text_muted']} !important;
}}

/* ── 9. METRIC CARDS ─────────────────────────────────────────────────────────*/
[data-testid="metric-container"] {{
    background-color: {T['panel']} !important;
    border: 1.5px solid {T['border']} !important;
    border-radius: 10px !important;
    padding: 16px 18px !important;
    box-shadow: 0 3px 10px {T['shadow']} !important;
    transition: border-color 0.2s !important;
}}
[data-testid="metric-container"]:hover {{
    border-color: {T['text_muted']} !important;
}}
[data-testid="stMetricValue"] > div {{
    font-size: 26px !important;
    font-weight: 700 !important;
    color: {T['text']} !important;
}}
[data-testid="stMetricLabel"] > div {{
    font-size: 12px !important;
    font-weight: 600 !important;
    letter-spacing: 0.5px !important;
    text-transform: uppercase !important;
    color: {T['text_muted']} !important;
}}

/* ── 10. ALERTS ──────────────────────────────────────────────────────────────*/
[data-testid="stAlert"] {{
    background-color: {T['panel']} !important;
    border: 1.5px solid {T['border']} !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 8px {T['shadow']} !important;
}}
[data-testid="stAlert"] .stMarkdown p,
[data-testid="stAlert"] .stMarkdown span,
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {{
    color: {T['text']} !important;
}}

/* ── 11. INPUTS & TEXTAREAS ──────────────────────────────────────────────────*/
input[type="text"],
input[type="number"],
input[type="search"],
textarea {{
    background-color: {T['input_bg']} !important;
    color: {T['text']} !important;
    border: 1.5px solid {T['border']} !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}}
input::placeholder, textarea::placeholder {{
    color: {T['text_muted']} !important;
    opacity: 0.75 !important;
}}
input:hover, textarea:hover {{
    border-color: {T['text_muted']} !important;
    box-shadow: 0 0 0 3px {T['focus_ring']} !important;
}}
input:focus, textarea:focus {{
    border-color: {T['text_muted']} !important;
    box-shadow: 0 0 0 3px {T['focus_ring']} !important;
    outline: none !important;
}}
.stTextArea > div,
.stTextArea > div > div {{
    background-color: {T['input_bg']} !important;
    border-color: {T['border']} !important;
}}

/* ── 12. SELECTBOX (closed state) ────────────────────────────────────────────*/
div[data-baseweb="select"] > div {{
    background-color: {T['input_bg']} !important;
    color: {T['text']} !important;
    border: 1.5px solid {T['border']} !important;
    border-radius: 8px !important;
    transition: border-color 0.2s !important;
}}
div[data-baseweb="select"] > div:hover {{
    border-color: {T['text_muted']} !important;
    box-shadow: 0 0 0 3px {T['focus_ring']} !important;
}}
div[data-baseweb="select"] [data-testid="stSelectboxValue"],
div[data-baseweb="select"] [class*="singleValue"],
div[data-baseweb="select"] [class*="placeholder"] {{
    color: {T['text']} !important;
}}
div[data-baseweb="select"] svg {{
    fill:  {T['icon']} !important;
    color: {T['icon']} !important;
}}

/* ── 13. SELECTBOX DROPDOWN (open state)
   Every layer from the popover container down to individual list items
   is explicitly painted. This fixes the invisible-text bug in light mode
   where BaseWeb defaults to white text on a white background.
────────────────────────────────────────────────────────────────────────────*/
div[data-baseweb="popover"] {{
    background-color: {T['panel']} !important;
    border: 1.5px solid {T['border']} !important;
    border-radius: 10px !important;
    box-shadow: 0 12px 32px {T['shadow']} !important;
    overflow: hidden !important;
}}
div[data-baseweb="popover"] ul,
div[data-baseweb="popover"] [role="listbox"] {{
    background-color: {T['panel']} !important;
    padding: 4px !important;
}}
div[data-baseweb="popover"] li,
li[role="option"],
[data-testid="stSelectboxVirtualDropdown"] li {{
    background-color: {T['panel']} !important;
    color: {T['text']} !important;
    font-size: 14px !important;
    border-radius: 6px !important;
    padding: 9px 14px !important;
    margin: 2px 0 !important;
    cursor: pointer !important;
    transition: background 0.12s !important;
}}
div[data-baseweb="popover"] li:hover,
li[role="option"]:hover {{
    background-color: {T['hover']} !important;
    color: {T['text']} !important;
}}
li[aria-selected="true"] {{
    background-color: {T['hover']} !important;
    color: {T['text']} !important;
    font-weight: 600 !important;
}}
div[data-baseweb="popover"] [class*="MenuOption"] span,
div[data-baseweb="popover"] [class*="option"] span {{
    color: {T['text']} !important;
}}
/* Scrollbar inside dropdown — clearly visible in both modes */
div[data-baseweb="popover"] ::-webkit-scrollbar {{
    width: 6px !important;
    background: {T['hover']} !important;
}}
div[data-baseweb="popover"] ::-webkit-scrollbar-thumb {{
    background: {T['border']} !important;
    border-radius: 999px !important;
}}
div[data-baseweb="popover"] ::-webkit-scrollbar-thumb:hover {{
    background: {T['text_muted']} !important;
}}

/* ── 14. PAGE SCROLLBAR ──────────────────────────────────────────────────────*/
::-webkit-scrollbar {{ width: 7px; }}
::-webkit-scrollbar-track {{ background: {T['bg']}; }}
::-webkit-scrollbar-thumb {{
    background: {T['border']};
    border-radius: 999px;
}}
::-webkit-scrollbar-thumb:hover {{ background: {T['text_muted']}; }}

/* ── 15. RADIO ───────────────────────────────────────────────────────────────*/
div[role="radiogroup"] {{
    gap: 12px !important;
    padding-top: 4px !important;
}}
div[role="radiogroup"] label {{
    color: {T['text']} !important;
    font-size: 14px !important;
}}
div[role="radiogroup"] label:hover {{
    background: {T['hover']} !important;
    border-radius: 6px !important;
    outline: 1.5px solid {T['focus_ring']} !important;
}}

/* ── 16. SLIDER ──────────────────────────────────────────────────────────────*/
[data-testid="stSlider"] [data-testid="stWidgetLabel"] p,
[data-testid="stSlider"] p {{
    color: {T['text']} !important;
}}

/* ── 17. TOGGLE ──────────────────────────────────────────────────────────────*/
[data-testid="stToggle"] label > div:first-child {{
    background-color: {T['border']} !important;
    border: 1.5px solid {T['text_muted']} !important;
}}
[data-testid="stToggle"] input:checked ~ label > div:first-child {{
    background-color: {T['text_muted']} !important;
}}
[data-testid="stToggle"] [data-testid="stWidgetLabel"] p,
[data-testid="stToggle"] span {{
    color: {T['text']} !important;
}}

/* ── 18. TOOLTIPS ────────────────────────────────────────────────────────────*/
[data-testid="stTooltipIcon"] svg {{
    stroke: {T['icon']} !important;
    fill: none !important;
    width: 15px !important;
    height: 15px !important;
    opacity: 0.6 !important;
    transition: opacity 0.15s !important;
}}
[data-testid="stTooltipIcon"]:hover svg {{ opacity: 1 !important; }}
[data-testid="stTooltipContent"],
div[role="tooltip"] {{
    background-color: {T['tooltip_bg']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 8px !important;
    padding: 11px 15px !important;
    max-width: 300px !important;
    line-height: 1.6 !important;
    box-shadow: 0 8px 22px rgba(0,0,0,0.18) !important;
    font-size: 13px !important;
}}
[data-testid="stTooltipContent"] p,
[data-testid="stTooltipContent"] span,
div[role="tooltip"] p,
div[role="tooltip"] span {{
    color: {T['tooltip_text']} !important;
    font-size: 13px !important;
}}

/* ── 19. BUTTONS ─────────────────────────────────────────────────────────────*/
.stButton > button {{
    background-color: {T['panel']} !important;
    color: {T['text']} !important;
    border: 1.5px solid {T['border']} !important;
    border-radius: 8px !important;
    padding: 8px 22px !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    box-shadow: 0 2px 5px {T['shadow']} !important;
    transition: all 0.2s ease !important;
}}
.stButton > button:hover {{
    background-color: {T['hover']} !important;
    border-color: {T['text_muted']} !important;
    box-shadow: 0 0 0 3px {T['focus_ring']},
                0 4px 8px {T['shadow']} !important;
    transform: translateY(-1px) !important;
}}
[data-testid="stDownloadButton"] > button {{
    background-color: {T['panel']} !important;
    color: {T['text']} !important;
    border: 1.5px solid {T['border']} !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    width: 100% !important;
    transition: all 0.2s ease !important;
}}
[data-testid="stDownloadButton"] > button:hover {{
    background-color: {T['hover']} !important;
    border-color: {T['text_muted']} !important;
}}

/* ── 20. CODE BLOCKS ─────────────────────────────────────────────────────────*/
.stCodeBlock {{
    background-color: {T['bg']} !important;
    border: 1.5px solid {T['border']} !important;
    border-radius: 8px !important;
}}
.stCodeBlock pre,
.stCodeBlock code,
.stCodeBlock span {{
    color: {T['text']} !important;
    background-color: transparent !important;
}}

/* ── 21. RISK PANELS (orange-red left-border cards) ──────────────────────────*/
.risk-panel {{
    background: linear-gradient(
        135deg,
        rgba(249,115,22,0.08),
        rgba(239,68,68,0.08)
    ) !important;
    border: 1px solid rgba(239,68,68,0.25) !important;
    border-left: 4px solid #ef4444 !important;
    border-radius: 8px !important;
    padding: 14px 16px !important;
    margin-bottom: 10px !important;
    font-size: 14px !important;
    line-height: 1.65 !important;
}}
.risk-panel p,
.risk-panel span {{ color: {T['text']} !important; }}
.risk-title {{
    color: #ea580c !important;
    font-weight: 700 !important;
    margin-bottom: 5px !important;
    display: block !important;
    font-size: 12px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.4px !important;
}}

/* ── 22. LENS MATRIX TABLE ───────────────────────────────────────────────────*/
.matrix-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    border: 1.5px solid {T['border']};
    border-radius: 10px;
    overflow: hidden;
    font-size: 14px;
    box-shadow: 0 4px 14px {T['shadow']};
}}
.matrix-table thead tr {{
    background-color: {T['hover']};
    border-bottom: 2px solid {T['border']};
}}
.matrix-table thead th {{
    padding: 11px 16px;
    text-align: left;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: {T['text_muted']} !important;
}}
.matrix-table tbody tr {{
    border-bottom: 1px solid {T['border']};
    transition: background 0.15s;
}}
.matrix-table tbody tr:last-child {{ border-bottom: none; }}
.matrix-table tbody tr:hover {{ background-color: {T['hover']} !important; }}
.matrix-table tbody td {{
    padding: 12px 16px;
    vertical-align: middle;
    color: {T['text']} !important;
    background-color: {T['panel']};
    font-size: 14px;
}}
.matrix-table tbody tr:hover td {{
    background-color: {T['hover']} !important;
    color: {T['text']} !important;
}}
.badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.3px;
}}
.badge-direct   {{ background:{T['matrix_direct']};   color:{T['badge_direct']}   !important; border:1px solid {T['badge_direct']};   }}
.badge-moderate {{ background:{T['matrix_moderate']}; color:{T['badge_moderate']} !important; border:1px solid {T['badge_moderate']}; }}
.badge-limited  {{ background:{T['matrix_limited']};  color:{T['badge_limited']}  !important; border:1px solid {T['badge_limited']};  }}
.badge-indirect {{ background:{T['matrix_limited']};  color:{T['badge_limited']}  !important; border:1px solid {T['badge_limited']};  }}
.badge-none     {{ background:{T['matrix_none']};     color:{T['badge_none']}     !important; border:1px solid {T['badge_none']};     }}
.badge-error    {{ background:{T['matrix_error']};    color:{T['badge_none']}     !important; border:1px solid {T['badge_none']};     }}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# LOGO
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div style="display:flex; align-items:center; gap:16px;
            margin-bottom:28px; margin-top:8px;">
  <svg width="40" height="40" viewBox="0 0 100 100"
       xmlns="http://www.w3.org/2000/svg">
    <circle cx="50" cy="50" r="45" fill="none"
            stroke="{T['text']}" stroke-width="2" opacity="0.15"/>
    <path d="M50 85 C80 80, 85 45, 50 15 C65 40, 65 65, 50 85 Z"
          fill="none" stroke="{T['text']}" stroke-width="2.5"
          stroke-linecap="round"/>
    <line x1="50" y1="35" x2="50" y2="85" fill="none"
          stroke="{T['text']}" stroke-width="2.5"
          stroke-linecap="round" opacity="0.8"/>
    <path d="M30 25 L70 25 L60 35 L40 35 Z" fill="none"
          stroke="{T['text']}" stroke-width="2.5" opacity="0.8"/>
  </svg>
  <div>
    <div style="font-size:22px; font-weight:600; letter-spacing:0.4px;
                color:{T['text']}; line-height:1.15;">EcoSentia</div>
    <div style="font-size:11px; letter-spacing:1px; color:{T['text_muted']};
                margin-top:4px; text-transform:uppercase; font-weight:500;">
      Evidence &amp; Interrogation Layer v0.2
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# EVALUATION PANEL
# ══════════════════════════════════════════════════════════════════════════════
def render_evaluation_panel(
    panel_id: str,
    preset_ui: str,
    lens_ui: str,
    claim: str,
    source: str,
    max_results: int,
):
    """Render the full 4-step evaluation workflow for a single claim."""
    base_payload = {
        "session_id":  f"streamlit-{panel_id}",
        "preset":      preset_ui.lower(),
        "project":     "",
        "claim":       claim,
        "lens":        lens_ui.lower(),
        "source":      source,
        "max_results": max_results,
    }

    st.divider()

    # ── Step 1: Refine Search Query ───────────────────────────────────────────
    st.markdown("### Step 1: Refine Search Query")
    st.caption(
        "Extracts key entities from the claim and builds a Boolean query "
        "optimized for PubMed and OpenAlex syntax."
    )
    if st.button(
        "Refine Query", key=f"refine_{panel_id}",
        help="NLP module extracts biological model, function, and application "
             "domain. Result is editable before scanning."
    ):
        with st.spinner("Refining..."):
            try:
                data = api_post("/evidence/refine-query", base_payload)
                st.session_state[f"query_text_{panel_id}"] = data["refined_query"]
                st.success("Query refined.")
            except Exception as e:
                st.error(f"Refinement failed: {e}")

    query_text = st.text_area(
        "Active Query (Editable)",
        height=80,
        key=f"query_text_{panel_id}",
        help="Boolean query sent to databases. Add MeSH tags or adjust scope "
             "before executing the scan."
    )
    st.divider()

    # ── Step 2: Run Evidence Scan ─────────────────────────────────────────────
    st.markdown("### Step 2: Run Evidence Scan")
    st.caption(
        "Retrieves abstracts from selected databases and scores "
        "semantic overlap with the original claim."
    )
    if st.button(
        "Execute Scan", key=f"scan_{panel_id}",
        help="Results are cached — re-running the same query returns instantly "
             "without an API call."
    ):
        with st.spinner("Querying scientific literature..."):
            try:
                payload = {**base_payload, "query_text": query_text}
                data = api_post("/evidence/scan", payload)
                st.session_state[f"scan_{panel_id}"] = data
                st.success("Literature scan complete.")

                snap = data["snapshot"]
                add_to_history(claim, lens_ui, snap.get("support_level", "none"))

                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Total Records",  snap["combined_count"])
                col_b.metric("Direct Matches", snap["direct_hits"])
                col_c.metric("Support Level",  snap.get("support_level", "—").title())

                # Inline captions replace tooltip for output metrics
                # (Hidden Affordance anti-pattern avoided per Nielsen's
                #  Visibility of System Status heuristic)
                st.caption(
                    "Total Records: all retrieved abstracts.  "
                    "Direct Matches: high semantic overlap with your claim.  "
                    "Support Level: aggregated evidence tier."
                )
                st.markdown(
                    render_support_bar(
                        snap.get("support_level", "none"),
                        T["text"], T["border"]
                    ),
                    unsafe_allow_html=True
                )
                st.info(snap["summary"])
                if snap.get("top_titles"):
                    with st.expander("Top Retrieved Titles"):
                        for t in snap["top_titles"]:
                            st.write(f"- {t}")
            except Exception as e:
                st.error(f"Scan failed: {e}")
    st.divider()

    # ── Step 3: Generate Evidence-Aware Prompts ───────────────────────────────
    st.markdown("### Step 3: Generate Evidence-Aware Prompts")
    st.caption(
        "Builds four structured LLM prompts grounded in the retrieved "
        "evidence snapshot and the selected evaluation lens."
    )
    if f"scan_{panel_id}" not in st.session_state:
        st.info("Complete Step 2 first.")
    else:
        if st.button(
            "Generate Prompts", key=f"prompts_btn_{panel_id}",
            help="Constructs Master, Counter, Uncertainty, and Redesign "
                 "prompts. Results are cached."
        ):
            with st.spinner("Structuring evaluation prompts..."):
                try:
                    scan_data = st.session_state[f"scan_{panel_id}"]
                    data = api_post("/evidence/prompts", {
                        "preset":     preset_ui.lower(),
                        "lens":       lens_ui.lower(),
                        "claim":      claim,
                        "query_text": scan_data["query_text"],
                        "snapshot":   scan_data["snapshot"],
                    })
                    st.session_state[f"prompts_{panel_id}"] = data["prompts"]
                except Exception as e:
                    st.error(f"Prompt generation failed: {e}")

        if f"prompts_{panel_id}" in st.session_state:
            p = st.session_state[f"prompts_{panel_id}"]
            level_map = {
                "none": "error", "limited": "warning",
                "indirect": "warning", "moderate": "info", "direct": "success"
            }
            getattr(st, level_map.get(p["support_level"], "info"))(
                f"**Support Level: {p['support_level'].title()}**"
                f"\n\n{p['evidence_note']}"
            )
            st.markdown(
                render_support_bar(p["support_level"], T["text"], T["border"]),
                unsafe_allow_html=True
            )

            if p.get("detected_biases"):
                st.markdown("#### Detected Translation Risk Patterns")
                for b in p["detected_biases"]:
                    st.markdown(f"""
                    <div class="risk-panel">
                        <span class="risk-title">{b['bias']}</span>
                        {b['explanation']}
                    </div>""", unsafe_allow_html=True)
            else:
                st.success("No translation risk patterns detected.")

            st.markdown("#### Evaluation Prompts")

            # Prompt descriptions are shown as inline captions inside each
            # expander — not as tooltips — because they describe output content
            # (Recognition over Recall, Cognitive Load Theory)
            prompt_meta = [
                ("Master Prompt",             "master_prompt",      True,
                 "Primary evaluation prompt — feed directly to your LLM."),
                ("Counter-Challenge Prompt",   "counter_prompt",     False,
                 "Instructs the LLM to argue against the claim's validity."),
                ("Uncertainty Mapping Prompt", "uncertainty_prompt", False,
                 "Enumerates what is unknown or contested in the literature."),
                ("Redesign Prompt",            "redesign_prompt",    False,
                 "Proposes evidence-grounded modifications to the design."),
            ]
            for title, key, expanded, desc in prompt_meta:
                with st.expander(title, expanded=expanded):
                    st.caption(desc)
                    if p.get(key):
                        copy_button(
                            p[key],
                            f"copy_{key}_{panel_id}",
                            T["icon"],
                            T["border"]
                        )
                        st.code(p[key], language="text")

            if p.get("look_for"):
                st.markdown("**Checklist For AI Response:**")
                for item in p["look_for"]:
                    st.markdown(f"- {item.capitalize()}")

    st.divider()

    # ── Step 4: Full Multi-Lens Audit ─────────────────────────────────────────
    st.markdown("### Step 4: Full Multi-Lens Audit")
    st.caption(
        "Runs the evidence scan across all 5 lenses — Mechanism, Context, "
        "Scale, Manufacturability, Safety — and returns a unified risk matrix."
    )
    if st.button(
        "Execute Full Matrix Audit", key=f"matrix_{panel_id}",
        help="5 sequential API calls. Results are cached — safe to re-run."
    ):
        with st.spinner("Scanning all lenses..."):
            try:
                data = api_post("/evidence/scan-all-lenses", base_payload)
                st.session_state[f"lens_matrix_{panel_id}"] = data["lens_matrix"]
            except Exception as e:
                st.error(f"Matrix audit failed: {e}")

    if f"lens_matrix_{panel_id}" in st.session_state:
        matrix = st.session_state[f"lens_matrix_{panel_id}"]
        table_data = []
        for lens_name, result in matrix.items():
            if "error" in result:
                table_data.append({
                    "Lens":          lens_name.capitalize(),
                    "Support Level": "Error",
                    "Risk Patterns": result["error"],
                    "_level":        "error",
                })
            else:
                biases_str = (
                    ", ".join(result["detected_biases"])
                    if result.get("detected_biases") else "None Detected"
                )
                table_data.append({
                    "Lens":          lens_name.capitalize(),
                    "Support Level": result["support_level"].capitalize(),
                    "Risk Patterns": biases_str,
                    "_level":        result["support_level"].lower(),
                })
        df = pd.DataFrame(table_data)

        st.markdown("#### Analytical Lens Matrix")
        rows_html = ""
        for _, row in df.iterrows():
            rows_html += f"""
            <tr>
              <td style="font-weight:600; color:{T['text']};">{row['Lens']}</td>
              <td><span class="badge badge-{row['_level']}">{row['Support Level']}</span></td>
              <td style="color:{T['text_muted']}; font-size:13px;">{row['Risk Patterns']}</td>
            </tr>"""
        st.markdown(f"""
        <table class="matrix-table">
          <thead><tr>
            <th style="width:16%;">Lens</th>
            <th style="width:20%;">Support Level</th>
            <th>Risk Patterns</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table><br>
        """, unsafe_allow_html=True)

        df_export = df.drop(columns=["_level"])
        ec1, ec2, ec3 = st.columns(3)

        with ec1:
            st.download_button(
                "Export CSV",
                data=df_export.to_csv(index=False).encode("utf-8"),
                file_name=f"ecosentia_matrix_{panel_id}.csv",
                mime="text/csv",
                key=f"dl_csv_{panel_id}",
                help="Compatible with Excel and Google Sheets."
            )
        with ec2:
            st.download_button(
                "Export JSON",
                data=json.dumps(
                    [{"lens":           r["Lens"],
                      "support_level":  r["Support Level"],
                      "risk_patterns":  r["Risk Patterns"]}
                     for r in table_data],
                    indent=2
                ).encode("utf-8"),
                file_name=f"ecosentia_matrix_{panel_id}.json",
                mime="application/json",
                key=f"dl_json_{panel_id}",
                help="For direct API integration or programmatic processing."
            )
        with ec3:
            scan_snap    = (st.session_state[f"scan_{panel_id}"]["snapshot"]
                            if f"scan_{panel_id}" in st.session_state else None)
            prompts_data = st.session_state.get(f"prompts_{panel_id}")
            try:
                pdf_bytes = generate_pdf_report(
                    claim=claim, lens=lens_ui, preset=preset_ui,
                    scan_snapshot=scan_snap,
                    prompts=prompts_data,
                    lens_matrix=matrix,
                )
                st.download_button(
                    "Export PDF Report",
                    data=pdf_bytes,
                    file_name=f"ecosentia_report_{panel_id}.pdf",
                    mime="application/pdf",
                    key=f"dl_pdf_{panel_id}",
                    help="Full structured report covering all completed steps."
                )
            except Exception as e:
                st.caption(f"PDF unavailable: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### Configuration")

col1, col2 = st.columns(2)
with col1:
    # Radio is preferred over selectbox for ≤4 options:
    # all choices visible simultaneously → faster scan, no extra click
    preset_ui = st.radio(
        "Preset", ["Fog", "EV"], horizontal=True,
        help="'Fog': biomimetic surface/structural concepts. "
             "'EV': medical and nanomedicine applications."
    )
with col2:
    # Selectbox is appropriate here: 5 options exceed the radio threshold
    lens_ui = st.selectbox(
        "Evaluation Lens",
        ["Mechanism", "Context", "Scale", "Manufacturability", "Safety"],
        help="Mechanism: function transfer validity. "
             "Context: ecological mismatch. "
             "Scale: size constraints. "
             "Manufacturability: fabrication feasibility. "
             "Safety: biocompatibility gaps."
    )

col3, col4 = st.columns(2)
with col3:
    # 3 options — radio keeps all choices visible without an extra interaction
    source = st.radio(
        "Literature Source", ["Both", "PubMed", "OpenAlex"], horizontal=True,
        help="PubMed: biomedical literature. "
             "OpenAlex: engineering and materials science. "
             "'Both' recommended for cross-disciplinary claims."
    )
with col4:
    max_results = st.slider(
        "Max Results Per Source", 1, 10, 5,
        help="Records per database. Keep at 5 during development; "
             "increase to 10 for final audits."
    )

# ── Normal mode ───────────────────────────────────────────────────────────────
if not st.session_state.compare_mode:
    claim = st.text_area(
        "Design Claim",
        value=(
            "A surface structure inspired by the Namib desert beetle "
            "for passive water collection and harvesting."
        ),
        height=90,
        help="Include: biological model, abstracted function, and "
             "proposed application domain."
    )
    render_evaluation_panel("main", preset_ui, lens_ui, claim, source, max_results)

# ── Claim comparison mode ─────────────────────────────────────────────────────
else:
    st.markdown(f"""
    <div style="padding:10px 14px; margin:10px 0 16px 0;
                background:rgba(59,130,246,0.07);
                border:1px solid rgba(59,130,246,0.2);
                border-radius:8px; font-size:13px; color:{T['text']};">
        Claim Comparison Mode — two independent claims evaluated
        side-by-side using the shared configuration above.
    </div>""", unsafe_allow_html=True)

    lc, rc = st.columns(2)
    with lc:
        st.markdown(
            f"<div style='font-size:11px; font-weight:700; "
            f"color:{T['text_muted']}; text-transform:uppercase; "
            f"letter-spacing:0.6px; margin-bottom:5px;'>Claim A</div>",
            unsafe_allow_html=True
        )
        claim_a = st.text_area(
            "Design Claim A",
            value=(
                "A surface structure inspired by the Namib desert beetle "
                "for passive water collection."
            ),
            height=90, key="claim_a",
            help="First concept to evaluate."
        )
    with rc:
        st.markdown(
            f"<div style='font-size:11px; font-weight:700; "
            f"color:{T['text_muted']}; text-transform:uppercase; "
            f"letter-spacing:0.6px; margin-bottom:5px;'>Claim B</div>",
            unsafe_allow_html=True
        )
        claim_b = st.text_area(
            "Design Claim B",
            value=(
                "A drag-reduction hull coating inspired by "
                "shark denticle microstructure."
            ),
            height=90, key="claim_b",
            help="Second concept to evaluate in parallel with Claim A."
        )

    lp, rp = st.columns(2)
    with lp:
        render_evaluation_panel("A", preset_ui, lens_ui, claim_a, source, max_results)
    with rp:
        render_evaluation_panel("B", preset_ui, lens_ui, claim_b, source, max_results)