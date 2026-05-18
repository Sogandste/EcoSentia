from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TypedDict, cast

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from fpdf import FPDF

st.set_page_config(page_title="EcoSentia", layout="wide", page_icon="▪")

API_BASE = os.getenv("ECOSENTIA_API_URL", "https://ecosentia.onrender.com")
APP_TITLE = "EcoSentia"
APP_VERSION = "v0.5"
APP_ICON = "▪"
HTTP_TIMEOUT = 120
HEALTH_TIMEOUT = 10


class SupportLevelConfig(TypedDict):
    pct: int
    color: str
    label: str


class ThemeDict(TypedDict):
    bg: str
    panel: str
    text: str
    border: str
    hover: str
    icon: str
    text_muted: str
    shadow: str
    tooltip_bg: str
    tooltip_text: str
    focus_ring: str
    input_bg: str
    matrix_direct: str
    matrix_moderate: str
    matrix_limited: str
    matrix_none: str
    matrix_error: str
    badge_direct: str
    badge_moderate: str
    badge_limited: str
    badge_none: str


class HistoryEntry(TypedDict):
    time: str
    claim: str
    lens: str
    support: str


SUPPORT_LEVELS: Dict[str, SupportLevelConfig] = {
    "none": {"pct": 5, "color": "#ef4444", "label": "None"},
    "limited": {"pct": 30, "color": "#f59e0b", "label": "Limited"},
    "indirect": {"pct": 50, "color": "#f59e0b", "label": "Indirect"},
    "moderate": {"pct": 70, "color": "#3b82f6", "label": "Moderate"},
    "direct": {"pct": 100, "color": "#10b981", "label": "Direct"},
}

DEFAULT_CLAIMS: Dict[str, str] = {
    "Fog": (
        "A surface structure inspired by the Namib desert beetle "
        "for passive water collection and harvesting."
    ),
    "EV": (
        "An extracellular vesicle-inspired nanoparticle for targeted "
        "drug delivery in inflammatory disease."
    ),
    "Custom": (
        "A painless transdermal drug delivery patch utilizing microneedles "
        "that mimic the geometry and insertion mechanism of a mosquito proboscis."
    ),
}


def get_http_session() -> requests.Session:
    if "_http_session" not in st.session_state:
        st.session_state["_http_session"] = requests.Session()
    return cast(requests.Session, st.session_state["_http_session"])


def ensure_session_defaults() -> None:
    defaults: Dict[str, Any] = {
        "dark_mode": False,
        "compare_mode": False,
        "history": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def delete_keys(keys: List[str]) -> None:
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]


def safe_get(data: Any, *path: str, default: Any = None) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return default
        if key not in current:
            return default
        current = current[key]
    return current


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def ensure_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def coerce_bias_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def api_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    session = get_http_session()
    try:
        response = session.post(
            f"{API_BASE}{path}",
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected API response format at {path}: expected object.")
        return data
    except requests.HTTPError as exc:
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text if exc.response is not None else str(exc)
        raise RuntimeError(f"API error at {path}: {detail}") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Connection error at {path}: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"Invalid JSON response at {path}.") from exc


def get_api_health() -> str:
    if "api_health" in st.session_state:
        return cast(str, st.session_state["api_health"])

    session = get_http_session()
    try:
        health = session.get(f"{API_BASE}/health", timeout=HEALTH_TIMEOUT).json()
        if isinstance(health, dict):
            message = (
                f"API Connected · {health.get('service', 'EcoSentia API')} "
                f"· v{health.get('version', '')}"
            )
        else:
            message = f"API Connected · {API_BASE}"
    except Exception:
        message = f"API Not Reachable · {API_BASE}"

    st.session_state["api_health"] = message
    return message


def extract_refined_query(response: Dict[str, Any], fallback_claim: str) -> str:
    query = first_non_empty(
        response.get("refined_query"),
        response.get("query"),
        response.get("refined"),
        safe_get(response, "data", "refined_query"),
        safe_get(response, "data", "query"),
    )
    return str(query) if query else fallback_claim


def extract_scan_payload(response: Dict[str, Any], fallback_query: str) -> Tuple[Dict[str, Any], str]:
    snapshot = first_non_empty(
        response.get("snapshot"),
        safe_get(response, "data", "snapshot"),
        safe_get(response, "results", "snapshot"),
    )
    snapshot_dict = ensure_dict(snapshot)

    query_text = first_non_empty(
        response.get("query_text"),
        response.get("query"),
        safe_get(response, "data", "query_text"),
        safe_get(response, "results", "query_text"),
        fallback_query,
    )
    return snapshot_dict, str(query_text)


def extract_prompts_payload(response: Dict[str, Any]) -> Dict[str, Any]:
    prompts = first_non_empty(
        response.get("prompts"),
        safe_get(response, "data", "prompts"),
        response if "master_prompt" in response else None,
    )
    return ensure_dict(prompts)


def extract_lens_matrix(response: Dict[str, Any]) -> Dict[str, Any]:
    matrix = first_non_empty(
        response.get("lens_matrix"),
        response.get("matrix"),
        safe_get(response, "data", "lens_matrix"),
        safe_get(response, "results", "lens_matrix"),
    )
    return ensure_dict(matrix)


def get_theme(dark_mode: bool) -> ThemeDict:
    if dark_mode:
        return {
            "bg": "#0f172a",
            "panel": "#1e293b",
            "text": "#f1f5f9",
            "border": "#334155",
            "hover": "#2d3f55",
            "icon": "#f1f5f9",
            "text_muted": "#94a3b8",
            "shadow": "rgba(0,0,0,0.40)",
            "tooltip_bg": "#f8fafc",
            "tooltip_text": "#0f172a",
            "focus_ring": "rgba(148,163,184,0.30)",
            "input_bg": "#1e293b",
            "matrix_direct": "rgba(16,185,129,0.18)",
            "matrix_moderate": "rgba(59,130,246,0.18)",
            "matrix_limited": "rgba(245,158,11,0.18)",
            "matrix_none": "rgba(239,68,68,0.18)",
            "matrix_error": "rgba(239,68,68,0.10)",
            "badge_direct": "#34d399",
            "badge_moderate": "#60a5fa",
            "badge_limited": "#fbbf24",
            "badge_none": "#f87171",
        }

    return {
        "bg": "#f8fafc",
        "panel": "#ffffff",
        "text": "#0f172a",
        "border": "#94a3b8",
        "hover": "#f1f5f9",
        "icon": "#0f172a",
        "text_muted": "#475569",
        "shadow": "rgba(15,23,42,0.10)",
        "tooltip_bg": "#0f172a",
        "tooltip_text": "#f8fafc",
        "focus_ring": "rgba(15,23,42,0.12)",
        "input_bg": "#ffffff",
        "matrix_direct": "rgba(4,120,87,0.10)",
        "matrix_moderate": "rgba(29,78,216,0.10)",
        "matrix_limited": "rgba(180,83,9,0.10)",
        "matrix_none": "rgba(185,28,28,0.10)",
        "matrix_error": "rgba(185,28,28,0.05)",
        "badge_direct": "#065f46",
        "badge_moderate": "#1e3a8a",
        "badge_limited": "#92400e",
        "badge_none": "#991b1b",
    }


def inject_css(theme: ThemeDict) -> None:
    st.markdown(
        f"""
<style>
:root {{
  --text-color:{theme['text']}!important;
  --background-color:{theme['bg']}!important;
  --secondary-background-color:{theme['panel']}!important;
  --primary-color:{theme['text_muted']}!important;
}}

html, body, #root, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="stMainBlockContainer"] {{
  background:{theme['bg']}!important;
  color:{theme['text']}!important;
  font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif!important;
}}

.stMarkdown p, .stMarkdown span, .stMarkdown li, .stMarkdown h1,
.stMarkdown h2, .stMarkdown h3, .stMarkdown h4,
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] span,
label {{
  color:{theme['text']}!important;
}}

[data-testid="stCaptionContainer"] p, .stCaption p, small {{
  color:{theme['text_muted']}!important;
}}

hr {{
  border-top:1px solid {theme['border']}!important;
  opacity:1!important;
}}

[data-testid="stSidebar"], [data-testid="stSidebar"] > div {{
  background:{theme['panel']}!important;
  border-right:1.5px solid {theme['border']}!important;
}}

[data-testid="collapsedControl"], [data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] button, [data-testid="stSidebarCollapseButton"] button,
button[data-testid="baseButton-headerNoPadding"], button[kind="headerNoPadding"] {{
  background:{theme['panel']}!important;
  border:2px solid {theme['border']}!important;
  border-radius:9px!important;
  box-shadow:0 3px 10px {theme['shadow']}!important;
  opacity:1!important;
  visibility:visible!important;
}}

[data-testid="collapsedControl"] svg, [data-testid="stSidebarCollapseButton"] svg,
button[data-testid="baseButton-headerNoPadding"] svg, button[kind="headerNoPadding"] svg {{
  fill:{theme['icon']}!important;
  stroke:{theme['icon']}!important;
  color:{theme['icon']}!important;
  opacity:1!important;
}}

input[type="text"], input[type="number"], input[type="search"], textarea,
div[data-baseweb="select"] > div {{
  background:{theme['input_bg']}!important;
  color:{theme['text']}!important;
  border:1.5px solid {theme['border']}!important;
  border-radius:8px!important;
}}

input::placeholder, textarea::placeholder {{
  color:{theme['text_muted']}!important;
  opacity:.75!important;
}}

input:hover, textarea:hover, input:focus, textarea:focus,
div[data-baseweb="select"] > div:hover {{
  border-color:{theme['text_muted']}!important;
  box-shadow:0 0 0 3px {theme['focus_ring']}!important;
  outline:none!important;
}}

div[data-baseweb="select"] svg {{
  fill:{theme['icon']}!important;
  color:{theme['icon']}!important;
}}

div[data-baseweb="popover"] {{
  background:{theme['panel']}!important;
  border:1.5px solid {theme['border']}!important;
  border-radius:10px!important;
  box-shadow:0 12px 32px {theme['shadow']}!important;
}}

div[data-baseweb="popover"] ul,
div[data-baseweb="popover"] [role="listbox"],
div[data-baseweb="popover"] li,
li[role="option"] {{
  background:{theme['panel']}!important;
  color:{theme['text']}!important;
}}

li[role="option"]:hover, li[aria-selected="true"] {{
  background:{theme['hover']}!important;
}}

[data-testid="stExpander"] {{
  background:{theme['panel']}!important;
  border:1.5px solid {theme['border']}!important;
  border-radius:10px!important;
  box-shadow:0 3px 10px {theme['shadow']}!important;
  overflow:hidden!important;
  margin-bottom:10px!important;
}}

[data-testid="stExpander"] summary {{
  background:{theme['panel']}!important;
  padding:14px 18px!important;
}}

[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary div {{
  color:{theme['text']}!important;
  font-weight:600!important;
}}

[data-testid="stExpander"] > div > div {{
  background:{theme['bg']}!important;
  padding:16px 18px!important;
}}

[data-testid="metric-container"] {{
  background:{theme['panel']}!important;
  border:1.5px solid {theme['border']}!important;
  border-radius:10px!important;
  box-shadow:0 3px 10px {theme['shadow']}!important;
}}

[data-testid="stMetricValue"] > div {{
  color:{theme['text']}!important;
  font-weight:700!important;
}}

[data-testid="stMetricLabel"] > div {{
  color:{theme['text_muted']}!important;
}}

[data-testid="stAlert"] {{
  background:{theme['panel']}!important;
  border:1.5px solid {theme['border']}!important;
  border-radius:8px!important;
}}

[data-testid="stTooltipContent"], div[role="tooltip"] {{
  background:{theme['tooltip_bg']}!important;
  border:1px solid {theme['border']}!important;
  border-radius:8px!important;
}}

[data-testid="stTooltipContent"] p, [data-testid="stTooltipContent"] span,
div[role="tooltip"] p, div[role="tooltip"] span {{
  color:{theme['tooltip_text']}!important;
}}

.stButton > button, [data-testid="stDownloadButton"] > button {{
  background:{theme['panel']}!important;
  color:{theme['text']}!important;
  border:1.5px solid {theme['border']}!important;
  border-radius:8px!important;
  box-shadow:0 2px 5px {theme['shadow']}!important;
}}

.stCodeBlock {{
  background:{theme['bg']}!important;
  border:1.5px solid {theme['border']}!important;
  border-radius:8px!important;
}}

.stCodeBlock pre, .stCodeBlock code, .stCodeBlock span {{
  color:{theme['text']}!important;
}}

.risk-panel {{
  background:linear-gradient(135deg, rgba(249,115,22,.08), rgba(239,68,68,.08))!important;
  border:1px solid rgba(239,68,68,.25)!important;
  border-left:4px solid #ef4444!important;
  border-radius:8px!important;
  padding:14px 16px!important;
  margin-bottom:10px!important;
  line-height:1.65!important;
}}

.risk-title {{
  color:#ea580c!important;
  font-weight:700!important;
  margin-bottom:5px!important;
  display:block!important;
  font-size:12px!important;
  text-transform:uppercase!important;
}}

.matrix-table {{
  width:100%;
  border-collapse:separate;
  border-spacing:0;
  border:1.5px solid {theme['border']};
  border-radius:10px;
  overflow:hidden;
  box-shadow:0 4px 14px {theme['shadow']};
}}

.matrix-table thead tr {{
  background:{theme['hover']};
}}

.matrix-table thead th {{
  padding:11px 16px;
  text-align:left;
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:.6px;
  color:{theme['text_muted']}!important;
}}

.matrix-table tbody td {{
  padding:12px 16px;
  color:{theme['text']}!important;
  background:{theme['panel']};
}}

.badge {{
  display:inline-block;
  padding:3px 10px;
  border-radius:999px;
  font-size:12px;
  font-weight:700;
}}

.badge-direct   {{background:{theme['matrix_direct']};color:{theme['badge_direct']}!important;border:1px solid {theme['badge_direct']};}}
.badge-moderate {{background:{theme['matrix_moderate']};color:{theme['badge_moderate']}!important;border:1px solid {theme['badge_moderate']};}}
.badge-limited  {{background:{theme['matrix_limited']};color:{theme['badge_limited']}!important;border:1px solid {theme['badge_limited']};}}
.badge-indirect {{background:{theme['matrix_limited']};color:{theme['badge_limited']}!important;border:1px solid {theme['badge_limited']};}}
.badge-none     {{background:{theme['matrix_none']};color:{theme['badge_none']}!important;border:1px solid {theme['badge_none']};}}
.badge-error    {{background:{theme['matrix_error']};color:{theme['badge_none']}!important;border:1px solid {theme['badge_none']};}}

::-webkit-scrollbar {{ width:7px; }}
::-webkit-scrollbar-track {{ background:{theme['bg']}; }}
::-webkit-scrollbar-thumb {{ background:{theme['border']}; border-radius:999px; }}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_header(theme: ThemeDict) -> None:
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:28px;margin-top:8px;">
          <svg width="40" height="40" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <circle cx="50" cy="50" r="45" fill="none" stroke="{theme['text']}" stroke-width="2" opacity="0.15"/>
            <path d="M50 85 C80 80, 85 45, 50 15 C65 40, 65 65, 50 85 Z"
                  fill="none" stroke="{theme['text']}" stroke-width="2.5" stroke-linecap="round"/>
            <line x1="50" y1="35" x2="50" y2="85" fill="none"
                  stroke="{theme['text']}" stroke-width="2.5" stroke-linecap="round" opacity="0.8"/>
            <path d="M30 25 L70 25 L60 35 L40 35 Z"
                  fill="none" stroke="{theme['text']}" stroke-width="2.5" opacity="0.8"/>
          </svg>
          <div>
            <div style="font-size:22px;font-weight:600;letter-spacing:.4px;color:{theme['text']};line-height:1.15;">
              {APP_TITLE}
            </div>
            <div style="font-size:11px;letter-spacing:1px;color:{theme['text_muted']};
                        margin-top:4px;text-transform:uppercase;font-weight:500;">
              Evidence and Interrogation Layer {APP_VERSION}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_support_bar_html(level: str, text_color: str, border_color: str) -> str:
    cfg = SUPPORT_LEVELS.get(
        level.lower(),
        {"pct": 0, "color": "#94a3b8", "label": level.title()},
    )
    return f"""
    <div style="margin:14px 0 6px 0;">
      <div style="display:flex;justify-content:space-between;margin-bottom:7px;
                  font-size:11px;font-weight:700;color:{text_color};
                  letter-spacing:.6px;text-transform:uppercase;opacity:.75;">
        <span>Evidence Support Level</span>
        <span style="color:{cfg['color']};opacity:1;">{cfg['label']}</span>
      </div>
      <div style="width:100%;height:5px;background:{border_color};
                  border-radius:999px;overflow:hidden;">
        <div style="width:{cfg['pct']}%;height:100%;background:{cfg['color']};
                    border-radius:999px;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:5px;
                  font-size:10px;color:{text_color};opacity:.45;">
        <span>None</span><span>Limited</span><span>Indirect</span>
        <span>Moderate</span><span>Direct</span>
      </div>
    </div>
    """


def render_copy_button(text: str, icon_color: str, border_color: str) -> None:
    escaped = (
        text.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("\n", "\\n")
        .replace("\r", "")
    )
    components.html(
        f"""
        <button onclick="navigator.clipboard.writeText(`{escaped}`).then(() => {{
            this.innerText = 'Copied';
            this.style.borderColor = '#10b981';
            this.style.color = '#10b981';
            setTimeout(() => {{
                this.innerText = 'Copy to Clipboard';
                this.style.borderColor = '{border_color}';
                this.style.color = '{icon_color}';
            }}, 1800);
        }})"
        style="background:transparent;border:1px solid {border_color};color:{icon_color};
               border-radius:6px;padding:5px 14px;font-size:12px;
               font-family:Inter,-apple-system,sans-serif;cursor:pointer;
               transition:all .2s;margin-bottom:8px;">
        Copy to Clipboard
        </button>
        """,
        height=42,
    )


def add_history_entry(claim: str, lens: str, support_level: str) -> None:
    short_claim = claim[:60] + "..." if len(claim) > 60 else claim
    entry: HistoryEntry = {
        "time": datetime.now().strftime("%H:%M"),
        "claim": short_claim,
        "lens": lens,
        "support": support_level,
    }
    exists = any(
        h["claim"] == entry["claim"] and h["lens"] == entry["lens"]
        for h in cast(List[HistoryEntry], st.session_state["history"])
    )
    if not exists:
        st.session_state["history"].insert(0, entry)
        st.session_state["history"] = st.session_state["history"][:5]


def render_sidebar(api_health: str) -> None:
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
            help="Enable side-by-side evaluation of two design claims using identical configuration.",
        )
        if compare_toggle != st.session_state.compare_mode:
            st.session_state.compare_mode = compare_toggle
            st.rerun()

        st.divider()
        st.markdown("## Recent Scans")

        history = cast(List[HistoryEntry], st.session_state["history"])
        if history:
            for h in history:
                lc = SUPPORT_LEVELS.get(h["support"].lower(), {"color": "#94a3b8"})
                bg = "#1e293b" if st.session_state.dark_mode else "#f1f5f9"
                br = "#334155" if st.session_state.dark_mode else "#cbd5e1"
                tc = "#f1f5f9" if st.session_state.dark_mode else "#0f172a"
                tc2 = "#94a3b8" if st.session_state.dark_mode else "#475569"

                st.markdown(
                    f"""
                    <div style="padding:8px 10px;margin-bottom:6px;border-radius:7px;
                                border:1px solid {br};background:{bg};">
                      <div style="font-size:11px;font-weight:600;color:{tc2};">
                        {h['time']} · {h['lens'].title()}
                      </div>
                      <div style="font-size:12px;margin-top:2px;color:{tc};">
                        {h['claim']}
                      </div>
                      <div style="margin-top:4px;">
                        <span style="font-size:11px;padding:2px 8px;border-radius:999px;
                                     color:{lc['color']};border:1px solid {lc['color']};">
                          {h['support'].title()}
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
            "literature, detects translation risk patterns, and generates structured prompts."
        )
        st.caption(api_health)


def pdf_safe(text: Any) -> str:
    if text is None:
        return ""

    replacements = {
        "\u2014": "-",
        "\u2013": "-",
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u2022": "-",
        "\u2026": "...",
        "\u00a0": " ",
    }
    s = str(text)
    for bad, good in replacements.items():
        s = s.replace(bad, good)
    return s.encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf_report(
    claim: str,
    lens: str,
    preset: str,
    snap: Optional[Dict[str, Any]],
    prompts: Optional[Dict[str, Any]],
    matrix: Optional[Dict[str, Any]],
) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, pdf_safe("EcoSentia - Evidence Report"), ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(
        0,
        6,
        pdf_safe(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
            f"Lens: {lens.title()} | Preset: {preset.upper()}"
        ),
        ln=True,
    )
    pdf.set_text_color(15, 23, 42)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, pdf_safe("Design Claim"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, pdf_safe(claim))
    pdf.ln(4)

    if snap:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, pdf_safe("Evidence Scan Snapshot"), ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, pdf_safe(f"Total Records: {snap.get('combined_count', '—')}"), ln=True)
        pdf.cell(0, 6, pdf_safe(f"Direct Matches: {snap.get('direct_hits', '—')}"), ln=True)
        pdf.cell(0, 6, pdf_safe(f"Support Level: {str(snap.get('support_level', '—')).title()}"), ln=True)
        pdf.multi_cell(0, 6, pdf_safe(f"Summary: {snap.get('summary', '')}"))
        pdf.ln(4)

    if prompts:
        for title, key in [
            ("Master Prompt", "master_prompt"),
            ("Counter Prompt", "counter_prompt"),
            ("Uncertainty Mapping", "uncertainty_prompt"),
            ("Redesign Prompt", "redesign_prompt"),
        ]:
            value = prompts.get(key, "")
            if value:
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, pdf_safe(title), ln=True)
                pdf.set_font("Courier", "", 8)
                pdf.multi_cell(0, 5, pdf_safe(value))
                pdf.ln(3)

    if matrix:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, pdf_safe("Multi-Lens Audit Matrix"), ln=True)
        pdf.set_font("Helvetica", "", 10)

        for lens_name, result in matrix.items():
            result_dict = ensure_dict(result)
            if "error" in result_dict:
                line = f"{lens_name.title()}: Error - {result_dict['error']}"
            else:
                biases = coerce_bias_list(result_dict.get("detected_biases"))
                risk_str = ", ".join(
                    b.get("bias", "") if isinstance(b, dict) else str(b)
                    for b in biases
                ) if biases else "None"
                line = (
                    f"{lens_name.title()}: "
                    f"{str(result_dict.get('support_level', 'none')).title()} | "
                    f"Risks: {risk_str}"
                )
            pdf.multi_cell(0, 6, pdf_safe(line))

    try:
        raw = pdf.output()
    except TypeError:
        raw = pdf.output(dest="S")

    return bytes(raw) if not isinstance(raw, bytes) else raw


def build_base_payload(
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
) -> Dict[str, Any]:
    return {
        "session_id": f"streamlit-{pid}",
        "preset": domain_mode.lower(),
        "domain_mode": domain_mode,
        "project": "",
        "claim": claim_text,
        "lens": lens_ui.lower(),
        "source": source,
        "max_results": max_results,
        "biological_model": bio_model,
        "target_function": trg_func,
        "application_context": app_ctx,
        "mechanism_keywords": mech_kw,
        "exclude_terms": excl_kw,
    }


def build_matrix_dataframe(matrix: Dict[str, Any]) -> pd.DataFrame:
    rows: List[Dict[str, str]] = []

    for lens_name, result in matrix.items():
        result_dict = ensure_dict(result)
        if "error" in result_dict:
            rows.append({
                "Lens": lens_name.capitalize(),
                "Support": "Error",
                "Risks": str(result_dict["error"]),
                "_level": "error",
            })
        else:
            biases = coerce_bias_list(result_dict.get("detected_biases"))
            risk_str = ", ".join(
                b.get("bias", "") if isinstance(b, dict) else str(b)
                for b in biases
            ) if biases else "None"
            rows.append({
                "Lens": lens_name.capitalize(),
                "Support": str(result_dict.get("support_level", "none")).capitalize(),
                "Risks": risk_str,
                "_level": str(result_dict.get("support_level", "none")).lower(),
            })

    return pd.DataFrame(rows)


def render_matrix_table(df: pd.DataFrame, theme: ThemeDict) -> None:
    rows_html = ""
    for _, row in df.iterrows():
        rows_html += f"""
        <tr>
          <td style="font-weight:600;color:{theme['text']};">{row['Lens']}</td>
          <td><span class="badge badge-{row['_level']}">{row['Support']}</span></td>
          <td style="color:{theme['text_muted']};font-size:13px;">{row['Risks']}</td>
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


def invalidate_panel_state(pid: str, claim_text: str) -> Dict[str, str]:
    keys = {
        "refined_query": f"refined_query_{pid}",
        "active_query": f"active_query_{pid}",
        "scan": f"scan_{pid}",
        "prompts": f"prompts_{pid}",
        "matrix": f"lens_matrix_{pid}",
        "claim_cache": f"claim_cache_{pid}",
        "pdf_cache": f"pdf_cache_{pid}",
    }

    if st.session_state.get(keys["claim_cache"]) != claim_text:
        st.session_state[keys["claim_cache"]] = claim_text
        delete_keys([
            keys["refined_query"],
            keys["active_query"],
            keys["scan"],
            keys["prompts"],
            keys["matrix"],
            keys["pdf_cache"],
        ])

    return keys


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
        ),
        unsafe_allow_html=True,
    )
    st.info(str(snapshot.get("summary", "No summary available.")))

    top_records = ensure_list(snapshot.get("top_records"))
    top_titles = ensure_list(snapshot.get("top_titles"))

    if top_records:
        with st.expander("Top Retrieved Titles"):
            for record in top_records:
                record_dict = ensure_dict(record)
                title = str(record_dict.get("title", "Untitled"))
                url = str(record_dict.get("url", ""))
                src = str(record_dict.get("source", "")).title()
                score = record_dict.get("score", "")
                meta = src + (f" · Score: {score}" if score != "" else "")

                if url:
                    st.markdown(f"- [{title}]({url})")
                else:
                    st.write(f"- {title}")

                matched_terms = ensure_list(record_dict.get("matched_terms"))
                if matched_terms:
                    st.caption(f"{meta} · Matched: {', '.join(map(str, matched_terms[:4]))}")
    elif top_titles:
        with st.expander("Top Retrieved Titles"):
            for title in top_titles:
                st.write(f"- {title}")


def render_prompt_results(prompts: Dict[str, Any], theme: ThemeDict) -> None:
    level = str(prompts.get("support_level", "none")).lower()
    evidence_note = str(prompts.get("evidence_note", ""))

    level_map = {
        "none": "error",
        "limited": "warning",
        "indirect": "warning",
        "moderate": "info",
        "direct": "success",
    }

    getattr(st, level_map.get(level, "info"))(
        f"**Support: {level.title()}**\n\n{evidence_note}"
    )

    st.markdown(
        render_support_bar_html(level, theme["text"], theme["border"]),
        unsafe_allow_html=True,
    )

    biases = coerce_bias_list(prompts.get("detected_biases"))
    if biases:
        st.markdown("#### Detected Translation Risk Patterns")
        for bias in biases:
            name = bias.get("bias", "") if isinstance(bias, dict) else str(bias)
            explanation = bias.get("explanation", "") if isinstance(bias, dict) else ""
            st.markdown(
                f"""
                <div class="risk-panel">
                    <span class="risk-title">{name}</span>
                    {explanation}
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.success("No translation risk patterns detected.")

    st.markdown("#### Evaluation Prompts")
    prompt_meta = [
        ("Master Prompt", "master_prompt", True, "Primary evaluation prompt for direct LLM use."),
        ("Counter Prompt", "counter_prompt", False, "Challenges the validity of the design claim."),
        ("Uncertainty Mapping", "uncertainty_prompt", False, "Maps unknowns and contested areas in the literature."),
        ("Redesign Prompt", "redesign_prompt", False, "Suggests evidence-grounded modifications."),
    ]

    for title, key, expanded, description in prompt_meta:
        with st.expander(title, expanded=expanded):
            st.caption(description)
            value = str(prompts.get(key, "") or "")
            if value:
                render_copy_button(value, theme["icon"], theme["border"])
                st.code(value, language="text")

    look_for = ensure_list(prompts.get("look_for"))
    if look_for:
        st.markdown("**Checklist for AI Response:**")
        for item in look_for:
            st.markdown(f"- {str(item).capitalize()}")


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
) -> None:
    keys = invalidate_panel_state(pid, claim_text)

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
    st.caption(
        "Extracts key entities from the claim and builds a Boolean query "
        "optimized for the selected literature sources."
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Refine Query", key=f"refine_btn_{pid}", use_container_width=True):
            with st.spinner("Refining..."):
                try:
                    response = api_post("/evidence/refine-query", payload_base)
                    refined_query = extract_refined_query(response, claim_text)
                    st.session_state[keys["refined_query"]] = refined_query
                    st.session_state[keys["active_query"]] = refined_query
                    st.success("Query refined.")
                except Exception as exc:
                    st.error(str(exc))

    with c2:
        if st.button("Use Claim", key=f"use_claim_btn_{pid}", use_container_width=True):
            st.session_state[keys["refined_query"]] = claim_text
            st.session_state[keys["active_query"]] = claim_text

    if keys["active_query"] not in st.session_state:
        st.session_state[keys["active_query"]] = st.session_state.get(keys["refined_query"], claim_text)

    q_text = st.text_area(
        "Active Query (Editable)",
        key=keys["active_query"],
        height=80,
        help="You can manually edit the active query before scanning.",
    )

    st.divider()

    st.markdown("### Step 2: Run Evidence Scan")
    st.caption(
        "Retrieves abstracts and scores semantic overlap with the original design claim."
    )

    if st.button("Execute Scan", key=f"scan_btn_{pid}"):
        with st.spinner("Querying scientific literature..."):
            try:
                response = api_post("/evidence/scan", {**payload_base, "query_text": q_text})
                snapshot, query_used = extract_scan_payload(response, q_text)

                scan_payload = {
                    "raw": response,
                    "snapshot": snapshot,
                    "query_text": query_used,
                }
                st.session_state[keys["scan"]] = scan_payload

                add_history_entry(
                    claim=claim_text,
                    lens=lens_ui,
                    support_level=str(snapshot.get("support_level", "none")),
                )
                delete_keys([keys["pdf_cache"]])
                st.success("Literature scan complete.")
            except Exception as exc:
                st.error(str(exc))

    if keys["scan"] in st.session_state:
        scan_state = ensure_dict(st.session_state[keys["scan"]])
        snapshot = ensure_dict(scan_state.get("snapshot"))
        render_scan_results(snapshot, theme)

    st.divider()

    st.markdown("### Step 3: Generate Evidence-Aware Prompts")
    st.caption("Builds structured LLM prompts grounded in the retrieved evidence snapshot.")

    if keys["scan"] not in st.session_state:
        st.info("Please complete Step 2 first.")
    else:
        if st.button("Generate Prompts", key=f"prompts_btn_{pid}"):
            with st.spinner("Generating evidence-aware prompts..."):
                try:
                    scan_state = ensure_dict(st.session_state[keys["scan"]])
                    payload_prompts = {
                        "preset": domain_mode.lower(),
                        "lens": lens_ui.lower(),
                        "claim": claim_text,
                        "query_text": str(scan_state.get("query_text", q_text)),
                        "snapshot": ensure_dict(scan_state.get("snapshot")),
                    }
                    response = api_post("/evidence/prompts", payload_prompts)
                    prompts = extract_prompts_payload(response)
                    st.session_state[keys["prompts"]] = prompts
                    delete_keys([keys["pdf_cache"]])
                    st.success("Prompts generated.")
                except Exception as exc:
                    st.error(str(exc))

        if keys["prompts"] in st.session_state:
            prompts = ensure_dict(st.session_state[keys["prompts"]])
            render_prompt_results(prompts, theme)

    st.divider()

    st.markdown("### Step 4: Full Multi-Lens Audit")
    st.caption(
        "Runs the evidence scan across all five analytical lenses and returns a unified risk matrix."
    )

    if st.button("Execute Full Audit", key=f"audit_btn_{pid}"):
        with st.spinner("Scanning all lenses..."):
            try:
                response = api_post("/evidence/scan-all-lenses", payload_base)
                matrix = extract_lens_matrix(response)
                st.session_state[keys["matrix"]] = matrix
                delete_keys([keys["pdf_cache"]])
                st.success("Multi-lens audit complete.")
            except Exception as exc:
                st.error(str(exc))

    if keys["matrix"] in st.session_state:
        matrix = ensure_dict(st.session_state[keys["matrix"]])
        df = build_matrix_dataframe(matrix)

        st.markdown("#### Analytical Lens Matrix")
        render_matrix_table(df, theme)

        export_df = df.drop(columns=["_level"])
        d1, d2, d3 = st.columns(3)

        with d1:
            st.download_button(
                "Download CSV",
                export_df.to_csv(index=False).encode("utf-8"),
                f"ecosentia_matrix_{pid}.csv",
                "text/csv",
                key=f"csv_btn_{pid}",
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
                        for _, row in export_df.iterrows()
                    ],
                    indent=2,
                    ensure_ascii=False,
                ).encode("utf-8"),
                f"ecosentia_matrix_{pid}.json",
                "application/json",
                key=f"json_btn_{pid}",
            )

        with d3:
            if keys["pdf_cache"] not in st.session_state:
                scan_state = ensure_dict(st.session_state.get(keys["scan"]))
                prompts = ensure_dict(st.session_state.get(keys["prompts"]))
                st.session_state[keys["pdf_cache"]] = generate_pdf_report(
                    claim=claim_text,
                    lens=lens_ui,
                    preset=domain_mode,
                    snap=ensure_dict(scan_state.get("snapshot")) if scan_state else None,
                    prompts=prompts if prompts else None,
                    matrix=matrix,
                )

            st.download_button(
                "Download PDF",
                st.session_state[keys["pdf_cache"]],
                f"ecosentia_report_{pid}.pdf",
                "application/pdf",
                key=f"pdf_btn_{pid}",
            )


def main() -> None:
    ensure_session_defaults()

    api_health = get_api_health()
    theme = get_theme(st.session_state.dark_mode)

    inject_css(theme)
    render_sidebar(api_health)
    render_header(theme)

    st.markdown("### Configuration")

    c1, c2 = st.columns(2)
    with c1:
        domain_mode = st.radio("Preset", ["Fog", "EV", "Custom"], horizontal=True)
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

    bio_model = ""
    trg_func = ""
    app_ctx = ""
    mech_kw = ""
    excl_kw = ""

    if domain_mode == "Custom":
        with st.expander("Custom Guidance (Optional but Recommended)", expanded=True):
            x1, x2 = st.columns(2)
            with x1:
                bio_model = st.text_input("Biological Model", placeholder="e.g., Gecko, Mussel")
                app_ctx = st.text_input("Application Context", placeholder="e.g., Wet biomedical surfaces")
            with x2:
                trg_func = st.text_input("Target Function", placeholder="e.g., Reversible adhesion")
                mech_kw = st.text_input("Mechanism Keywords", placeholder="e.g., microstructure, van der Waals")
            excl_kw = st.text_input("Exclude Terms", placeholder="e.g., vaccine, remote sensing")

    if not st.session_state.compare_mode:
        claim_main = st.text_area(
            "Design Claim",
            value=DEFAULT_CLAIMS.get(domain_mode, ""),
            height=90,
            help="Paste or type the biomimetic design claim to evaluate.",
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

        with left:
            st.markdown("### Panel A")
            claim_a = st.text_area(
                "Design Claim A",
                value="A painless transdermal patch inspired by mosquito proboscis geometry.",
                height=90,
                key="claim_a",
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
            )

        with right:
            st.markdown("### Panel B")
            claim_b = st.text_area(
                "Design Claim B",
                value="A painless transdermal patch inspired by porcupine quill microstructure.",
                height=90,
                key="claim_b",
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
            )


if __name__ == "__main__":
    main()