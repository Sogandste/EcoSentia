# streamlit_app.py
# EcoSentia Evidence & Interrogation Layer v0.3

import os
import json
from datetime import datetime
import requests
import streamlit as st
import pandas as pd
from fpdf import FPDF

# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

API_BASE = os.getenv("ECOSENTIA_API_URL", "https://ecosentia.onrender.com")
st.set_page_config(
    page_title="EcoSentia Evidence Layer",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
# Session State Initialization
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULTS = {
    "theme_mode": "Dark",
    "compare_mode": False,
}

for key, val in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ══════════════════════════════════════════════════════════════════════════════
# Theme System
# ══════════════════════════════════════════════════════════════════════════════

def get_theme():
    dark = st.session_state.theme_mode == "Dark"
    if dark:
        return {
            "bg": "#0b1120", "panel": "#111827", "panel2": "#0f172a",
            "card": "#172033", "text": "#e5e7eb", "muted": "#94a3b8",
            "border": "rgba(148,163,184,0.18)", "accent": "#3b82f6",
            "input_bg": "#0f172a",
            "ok_bg": "rgba(34,197,94,0.10)", "ok_border": "rgba(34,197,94,0.28)",
            "warn_bg": "rgba(245,158,11,0.10)", "warn_border": "rgba(245,158,11,0.30)",
            "info_bg": "rgba(59,130,246,0.10)", "info_border": "rgba(59,130,246,0.30)",
            "danger_bg": "rgba(239,68,68,0.10)", "danger_border": "rgba(239,68,68,0.30)",
        }
    return {
        "bg": "#f8fafc", "panel": "#ffffff", "panel2": "#f8fafc",
        "card": "#ffffff", "text": "#0f172a", "muted": "#475569",
        "border": "rgba(15,23,42,0.10)", "accent": "#2563eb",
        "input_bg": "#ffffff",
        "ok_bg": "rgba(34,197,94,0.08)", "ok_border": "rgba(34,197,94,0.22)",
        "warn_bg": "rgba(245,158,11,0.10)", "warn_border": "rgba(245,158,11,0.28)",
        "info_bg": "rgba(59,130,246,0.08)", "info_border": "rgba(59,130,246,0.22)",
        "danger_bg": "rgba(239,68,68,0.08)", "danger_border": "rgba(239,68,68,0.22)",
    }


T = get_theme()


# ══════════════════════════════════════════════════════════════════════════════
# CSS Injection (cached to avoid repeated regeneration)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data
def get_css(theme_mode: str) -> str:
    t = get_theme()
    return f"""<style>
    .stApp {{ background: {t['bg']}; }}
    html, body, [class*="css"] {{ color: {t['text']}; }}
    .block-container {{ padding-top:1.4rem; max-width:1260px; }}
    .panel {{ background:linear-gradient(180deg,{t['panel']},{t['panel2']}); border:1px solid {t['border']}; border-radius:14px; padding:16px 18px; margin-bottom:16px; }}
    .section-title {{ font-size:12px; font-weight:700; color:{t['muted']}; text-transform:uppercase; letter-spacing:0.6px; margin-bottom:8px; }}
    .metric-card {{ background:{t['card']}; border:1px solid {t['border']}; border-radius:12px; padding:12px 14px; }}
    .soft-info {{ background:{t['info_bg']}; border:1px solid {t['info_border']}; border-left:4px solid {t['accent']}; border-radius:10px; padding:12px 14px; margin:8px 0 14px 0; }}
    .checklist-panel {{ background:{t['warn_bg']}; border:1px solid {t['warn_border']}; border-left:4px solid #f59e0b; border-radius:10px; padding:14px 16px; margin-top:12px; margin-bottom:10px; }}
    .checklist-title {{ color:#d97706; font-weight:700; font-size:12px; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px; display:block; }}
    .prompt-box {{ background:{t['card']}; border:1px solid {t['border']}; border-radius:12px; padding:12px 14px; font-family:monospace; font-size:13px; white-space:pre-wrap; line-height:1.55; }}
    .matrix-table {{ width:100%; border-collapse:collapse; border:1px solid {t['border']}; border-radius:10px; overflow:hidden; }}
    .matrix-table th {{ background:rgba(59,130,246,0.08); color:{t['text']}; text-align:left; padding:10px 12px; font-size:12px; text-transform:uppercase; border-bottom:1px solid {t['border']}; }}
    .matrix-table td {{ padding:10px 12px; border-bottom:1px solid {t['border']}; color:{t['text']}; font-size:13px; }}
    .badge {{ display:inline-block; padding:3px 8px; border-radius:999px; font-size:11px; font-weight:700; }}
    .badge-direct {{ background:rgba(34,197,94,0.10); color:#16a34a; }}
    .badge-moderate {{ background:rgba(59,130,246,0.10); color:#2563eb; }}
    .badge-indirect {{ background:rgba(245,158,11,0.12); color:#d97706; }}
    .badge-limited, .badge-none {{ background:rgba(148,163,184,0.10); color:{t['muted']}; }}
    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, textarea, input {{ background:{t['input_bg']} !important; color:{t['text']} !important; }}
    .stTextArea textarea, .stTextInput input {{ background:{t['input_bg']} !important; color:{t['text']} !important; border:1px solid {t['border']} !important; }}
    .stRadio label, .stSelectbox label, .stSlider label, .stTextInput label, .stTextArea label {{ color:{t['text']} !important; font-weight:600 !important; }}
    .stExpander {{ border:1px solid {t['border']} !important; border-radius:12px !important; background:{t['card']} !important; }}
    </style>"""


st.markdown(get_css(st.session_state.theme_mode), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# API Communication Layer
# ══════════════════════════════════════════════════════════════════════════════

def api_post(path: str, payload: dict, timeout: int = 120) -> dict:
    """Send POST request to API with error handling."""
    try:
        resp = requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        st.error(f"⏱️ Request timed out after {timeout}s. Try reducing max results or using a single source.")
        return {"ok": False, "error": "timeout"}
    except requests.exceptions.ConnectionError:
        st.error(f"🔌 Cannot connect to API at {API_BASE}. Is the backend running?")
        return {"ok": False, "error": "connection"}
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("detail", {}).get("message", str(e))
        except Exception:
            detail = str(e)
        st.error(f"❌ API Error: {detail}")
        return {"ok": False, "error": detail}


def api_health() -> dict:
    """Check API health status."""
    try:
        return requests.get(f"{API_BASE}/health", timeout=10).json()
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# PDF Report Generator
# ══════════════════════════════════════════════════════════════════════════════

def pdf_safe(text) -> str:
    """Sanitize text for PDF output (latin-1 compatible)."""
    if text is None:
        return ""
    text = str(text)
    replacements = {
        "\u2014": "-", "\u2013": "-", "\u2212": "-",
        "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'",
        "\u2022": "-", "\u2026": "...", "\u00a0": " ",
        "\u2192": "->", "\u2190": "<-", "\u2265": ">=", "\u2264": "<=",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf_report(claim, lens, preset, scan_snapshot, prompts, lens_matrix) -> bytes:
    """Generate a comprehensive PDF report."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, pdf_safe("EcoSentia - Evidence Report"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6, pdf_safe(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        f"Lens: {lens} | Domain: {preset}"
    ), ln=True)
    pdf.set_text_color(15, 23, 42)
    pdf.ln(4)

    # Claim
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, pdf_safe("Design Claim"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, pdf_safe(claim))
    pdf.ln(4)

    # Evidence Scan
    if scan_snapshot:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, pdf_safe("Evidence Scan Results"), ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, pdf_safe(f"Records: {scan_snapshot.get('combined_count', '-')}"), ln=True)
        pdf.cell(0, 6, pdf_safe(f"Direct Hits: {scan_snapshot.get('direct_hits', '-')}"), ln=True)
        pdf.cell(0, 6, pdf_safe(f"Support: {str(scan_snapshot.get('support_level', '-')).title()}"), ln=True)
        pdf.multi_cell(0, 6, pdf_safe(f"Summary: {scan_snapshot.get('summary', '')}"))

        # Top records
        top_recs = scan_snapshot.get("top_records", [])
        if top_recs:
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, pdf_safe("Top Retrieved Records:"), ln=True)
            pdf.set_font("Helvetica", "", 9)
            for i, rec in enumerate(top_recs[:5], 1):
                title = rec.get("title", "Untitled")
                score = rec.get("score", "")
                source = rec.get("source", "").title()
                direct = " [DIRECT]" if rec.get("is_direct_hit") else ""
                pdf.multi_cell(0, 5, pdf_safe(
                    f"  {i}. {title} ({source}, score={score}){direct}"
                ))
        pdf.ln(4)

    # Prompts
    if prompts:
        prompt_sections = [
            ("Master Prompt", "master_prompt"),
            ("Counter-Challenge", "counter_prompt"),
            ("Uncertainty Mapping", "uncertainty_prompt"),
            ("Redesign Prompt", "redesign_prompt"),
        ]
        for title, key in prompt_sections:
            if prompts.get(key):
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, pdf_safe(title), ln=True)
                pdf.set_font("Courier", "", 8)
                pdf.multi_cell(0, 5, pdf_safe(prompts[key]))
                pdf.ln(3)

        # Checklist
        if prompts.get("look_for"):
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, pdf_safe(f"Checklist ({lens.title()} Lens)"), ln=True)
            pdf.set_font("Helvetica", "", 10)
            for item in prompts["look_for"]:
                pdf.multi_cell(0, 6, pdf_safe(f"  [ ] {item}"))
            pdf.ln(3)

        # Detected biases
        if prompts.get("detected_biases"):
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, pdf_safe("Detected Risk Patterns"), ln=True)
            pdf.set_font("Helvetica", "", 10)
            for b in prompts["detected_biases"]:
                if isinstance(b, dict):
                    pdf.multi_cell(0, 6, pdf_safe(f"  - {b.get('bias', '')}: {b.get('explanation', '')}"))
            pdf.ln(3)

    # Lens Matrix
    if lens_matrix:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, pdf_safe("Multi-Lens Matrix"), ln=True)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(40, 7, pdf_safe("Lens"), border=1)
        pdf.cell(30, 7, pdf_safe("Support"), border=1)
        pdf.cell(120, 7, pdf_safe("Risk Patterns"), border=1)
        pdf.ln()
        pdf.set_font("Helvetica", "", 9)
        for ln_name, result in lens_matrix.items():
            if "error" in result and result["error"]:
                pdf.cell(40, 7, pdf_safe(ln_name.title()), border=1)
                pdf.cell(30, 7, pdf_safe("Error"), border=1)
                pdf.cell(120, 7, pdf_safe(str(result["error"])[:80]), border=1)
            else:
                det = result.get("detected_biases", [])
                biases_str = ", ".join(
                    b["bias"] if isinstance(b, dict) else str(b) for b in det
                ) if det else "None"
                pdf.cell(40, 7, pdf_safe(ln_name.title()), border=1)
                pdf.cell(30, 7, pdf_safe(str(result.get("support_level", "-")).title()), border=1)
                pdf.cell(120, 7, pdf_safe(biases_str[:80]), border=1)
            pdf.ln()

    try:
        raw = pdf.output()
    except TypeError:
        raw = pdf.output(dest="S")
    return bytes(raw) if not isinstance(raw, bytes) else raw


# ══════════════════════════════════════════════════════════════════════════════
# UI Components
# ══════════════════════════════════════════════════════════════════════════════

def support_badge(level: str) -> str:
    """Generate HTML badge for support level."""
    level = (level or "none").lower()
    valid = ("direct", "moderate", "indirect", "limited", "none")
    cls = f"badge-{level}" if level in valid else "badge-none"
    return f'<span class="badge {cls}">{level.title()}</span>'


def render_snapshot(snap: dict):
    """Render evidence scan results."""
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="section-title">Combined Records</div>'
            f'<div style="font-size:24px;font-weight:700;">{snap.get("combined_count", 0)}</div>'
            f'</div>', unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="section-title">Direct Hits</div>'
            f'<div style="font-size:24px;font-weight:700;">{snap.get("direct_hits", 0)}</div>'
            f'</div>', unsafe_allow_html=True
        )
    with c3:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="section-title">Support Level</div>'
            f'<div style="font-size:18px;">{support_badge(snap.get("support_level", "none"))}</div>'
            f'</div>', unsafe_allow_html=True
        )

    st.markdown(
        f'<div class="soft-info">'
        f'<div class="section-title">Evidence Summary</div>'
        f'<div style="font-size:14px;line-height:1.65;">{snap.get("summary", "")}</div>'
        f'</div>', unsafe_allow_html=True
    )

    # Top Records
    if snap.get("top_records"):
        with st.expander(" Top Retrieved Records", expanded=True):
            for r in snap["top_records"]:
                title = r.get("title", "Untitled")
                url = r.get("url", "")
                src = r.get("source", "").title()
                year = r.get("year", "")
                score = r.get("score", "")
                matched = r.get("matched_terms", [])
                is_direct = r.get("is_direct_hit", False)

                # Title with link
                prefix = "🟢 " if is_direct else "⚪ "
                if url:
                    st.markdown(f"{prefix}[{title}]({url})")
                else:
                    st.write(f"{prefix}{title}")

                # Metadata line
                meta_parts = [src]
                if year:
                    meta_parts.append(str(year))
                if score:
                    meta_parts.append(f"Score: {score}")
                if matched:
                    meta_parts.append(f"Matched: {', '.join(matched[:4])}")
                st.caption(" · ".join(meta_parts))

    elif snap.get("top_titles"):
        with st.expander(" Top Retrieved Titles", expanded=True):
            for t in snap["top_titles"]:
                st.write(f"- {t}")


def render_matrix(pid: str, claim: str, lens_ui: str, preset_ui: str, matrix: dict):
    """Render the multi-lens analysis matrix."""
    level_order = {"direct": 4, "moderate": 3, "indirect": 2, "limited": 1, "none": 0}
    rows = []

    for ln, res in matrix.items():
        if res.get("error"):
            rows.append({
                "Lens": ln.title(),
                "Support Level": "Error",
                "Risk Patterns": str(res["error"]),
                "_o": -1,
            })
        else:
            sup = res.get("support_level", "none")
            det = res.get("detected_biases", [])
            risks = ", ".join(
                b["bias"] if isinstance(b, dict) else str(b) for b in det
            ) if det else "None"
            rows.append({
                "Lens": ln.title(),
                "Support Level": sup.title(),
                "Risk Patterns": risks,
                "_o": level_order.get(sup, 0),
            })

    df = pd.DataFrame(rows).sort_values("_o", ascending=False)

    # Build HTML table
    html_rows = ""
    for _, row in df.iterrows():
        lvl = row["Support Level"].lower()
        badge = support_badge(lvl) if lvl != "error" else '<span class="badge badge-none">Error</span>'
        html_rows += f"<tr><td>{row['Lens']}</td><td>{badge}</td><td>{row['Risk Patterns']}</td></tr>"

    st.markdown("#### Analytical Lens Matrix")
    st.markdown(
        f'<table class="matrix-table">'
        f'<thead><tr><th>Lens</th><th>Support</th><th>Risk Patterns</th></tr></thead>'
        f'<tbody>{html_rows}</tbody></table><br>',
        unsafe_allow_html=True,
    )

    # Export buttons
    df_export = df.drop(columns=["_o"])
    ec1, ec2, ec3 = st.columns(3)

    with ec1:
        st.download_button(
            "📥 Export CSV", df_export.to_csv(index=False).encode(),
            f"matrix_{pid}.csv", "text/csv", key=f"csv_{pid}",
        )
    with ec2:
        json_data = json.dumps([
            {"lens": r["Lens"], "support": r["Support Level"], "risks": r["Risk Patterns"]}
            for r in rows
        ], indent=2, ensure_ascii=False)
        st.download_button(
            "📥 Export JSON", json_data.encode(),
            f"matrix_{pid}.json", "application/json", key=f"json_{pid}",
        )
    with ec3:
        snap_data = st.session_state.get(f"scan_{pid}", {}).get("snapshot")
        prompts_data = st.session_state.get(f"prompts_{pid}")
        try:
            pdf_bytes = generate_pdf_report(claim, lens_ui, preset_ui, snap_data, prompts_data, matrix)
            st.download_button(
                "Export PDF", pdf_bytes,
                f"report_{pid}.pdf", "application/pdf", key=f"pdf_{pid}",
            )
        except Exception as e:
            st.caption(f"PDF unavailable: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Main Evaluation Panel
# ══════════════════════════════════════════════════════════════════════════════

def render_panel(
    pid: str,
    preset_ui: str,
    domain_mode: str,
    lens_ui: str,
    claim: str,
    source: str,
    max_results: int,
    biological_model: str = "",
    target_function: str = "",
    application_context: str = "",
    mechanism_keywords: str = "",
    exclude_terms: str = "",
):
    """Render a complete evaluation panel (query → scan → prompts → matrix)."""
    st.markdown('<div class="panel">', unsafe_allow_html=True)

    payload_base = {
        "session_id": f"st-{pid}",
        "preset": preset_ui.lower() if preset_ui.lower() in ("fog", "ev") else "custom",
        "project": "",
        "claim": claim,
        "lens": lens_ui.lower(),
        "source": source,
        "max_results": max_results,
        "domain_mode": domain_mode,
        "biological_model": biological_model,
        "target_function": target_function,
        "application_context": application_context,
        "mechanism_keywords": mechanism_keywords,
        "exclude_terms": exclude_terms,
    }

    # ─── Step 1: Query Refinement ─────────────────────────────────────────
    st.markdown("#### Step 1 — Refine Query")

    # Initialize query state
    qk = f"query_state_{pid}"
    if qk not in st.session_state:
        st.session_state[qk] = ""

    r1, r2 = st.columns(2)
    with r1:
        if st.button(" Refine Query", key=f"ref_{pid}", use_container_width=True):
            data = api_post("/evidence/refine-query", payload_base)
            if data.get("ok"):
                st.session_state[qk] = data.get("refined_query", "")
                st.rerun()

    with r2:
        if st.button("📝 Use Claim As Query", key=f"def_{pid}", use_container_width=True):
            st.session_state[qk] = claim
            st.rerun()

    # Query text area — use callback to sync state properly
    def _on_query_change():
        st.session_state[qk] = st.session_state[f"_qa_widget_{pid}"]

    st.text_area(
        "Active Query",
        value=st.session_state[qk],
        height=110,
        key=f"_qa_widget_{pid}",
        on_change=_on_query_change,
    )

    # ─── Step 2: Evidence Scan ────────────────────────────────────────────
    st.markdown("#### Step 2 — Evidence Scan")

    if st.button("▶️ Run Scan", key=f"scan_btn_{pid}", use_container_width=True):
        if not st.session_state[qk].strip():
            st.warning(" Query is empty. Click 'Refine Query' or enter one manually.")
        else:
            with st.spinner("Scanning literature databases..."):
                p = {**payload_base, "query_text": st.session_state[qk]}
                data = api_post("/evidence/scan", p)
                if data.get("ok"):
                    st.session_state[f"scan_{pid}"] = data

    if f"scan_{pid}" in st.session_state:
        scan_data = st.session_state[f"scan_{pid}"]
        if scan_data.get("ok"):
            render_snapshot(scan_data["snapshot"])

    # ─── Step 3: Generate Prompts ─────────────────────────────────────────
    st.markdown("#### Step 3 — Generate Prompts")

    if st.button(" Generate Prompts", key=f"pr_btn_{pid}", use_container_width=True):
        if f"scan_{pid}" not in st.session_state:
            st.warning(" Run an evidence scan first (Step 2).")
        else:
            scan_data = st.session_state[f"scan_{pid}"]
            if not scan_data.get("ok"):
                st.warning(" Previous scan had errors. Please re-run.")
            else:
                with st.spinner("Generating evidence-aware prompts..."):
                    p = {
                        "preset": payload_base["preset"],
                        "lens": lens_ui.lower(),
                        "claim": claim,
                        "query_text": scan_data["query_text"],
                        "snapshot": scan_data["snapshot"],
                    }
                    data = api_post("/evidence/prompts", p)
                    if data.get("ok"):
                        st.session_state[f"prompts_{pid}"] = data.get("prompts", {})

    if f"prompts_{pid}" in st.session_state:
        p = st.session_state[f"prompts_{pid}"]

        # Evidence Note
        if p.get("evidence_note"):
            st.markdown(
                f'<div class="soft-info">'
                f'<div class="section-title">Evidence Note</div>'
                f'<div style="font-size:14px;line-height:1.65;">{p["evidence_note"]}</div>'
                f'</div>', unsafe_allow_html=True
            )

        # Prompt sections
        prompt_tabs = st.tabs(["Master", "Counter", "Uncertainty", "Redesign"])
        prompt_keys = [
            ("Master Prompt", "master_prompt"),
            ("Counter-Challenge", "counter_prompt"),
            ("Uncertainty Mapping", "uncertainty_prompt"),
            ("Redesign", "redesign_prompt"),
        ]

        for tab, (title, key) in zip(prompt_tabs, prompt_keys):
            with tab:
                if p.get(key):
                    st.markdown(f'<div class="prompt-box">{p[key]}</div>', unsafe_allow_html=True)
                    st.button(
                        f"📋 Copy {title}",
                        key=f"copy_{key}_{pid}",
                        help="Copy prompt to clipboard (use browser copy after selecting)",
                    )

        # Checklist
        if p.get("look_for"):
            items_html = "".join(f"<li>{str(i)}</li>" for i in p["look_for"])
            st.markdown(
                f'<div class="checklist-panel" style="color:{T["text"]};">'
                f'<span class="checklist-title"> Checklist For AI Response ({lens_ui} Lens)</span>'
                f'<ul style="margin:0 0 0 18px;padding:0;line-height:1.7;">{items_html}</ul>'
                f'</div>', unsafe_allow_html=True
            )

        # Detected Biases
        if p.get("detected_biases"):
            with st.expander("⚠️ Detected Risk Patterns", expanded=False):
                for b in p["detected_biases"]:
                    if isinstance(b, dict):
                        bias_name = b.get("bias", "")
                        if bias_name == "No Strong Pattern Detected":
                            st.success(f"{bias_name}")
                        else:
                            st.warning(f"**{bias_name}**")
                        st.caption(b.get("explanation", ""))
                    else:
                        st.write(str(b))

    # ─── Step 4: Full Lens Audit ──────────────────────────────────────────
    st.markdown("#### 🧬 Step 4 — Full Lens Audit")
    st.caption("Scans claim across all 5 analytical lenses. May take 30–90 seconds.")

    if st.button("🔬 Scan All Lenses", key=f"all_{pid}", use_container_width=True):
        if not st.session_state[qk].strip():
            st.warning(" Query is empty.")
        else:
            with st.spinner("Running multi-lens audit (this may take a minute)..."):
                p = {**payload_base, "query_text": st.session_state[qk]}
                data = api_post("/evidence/scan-all-lenses", p, timeout=180)
                if data.get("ok"):
                    st.session_state[f"matrix_{pid}"] = data.get("lens_matrix", {})

    if f"matrix_{pid}" in st.session_state:
        render_matrix(pid, claim, lens_ui, domain_mode, st.session_state[f"matrix_{pid}"])

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### Interface Settings")
    st.toggle("Compare Mode", key="compare_mode", help="Evaluate two claims side-by-side.")

    if st.button(" Toggle Dark / Light", use_container_width=True):
        st.session_state.theme_mode = "Light" if st.session_state.theme_mode == "Dark" else "Dark"
        st.rerun()

    st.divider()
    st.markdown("### About")
    st.caption(
        "EcoSentia is a human-centered framework for augmented intelligence "
        "in biomimetic design. It mediates AI outputs with evidence from "
        "PubMed and OpenAlex."
    )
    st.caption("v0.3 · Academic Prototype")


# ══════════════════════════════════════════════════════════════════════════════
# Header
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;margin-top:4px;">
    <div style="width:48px;height:48px;border-radius:14px;
                background:radial-gradient(circle at 30% 30%,rgba(59,130,246,0.95),rgba(29,78,216,0.90));
                box-shadow:0 0 0 6px rgba(59,130,246,0.10),0 0 30px rgba(59,130,246,0.18);"></div>
    <div>
        <div style="font-size:24px;font-weight:700;color:{T['text']};line-height:1.1;">EcoSentia</div>
        <div style="font-size:11px;letter-spacing:1px;color:{T['muted']};text-transform:uppercase;
                    font-weight:600;margin-top:4px;">Evidence &amp; Interrogation Layer v0.3</div>
    </div>
</div>
""", unsafe_allow_html=True)

# API Status
health_data = api_health()
if health_data:
    st.markdown(
        f'<div class="soft-info">'
        f'<strong> API Status:</strong> Connected — {health_data.get("service", "")} '
        f'v{health_data.get("version", "")}'
        f'</div>', unsafe_allow_html=True
    )
else:
    st.markdown(
        f'<div class="soft-info" style="background:{T["danger_bg"]};border-color:{T["danger_border"]};'
        f'border-left-color:#ef4444;">'
        f'<strong> API Status:</strong> Not reachable at {API_BASE}. '
        f'Run: <code>uvicorn api:app --reload --port 8000</code>'
        f'</div>', unsafe_allow_html=True
    )


# ══════════════════════════════════════════════════════════════════════════════
# Configuration Panel
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("###  Configuration")

c1, c2 = st.columns(2)
with c1:
    domain_mode = st.radio("Domain Mode", ["Fog", "EV", "Custom"], horizontal=True)
with c2:
    lens_ui = st.selectbox(
        "Evaluation Lens",
        ["Mechanism", "Context", "Scale", "Manufacturability", "Safety"],
    )

c3, c4 = st.columns(2)
with c3:
    source = st.radio("Literature Source", ["Both", "PubMed", "OpenAlex"], horizontal=True)
with c4:
    max_results = st.slider("Max Results Per Source", 1, 10, 5)

preset_ui = domain_mode if domain_mode in ("Fog", "EV") else "Custom"

# Custom domain fields
biological_model = ""
target_function = ""
application_context = ""
mechanism_keywords = ""
exclude_terms = ""

if domain_mode == "Custom":
    st.markdown("#### Custom Domain Guidance")
    st.caption("Optional structured fields improve retrieval precision for open-ended claims.")

    x1, x2 = st.columns(2)
    with x1:
        biological_model = st.text_input(
            "Biological Model",
            placeholder="e.g., Gecko, Mussel, Lotus leaf",
        )
        application_context = st.text_input(
            "Application Context",
            placeholder="e.g., Wet biomedical surfaces, marine coating",
        )
    with x2:
        target_function = st.text_input(
            "Target Function",
            placeholder="e.g., Reversible adhesion, anti-fouling",
        )
        mechanism_keywords = st.text_input(
            "Mechanism Keywords",
            placeholder="e.g., microstructure, capillary adhesion",
        )

    exclude_terms = st.text_input(
        "Exclude Terms",
        placeholder="e.g., vaccine, cancer, remote sensing",
        help="Comma-separated terms to downrank or exclude from results.",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Main Content
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_CLAIMS = {
    "Fog": "A surface structure inspired by the Namib desert beetle for passive fog water collection and harvesting via wettability gradient.",
    "EV": "An extracellular vesicle-inspired nanoparticle for targeted drug delivery in inflammatory disease with immune evasion properties.",
    "Custom": "A gecko-inspired reversible adhesive patch for wet biomedical surfaces using microstructure arrays.",
}

if not st.session_state.compare_mode:
    # ─── Single Claim Mode ────────────────────────────────────────────────
    claim = st.text_area(
        "Design Claim",
        value=DEFAULT_CLAIMS.get(domain_mode, ""),
        height=100,
        key="main_claim",
    )

    render_panel(
        "main", preset_ui, domain_mode, lens_ui, claim, source, max_results,
        biological_model, target_function, application_context,
        mechanism_keywords, exclude_terms,
    )

else:
    # ─── Compare Mode ─────────────────────────────────────────────────────
    st.markdown(
        f'<div class="soft-info"> <strong>Comparison Mode</strong> — '
        f'Two independent claims evaluated side-by-side under the same lens.</div>',
        unsafe_allow_html=True,
    )

    lc, rc = st.columns(2)
    with lc:
        st.markdown("#### Claim A")
        claim_a = st.text_area(
            "Design Claim A",
            value=DEFAULT_CLAIMS.get(domain_mode, ""),
            height=90,
            key="claim_a",
        )
    with rc:
        st.markdown("#### Claim B")
        claim_b = st.text_area(
            "Design Claim B",
            value="A drag-reduction hull coating inspired by shark denticle microstructure for marine applications.",
            height=90,
            key="claim_b",
        )

    lp, rp = st.columns(2)
    with lp:
        render_panel(
            "A", preset_ui, domain_mode, lens_ui, claim_a, source, max_results,
            biological_model, target_function, application_context,
            mechanism_keywords, exclude_terms,
        )
    with rp:
        render_panel(
            "B", preset_ui, domain_mode, lens_ui, claim_b, source, max_results,
            biological_model, target_function, application_context,
            mechanism_keywords, exclude_terms,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Footer
# ══════════════════════════════════════════════════════════════════════════════

st.divider()
st.caption(
    "EcoSentia v0.3 · Evidence & Interrogation Layer · "
    "Human-centered augmented intelligence for biomimetic design · "
    f"Session: {datetime.now().strftime('%Y-%m-%d')}"
)