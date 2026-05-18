# app.py
import os
import streamlit as st
import requests
import pandas as pd

API_BASE = os.getenv("ECOSENTIA_API_URL", "https://ecosentia.onrender.com")

def api_post(path: str, payload: dict) -> dict:
    resp = requests.post(f"{API_BASE}{path}", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()

st.set_page_config(page_title="EcoSentia", layout="centered", page_icon="▪")

# ── 1. Theme State & Sidebar ──────────────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

with st.sidebar:
    st.markdown("## ◒ Appearance")
    is_dark = st.toggle("Dark Mode", value=st.session_state.dark_mode)
    if is_dark != st.session_state.dark_mode:
        st.session_state.dark_mode = is_dark
        st.rerun()
    st.divider()
    st.markdown("## ⌗ About\nEcoSentia evaluates biomimetic design claims against literature.")

dm = st.session_state.dark_mode

# ── 2. Symmetrical Pro UI/UX Palette ──────────────────────────────────────────
if dm:
    T = {
        "bg": "#0f172a",
        "panel": "#1e293b",
        "text": "#f8fafc",
        "border": "#334155",
        "hover": "#475569",
        "icon": "#f8fafc"
    }
else:
    T = {
        "bg": "#f8fafc",
        "panel": "#ffffff",
        "text": "#0f172a",
        "border": "#cbd5e1",
        "hover": "#f1f5f9",
        "icon": "#0f172a"
    }

# ── 3. Deep CSS Architecture ──────────────────────────────────────────────────
st.markdown(f"""
<style>
/* Base Elements */
.stApp, .main {{ background-color: {T['bg']} !important; }}
[data-testid="stSidebar"] {{ background-color: {T['panel']} !important; border-right: 1px solid {T['border']}; }}
p, span, h1, h2, h3, h4, label, div {{ color: {T['text']} !important; }}

/* Inputs & Textareas */
input, textarea, div[data-baseweb="select"] > div {{
    background-color: {T['panel']} !important;
    color: {T['text']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 6px !important;
}}

/* FIX FOR DROPDOWN ARROW (CARET) */
div[data-baseweb="select"] svg {{
    fill: {T['icon']} !important;
    color: {T['icon']} !important;
}}

/* FIX FOR DROPDOWNS LIST (POPOVERS) */
div[data-baseweb="popover"], div[data-baseweb="popover"] > div {{
    background-color: {T['panel']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 6px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
}}
ul[data-baseweb="menu"], ul[role="listbox"] {{ background-color: {T['panel']} !important; }}
li[role="option"] {{ background-color: {T['panel']} !important; color: {T['text']} !important; }}
li[role="option"]:hover, li[aria-selected="true"] {{ background-color: {T['hover']} !important; }}

/* FIX FOR TOOLTIPS */
[data-testid="stTooltipContent"], div[role="tooltip"], div[data-baseweb="tooltip"] > div {{
    background-color: #111827 !important; 
    color: #ffffff !important;
    border: 1px solid #374151 !important;
    border-radius: 6px !important;
    padding: 8px 12px !important;
}}
[data-testid="stTooltipContent"] * {{ color: #ffffff !important; font-size: 13px !important; }}

/* Panels, Expanders, Metrics */
[data-testid="metric-container"], details, .stCodeBlock {{
    background-color: {T['panel']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 6px !important;
}}
details summary, details div {{ background-color: {T['panel']} !important; }}
code, pre {{ background-color: {T['hover']} !important; border: none !important; }}
hr {{ border-color: {T['border']} !important; opacity: 0.6; }}

/* Overriding Streamlit Alert Box Styles to be minimal */
[data-testid="stAlert"] {{ background-color: {T['panel']} !important; border: 1px solid {T['border']} !important; }}
</style>
""", unsafe_allow_html=True)

# ── 4. Dynamic Vector Logo (No Emojis) ────────────────────────────────────────
st.markdown(f"""
<div style="display:flex; align-items:center; gap:15px; margin-bottom:20px;">
  <svg width="65" height="65" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <radialGradient id="g" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="rgba(99,102,241,0.4)"/><stop offset="100%" stop-color="rgba(99,102,241,0)"/>
      </radialGradient>
      <style>
        .aura {{ animation: p 3.5s infinite alternate ease-in-out; transform-origin: center; }}
        @keyframes p {{ 0% {{ transform: scale(0.8); opacity: 0.4; }} 100% {{ transform: scale(1.1); opacity: 1; }} }}
        .hm {{ fill: none; stroke: {T['text']}; stroke-width: 3.5; stroke-linecap: round; stroke-linejoin: round; }}
        .lf {{ fill: none; stroke: #10b981; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }}
      </style>
    </defs>
    <circle class="aura" cx="50" cy="45" r="35" fill="url(#g)"/>
    <path class="lf" d="M50 85 C80 80, 85 45, 50 15 C65 40, 65 65, 50 85 Z"/>
    <line class="hm" x1="50" y1="35" x2="50" y2="85"/>
    <path class="hm" d="M30 25 L70 25 L60 35 L40 35 Z"/>
    <circle cx="50" cy="15" r="3.5" fill="#6366f1"/>
  </svg>
  <div>
    <div style="font-size:30px; font-weight:300; letter-spacing:2px; color:{T['text']}; line-height:1.1;">EcoSentia</div>
    <div style="font-size:11.5px; letter-spacing:1px; opacity:0.65; color:{T['text']}; margin-top:4px;">EVIDENCE STUDIO · V0.3</div>
  </div>
</div>
""", unsafe_allow_html=True)
st.divider()

# ── 5. Main UI Configuration ──────────────────────────────────────────────────
st.markdown("#### Configuration")
c1, c2 = st.columns(2)
with c1: preset_ui = st.selectbox("Preset", ["Fog", "EV"], help="Select a domain logic preset.")
with c2: lens_ui = st.selectbox("Evaluation Lens", ["Mechanism", "Context", "Scale", "Manufacturability", "Safety"], help="Choose analytical perspective.")

claim = st.text_area("Design Claim", value="A painless transdermal drug delivery patch utilizing microneedles that mimic the geometry and vibrational insertion mechanism of a mosquito proboscis.", height=90, help="Paste biomimetic concept here.")

c3, c4 = st.columns(2)
with c3: source = st.selectbox("Literature Source", ["Both", "PubMed", "OpenAlex"], help="Databases to search.")
with c4: max_results = st.slider("Max Results Per Source", 1, 10, 5, help="Limit to avoid API timeouts.")

pld = {"session_id": "main_session", "preset": preset_ui.lower(), "project": "", "claim": claim, "lens": lens_ui.lower(), "source": source, "max_results": max_results}
st.divider()

# ── Step 1 ────────────────────────────────────────────────────────────────────
st.subheader("Step 1: Refine Search Query", help="Translates the design claim into Boolean operators.")
if st.button("Refine Query"):
    with st.spinner("Refining..."):
        try:
            st.session_state["refined_query"] = api_post("/evidence/refine-query", pld)["refined_query"]
            st.success("Query Refined.", icon="✓")
        except Exception as e: st.error(f"Error: {e}", icon="✕")

q_text = st.text_area("Active Query", value=st.session_state.get("refined_query", ""), height=80, help="Editable Boolean query.")
st.divider()

# ── Step 2 ────────────────────────────────────────────────────────────────────
st.subheader("Step 2: Run Evidence Scan", help="Searches databases using the Active Query.")
if st.button("Execute Scan"):
    with st.spinner("Querying..."):
        try:
            data = api_post("/evidence/scan", {**pld, "query_text": q_text})
            st.session_state["scan"] = data
            st.success("Scan Complete.", icon="✓")
            snap = data["snapshot"]
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Records", snap["combined_count"])
            m2.metric("Direct Matches", snap["direct_hits"])
            m3.metric("Support Level", snap.get("support_level", "—").title())
            st.info(snap["summary"], icon="▪")
            if snap.get("top_titles"):
                with st.expander("Top Retrieved Titles"):
                    for t in snap["top_titles"]: st.write(f"- {t}")
        except Exception as e: st.error(f"Error: {e}", icon="✕")
st.divider()

# ── Step 3 ────────────────────────────────────────────────────────────────────
st.subheader("Step 3: Generate Evidence-Aware Prompts", help="Builds structured LLM prompts based on the retrieved evidence.")
if "scan" not in st.session_state:
    st.warning("Please complete Step 2 first.", icon="⚠")
else:
    if st.button("Generate Prompts"):
        with st.spinner("Generating..."):
            try:
                payload_prompts = {
                    "preset": preset_ui.lower(), 
                    "lens": lens_ui.lower(), 
                    "claim": claim, 
                    "query_text": st.session_state["scan"]["query_text"], 
                    "snapshot": st.session_state["scan"]["snapshot"]
                }
                st.session_state["prompts"] = api_post("/evidence/prompts", payload_prompts)["prompts"]
            except Exception as e: st.error(f"Error: {e}", icon="✕")

    if "prompts" in st.session_state:
        p = st.session_state["prompts"]
        lvl = p.get("support_level", "none")
        
        if lvl == "none":
            st.error(f"**Support: {lvl.title()}**\n\n{p['evidence_note']}", icon="✕")
        elif lvl in ["limited", "indirect"]:
            st.warning(f"**Support: {lvl.title()}**\n\n{p['evidence_note']}", icon="⚠")
        elif lvl == "moderate":
            st.info(f"**Support: {lvl.title()}**\n\n{p['evidence_note']}", icon="▪")
        else:
            st.success(f"**Support: {lvl.title()}**\n\n{p['evidence_note']}", icon="✓")

        if p.get("detected_biases"):
            with st.expander("Translation Risks", expanded=True):
                for b in p["detected_biases"]:
                    # Handle robust parsing for dict structure
                    b_name = b.get("bias", "") if isinstance(b, dict) else str(b)
                    b_exp = b.get("explanation", "") if isinstance(b, dict) else ""
                    st.warning(f"**{b_name}**: {b_exp}", icon="⚠")
        else: 
            st.success("No Risk Patterns Detected.", icon="✓")

        st.markdown("#### Prompts")
        with st.expander("Master Prompt", expanded=True): st.code(p.get("master_prompt", ""))
        with st.expander("Counter Prompt"): st.code(p.get("counter_prompt", ""))
        with st.expander("Uncertainty Mapping"): st.code(p.get("uncertainty_prompt", ""))
        with st.expander("Redesign Prompt"): st.code(p.get("redesign_prompt", ""))
st.divider()

# ── Step 4 ────────────────────────────────────────────────────────────────────
st.subheader("Step 4: Full Multi-Lens Audit", help="Runs the evaluation across all 5 lenses automatically.")
if st.button("Execute Full Audit"):
    with st.spinner("Scanning all lenses..."):
        try:
            st.session_state["lens_matrix"] = api_post("/evidence/scan-all-lenses", pld)["lens_matrix"]
        except Exception as e: st.error(f"Error: {e}", icon="✕")

if "lens_matrix" in st.session_state:
    mx = st.session_state["lens_matrix"]
    rows = []
    for k, v in mx.items():
        if "error" in v: 
            rows.append({"Lens": k.capitalize(), "Support": "Error", "Risks": v["error"]})
        else:
            biases = v.get("detected_biases", [])
            risk_str = ", ".join(b.get("bias", "") if isinstance(b, dict) else str(b) for b in biases) if biases else "None"
            rows.append({"Lens": k.capitalize(), "Support": v["support_level"].capitalize(), "Risks": risk_str})
    
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), "ecosentia_matrix.csv", "text/csv")