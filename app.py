from __future__ import annotations

import json
import os
from datetime import datetime
from html import escape
from typing import Any, Dict, List, Tuple, TypedDict, cast

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="EcoSentia Checkpoint", layout="wide", page_icon="■")

API_BASE = os.getenv("ECOSENTIA_API_URL", "https://ecosentia.onrender.com")
APP_TITLE = "EcoSentia Checkpoint"
APP_VERSION = "v0.5.4"
HTTP_TIMEOUT = int(os.getenv("ECOSENTIA_HTTP_TIMEOUT", "120"))
HEALTH_TIMEOUT = int(os.getenv("ECOSENTIA_HEALTH_TIMEOUT", "10"))


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
    focus_ring: str
    input_bg: str
    accent: str
    accent_soft: str
    accent_bg: str


class HistoryEntry(TypedDict):
    time: str
    claim: str
    lens: str
    support: str


SUPPORT_LEVELS: Dict[str, SupportLevelConfig] = {
    "none": {"pct": 5, "color": "#e59aa5", "label": "None"},
    "limited": {"pct": 30, "color": "#ebb184", "label": "Limited"},
    "indirect": {"pct": 50, "color": "#e3a377", "label": "Indirect"},
    "moderate": {"pct": 70, "color": "#c2c9d4", "label": "Moderate"},
    "direct": {"pct": 100, "color": "#d9dde5", "label": "Direct"},
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
    "Custom": "",  
}

DEFAULT_COMPARE_CLAIMS: Dict[str, Tuple[str, str]] = {
    "Fog": (
        "A surface structure inspired by the Namib desert beetle for passive fog harvesting and water collection.",
        "A cactus-spine-inspired surface for directional fog capture and passive water transport.",
    ),
    "EV": (
        "An extracellular vesicle-inspired nanoparticle for targeted drug delivery in inflammatory disease.",
        "An extracellular-vesicle-inspired drug delivery system with low immunogenicity and natural tissue tropism.",
    ),
    "Custom": ("", ""), 
}

def get_http_session() -> requests.Session:
    if "_http_session" not in st.session_state:
        st.session_state["_http_session"] = requests.Session()
    return cast(requests.Session, st.session_state["_http_session"])


def ensure_session_defaults() -> None:
    defaults: Dict[str, Any] = {
        "dark_mode": True,
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
        if not isinstance(current, dict) or key not in current:
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


def html_safe(value: Any) -> str:
    return escape("" if value is None else str(value))


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
        response = session.get(f"{API_BASE}/health", timeout=HEALTH_TIMEOUT)
        response.raise_for_status()
        health = response.json()
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
    query_text = first_non_empty(
        response.get("query_text"),
        response.get("query"),
        safe_get(response, "data", "query_text"),
        safe_get(response, "results", "query_text"),
        fallback_query,
    )
    return ensure_dict(snapshot), str(query_text)


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
            "bg": "#0b0c10",
            "panel": "#15171d",
            "text": "#f4f4f5",
            "border": "#2b2f38",
            "hover": "#1a1d24",
            "icon": "#f4f4f5",
            "text_muted": "#a7afb9",
            "shadow": "rgba(0,0,0,0.34)",
            "focus_ring": "rgba(231,163,143,0.22)",
            "input_bg": "#11141a",
            "accent": "#e7a38f",
            "accent_soft": "#e7a0ab",
            "accent_bg": "rgba(231,163,143,0.12)",
        }

    return {
        "bg": "#f7f7f8",
        "panel": "#ffffff",
        "text": "#17191d",
        "border": "#e5e7eb",
        "hover": "#f3f4f6",
        "icon": "#17191d",
        "text_muted": "#6e7683",
        "shadow": "rgba(23,25,29,0.06)",
        "focus_ring": "rgba(216,141,122,0.18)",
        "input_bg": "#ffffff",
        "accent": "#d88d7a",
        "accent_soft": "#cf8695",
        "accent_bg": "rgba(216,141,122,0.10)",
    }


def inject_css(theme: ThemeDict) -> None:
    st.markdown(
        f"""
<style>
:root {{
  --text-color: {theme['text']} !important;
  --background-color: {theme['bg']} !important;
  --secondary-background-color: {theme['panel']} !important;
  --primary-color: {theme['accent']} !important;
}}

html, body, #root, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="stMainBlockContainer"] {{
  background: {theme['bg']} !important;
  color: {theme['text']} !important;
  font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif !important;
}}

.stMarkdown p, .stMarkdown span, .stMarkdown li, .stMarkdown h1,
.stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5,
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] span, label {{
  color: {theme['text']} !important;
}}

[data-testid="stCaptionContainer"] p, .stCaption p, small {{
  color: {theme['text_muted']} !important;
}}

hr {{
  border-top: 1px solid {theme['border']} !important;
  opacity: 1 !important;
}}

[data-testid="stSidebar"], [data-testid="stSidebar"] > div {{
  background: {theme['panel']} !important;
  border-right: 1px solid {theme['border']} !important;
}}

[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] button,
[data-testid="stSidebarCollapseButton"] button,
button[data-testid="baseButton-headerNoPadding"],
button[kind="headerNoPadding"] {{
  background: {theme['panel']} !important;
  border: 1px solid {theme['border']} !important;
  border-radius: 8px !important;
  box-shadow: 0 2px 8px {theme['shadow']} !important;
  opacity: 1 !important;
  visibility: visible !important;
}}

[data-testid="collapsedControl"] svg,
[data-testid="stSidebarCollapseButton"] svg,
button[data-testid="baseButton-headerNoPadding"] svg,
button[kind="headerNoPadding"] svg {{
  fill: {theme['icon']} !important;
  stroke: {theme['icon']} !important;
  color: {theme['icon']} !important;
}}

input[type="text"], input[type="number"], input[type="search"], textarea,
div[data-baseweb="select"] > div {{
  background: {theme['input_bg']} !important;
  color: {theme['text']} !important;
  border: 1px solid {theme['border']} !important;
  border-radius: 10px !important;
  transition: all .16s ease !important;
}}

input::placeholder, textarea::placeholder {{
  color: {theme['text_muted']} !important;
  opacity: .78 !important;
}}

input:hover, textarea:hover, input:focus, textarea:focus,
input:focus-visible, textarea:focus-visible,
div[data-baseweb="select"] > div:hover,
div[data-baseweb="select"] > div:focus-within {{
  border-color: {theme['accent']} !important;
  box-shadow: 0 0 0 3px {theme['focus_ring']} !important;
  outline: none !important;
}}

div[data-baseweb="select"] svg {{
  fill: {theme['icon']} !important;
  color: {theme['icon']} !important;
}}

div[data-baseweb="popover"] {{
  background: {theme['panel']} !important;
  border: 1px solid {theme['accent']} !important;
  border-radius: 10px !important;
  box-shadow: 0 12px 28px {theme['shadow']} !important;
}}

div[data-baseweb="popover"] ul,
div[data-baseweb="popover"] [role="listbox"],
div[data-baseweb="popover"] li,
li[role="option"] {{
  background: {theme['panel']} !important;
  color: {theme['text']} !important;
}}

div[data-baseweb="select"] > div,
div[data-baseweb="select"] > div > div,
div[data-baseweb="select"] span,
div[data-baseweb="select"] div[value] {{
  color: {theme['text']} !important;
}}

div[data-baseweb="popover"] li,
div[data-baseweb="popover"] li *,
li[role="option"],
li[role="option"] * {{
  color: {theme['text']} !important;
  background: {theme['panel']} !important;
}}

/* hover و selected */
li[role="option"]:hover,
li[role="option"]:hover *,
li[aria-selected="true"],
li[aria-selected="true"] * {{
  background: {theme['hover']} !important;
  color: {theme['text']} !important;
}}

/* radio و horizontal options (Preset / Source) */
div[role="radiogroup"] label,
div[role="radiogroup"] label *,
div[data-baseweb="radio"] *,
[data-testid="stRadio"] label,
[data-testid="stRadio"] label * {{
  color: {theme['text']} !important;
}}

/* slider label و مقادیر */
[data-testid="stSlider"] label,
[data-testid="stSlider"] * {{
  color: {theme['text']} !important;
}}
li[role="option"]:hover,
li[aria-selected="true"] {{
  background: {theme['hover']} !important;
}}

[data-testid="stExpander"] {{
  background: {theme['panel']} !important;
  border: 1px solid {theme['border']} !important;
  border-radius: 12px !important;
  box-shadow: 0 2px 8px {theme['shadow']} !important;
  overflow: hidden !important;
  margin-bottom: 12px !important;
  transition: all .18s ease !important;
}}

[data-testid="stExpander"]:hover {{
  border-color: {theme['accent']} !important;
}}

[data-testid="stExpander"] summary {{
  background: {theme['panel']} !important;
  padding: 14px 16px !important;
}}

[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary div {{
  color: {theme['text']} !important;
  font-weight: 600 !important;
}}

[data-testid="stExpander"] > div > div {{
  background: {theme['bg']} !important;
  padding: 16px !important;
}}

[data-testid="metric-container"] {{
  background: {theme['panel']} !important;
  border: 1px solid {theme['accent']} !important;
  border-radius: 12px !important;
  box-shadow: 0 2px 8px {theme['shadow']} !important;
  transition: all .18s ease !important;
}}

[data-testid="metric-container"]:hover {{
  border-color: {theme['accent']} !important;
  box-shadow: 0 0 0 2px {theme['accent_bg']} !important;
}}

[data-testid="stMetricValue"] > div {{
  color: {theme['text']} !important;
  font-weight: 700 !important;
}}

[data-testid="stMetricLabel"] > div {{
  color: {theme['text_muted']} !important;
}}

.stButton > button,
[data-testid="stDownloadButton"] > button {{
  background: {theme['accent_bg']} !important;
  color: {theme['accent']} !important;
  border: 1px solid {theme['accent']} !important;
  border-radius: 10px !important;
  box-shadow: 0 2px 8px {theme['shadow']} !important;
  transition: all .18s ease !important;
  font-weight: 600 !important;
}}

.stButton > button:hover,
[data-testid="stDownloadButton"] > button:hover,
.stButton > button:focus,
[data-testid="stDownloadButton"] > button:focus,
.stButton > button:focus-visible,
[data-testid="stDownloadButton"] > button:focus-visible {{
  background: {theme['accent']} !important;
  color: #ffffff !important;
  border-color: {theme['accent']} !important;
  box-shadow: 0 0 0 3px {theme['focus_ring']} !important;
  outline: none !important;
}}

.stCodeBlock {{
  background: {theme['bg']} !important;
  border: 1px solid {theme['accent']} !important;
  border-radius: 10px !important;
}}

.stCodeBlock pre, .stCodeBlock code, .stCodeBlock span {{
  color: {theme['text']} !important;
}}

.note-box {{
  background: {theme['panel']};
  border: 1px solid {theme['border']};
  border-left: 3px solid {theme['accent']};
  border-radius: 12px;
  padding: 12px 14px;
  margin: 8px 0 16px 0;
}}

.note-title {{
  color: {theme['accent']};
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .45px;
  text-transform: uppercase;
  margin-bottom: 6px;
}}

.note-body {{
  color: {theme['text_muted']};
  line-height: 1.65;
  font-size: 13px;
}}

.risk-panel {{
  background: {theme['panel']} !important;
  border: 1px solid {theme['accent']} !important;
  border-left: 3px solid {theme['accent_soft']} !important;
  border-radius: 10px !important;
  padding: 12px 14px !important;
  margin-bottom: 10px !important;
  line-height: 1.65 !important;
}}

.risk-title {{
  color: {theme['accent']} !important;
  font-weight: 700 !important;
  margin-bottom: 5px !important;
  display: block !important;
  font-size: 12px !important;
  text-transform: uppercase !important;
  letter-spacing: .45px !important;
}}

.matrix-table {{
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  border: 1px solid {theme['accent']}33;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px {theme['shadow']};
}}

.matrix-table thead tr {{
  background: {theme['hover']};
}}

.matrix-table thead th {{
  padding: 11px 16px;
  text-align: left;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .6px;
  color: {theme['text_muted']} !important;
}}

.matrix-table tbody td {{
  padding: 12px 16px;
  color: {theme['text']} !important;
  background: {theme['panel']};
  border-top: 1px solid {theme['border']};
}}

.badge {{
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .35px;
  text-transform: uppercase;
  background: {theme['accent_bg']} !important;
  color: {theme['accent']} !important;
  border: 1px solid {theme['accent']} !important;
}}

.checklist-box {{
  background: {theme['panel']};
  border: 1px solid {theme['accent']};
  border-radius: 12px;
  padding: 14px 16px;
  margin-top: 10px;
  margin-bottom: 14px;
}}

.checklist-title {{
  color: {theme['accent']};
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .5px;
  margin-bottom: 10px;
}}

.checklist-box ul {{
  margin: 0;
  padding-left: 18px;
}}

.checklist-box li {{
  margin: 0 0 8px 0;
  color: {theme['text']};
  line-height: 1.6;
}}

::-webkit-scrollbar {{
  width: 7px;
}}

::-webkit-scrollbar-track {{
  background: {theme['bg']};
}}

::-webkit-scrollbar-thumb {{
  background: {theme['border']};
  border-radius: 999px;
}}
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
            <line x1="50" y1="35" x2="50" y2="85"
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


def render_note_box(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="note-box">
          <div class="note-title">{html_safe(title)}</div>
          <div class="note-body">{html_safe(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_support_bar_html(level: str, text_color: str, border_color: str, accent_color: str) -> str:
    cfg = SUPPORT_LEVELS.get(level.lower(), {"pct": 0, "color": accent_color, "label": level.title()})
    return f"""
    <div style="margin:14px 0 10px 0;">
      <div style="display:flex;justify-content:space-between;margin-bottom:7px;
                  font-size:11px;font-weight:700;color:{accent_color};
                  letter-spacing:.6px;text-transform:uppercase;opacity:.95;">
        <span>Evidence Support Level</span>
        <span style="color:{accent_color};">{html_safe(cfg['label'])}</span>
      </div>
      <div style="width:100%;height:5px;background:{border_color};
                  border-radius:999px;overflow:hidden;">
        <div style="width:{cfg['pct']}%;height:100%;background:{accent_color};
                    border-radius:999px;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:5px;
                  font-size:10px;color:{text_color};opacity:.45;">
        <span>None</span><span>Limited</span><span>Indirect</span><span>Moderate</span><span>Direct</span>
      </div>
    </div>
    """


def _js_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace("</", "<\\/")
        .replace('"', '\\"')
    )


def render_copy_button(text: str, icon_color: str, border_color: str, accent_color: str) -> None:
    escaped = _js_escape(text)
    components.html(
        f"""
        <button
          onclick="navigator.clipboard.writeText(`{escaped}`).then(() => {{
            this.innerText = 'Copied';
            this.style.borderColor = '{accent_color}';
            this.style.color = '{accent_color}';
            setTimeout(() => {{
              this.innerText = 'Copy to Clipboard';
              this.style.borderColor = '{border_color}';
              this.style.color = '{icon_color}';
            }}, 1600);
          }})"
          style="
            background:transparent;
            border:1px solid {border_color};
            color:{icon_color};
            border-radius:8px;
            padding:6px 14px;
            font-size:12px;
            font-family:Inter,-apple-system,sans-serif;
            cursor:pointer;
            transition:all .2s;
            margin-bottom:8px;
          "
        >
          Copy to Clipboard
        </button>
        """,
        height=44,
    )


def add_history_entry(claim: str, lens: str, support_level: str) -> None:
    short_claim = claim[:64] + "..." if len(claim) > 64 else claim
    entry: HistoryEntry = {
        "time": datetime.now().strftime("%H:%M"),
        "claim": short_claim,
        "lens": lens,
        "support": support_level,
    }
    history = cast(List[HistoryEntry], st.session_state["history"])
    exists = any(h["claim"] == entry["claim"] and h["lens"] == entry["lens"] for h in history)
    if not exists:
        history.insert(0, entry)
        st.session_state["history"] = history[:5]


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
        "source": source.lower(),
        "max_results": max_results,
        "biological_model": bio_model,
        "target_function": trg_func,
        "application_context": app_ctx,
        "mechanism_keywords": mech_kw,
        "exclude_terms": excl_kw,
    }


def build_matrix_dataframe(matrix: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    rows: List[Dict[str, str]] = []
    levels: List[str] = []

    for lens_name, result in matrix.items():
        result_dict = ensure_dict(result)
        if result_dict.get("error"):
            rows.append(
                {
                    "Lens": lens_name.capitalize(),
                    "Support": "Error",
                    "Risks": str(result_dict["error"]),
                }
            )
            levels.append("error")
        else:
            biases = coerce_bias_list(result_dict.get("detected_biases"))
            risk_str = (
                ", ".join(
                    b.get("bias", "") if isinstance(b, dict) else str(b)
                    for b in biases
                )
                if biases
                else "None"
            )
            rows.append(
                {
                    "Lens": lens_name.capitalize(),
                    "Support": str(result_dict.get("support_level", "none")).capitalize(),
                    "Risks": risk_str,
                }
            )
            levels.append(str(result_dict.get("support_level", "none")).lower())

    return pd.DataFrame(rows), levels


def render_matrix_table(df: pd.DataFrame, theme: ThemeDict) -> None:
    rows_html = ""
    for _, row in df.iterrows():
        rows_html += f"""
        <tr>
          <td style="font-weight:600;color:{theme['text']};">{html_safe(row['Lens'])}</td>
          <td><span class="badge">{html_safe(row['Support'])}</span></td>
          <td style="color:{theme['text_muted']};font-size:13px;">{html_safe(row['Risks'])}</td>
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
def get_panel_state(pid: str) -> Dict[str, Any]:
    """
    Collect all available outputs for a given panel into a structured report object.
    This export is intended for reproducibility and case documentation.
    """
    keys = {
        "refined_query": f"refined_query_{pid}",
        "active_query": f"active_query_{pid}",
        "scan": f"scan_{pid}",
        "prompts": f"prompts_{pid}",
        "matrix": f"lens_matrix_{pid}",
        "claim_cache": f"claim_cache_{pid}",
    }

    scan_state = ensure_dict(st.session_state.get(keys["scan"], {}))
    prompts = ensure_dict(st.session_state.get(keys["prompts"], {}))
    matrix = ensure_dict(st.session_state.get(keys["matrix"], {}))

    return {
        "app": APP_TITLE,
        "version": APP_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "panel_id": pid,
        "claim": st.session_state.get(keys["claim_cache"], ""),
        "active_query": st.session_state.get(keys["active_query"], ""),
        "refined_query": st.session_state.get(keys["refined_query"], ""),
        "scan": scan_state,
        "prompts": prompts,
        "lens_matrix": matrix,
    }


def build_report_html(report: Dict[str, Any]) -> str:
    """
    Build a standalone HTML report from the current panel state.
    The report can be opened in a browser and printed/saved as PDF.
    """
    scan = ensure_dict(report.get("scan"))
    snapshot = ensure_dict(scan.get("snapshot"))
    prompts = ensure_dict(report.get("prompts"))
    matrix = ensure_dict(report.get("lens_matrix"))

    top_records = ensure_list(snapshot.get("top_records"))
    biases = coerce_bias_list(prompts.get("detected_biases"))

    top_records_html = ""
    for record in top_records:
        record_dict = ensure_dict(record)
        title = html_safe(record_dict.get("title", "Untitled"))
        url = html_safe(record_dict.get("url", ""))
        source = html_safe(record_dict.get("source", ""))
        score = html_safe(record_dict.get("score", ""))

        if url:
            top_records_html += (
                f'<li><a href="{url}" target="_blank">{title}</a>'
                f'<br><small>{source} · Score: {score}</small></li>'
            )
        else:
            top_records_html += (
                f"<li>{title}<br><small>{source} · Score: {score}</small></li>"
            )

    biases_html = ""
    if biases:
        for bias in biases:
            if isinstance(bias, dict):
                name = html_safe(bias.get("bias", ""))
                explanation = html_safe(bias.get("explanation", ""))
            else:
                name = html_safe(str(bias))
                explanation = ""

            biases_html += f"""
            <div class="risk">
                <strong>{name}</strong>
                <p>{explanation}</p>
            </div>
            """
    else:
        biases_html = "<p>No translation risk patterns detected.</p>"

    prompt_sections = ""
    for label, key in [
        ("Master Prompt", "master_prompt"),
        ("Counter Prompt", "counter_prompt"),
        ("Uncertainty Mapping", "uncertainty_prompt"),
        ("Redesign Prompt", "redesign_prompt"),
    ]:
        value = html_safe(prompts.get(key, ""))
        if value:
            prompt_sections += f"""
            <h3>{label}</h3>
            <pre>{value}</pre>
            """

    look_for_items = ensure_list(prompts.get("look_for"))
    look_for_html = ""
    if look_for_items:
        items = "".join(f"<li>{html_safe(item)}</li>" for item in look_for_items)
        look_for_html = f"""
        <h2>Checklist for AI Response</h2>
        <ul>{items}</ul>
        """

    matrix_rows = ""
    for lens_name, result in matrix.items():
        result_dict = ensure_dict(result)
        support = html_safe(result_dict.get("support_level", "none"))
        risk_list = coerce_bias_list(result_dict.get("detected_biases"))
        risk_text = (
            ", ".join(
                b.get("bias", "") if isinstance(b, dict) else str(b)
                for b in risk_list
            )
            if risk_list
            else "None"
        )

        query_used = html_safe(result_dict.get("query_used", ""))

        matrix_rows += f"""
        <tr>
            <td>{html_safe(lens_name.capitalize())}</td>
            <td>{support}</td>
            <td>{html_safe(risk_text)}</td>
            <td>{query_used}</td>
        </tr>
        """

    report_json = html_safe(json.dumps(report, indent=2, ensure_ascii=False))

    html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{html_safe(APP_TITLE)} Report - {html_safe(report.get("panel_id", ""))}</title>
<style>
body {{
    font-family: Inter, Arial, sans-serif;
    margin: 40px;
    color: #17191d;
    line-height: 1.6;
}}
h1, h2, h3 {{
    color: #17191d;
}}
a {{
    color: #b86f5d;
}}
.meta {{
    color: #6e7683;
    font-size: 13px;
    margin-bottom: 24px;
}}
.box {{
    border: 1px solid #e5e7eb;
    border-left: 4px solid #d88d7a;
    border-radius: 10px;
    padding: 14px 16px;
    margin: 14px 0;
    background: #fafafa;
}}
pre {{
    white-space: pre-wrap;
    word-break: break-word;
    background: #f7f7f8;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 12px;
    font-size: 13px;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
}}
th, td {{
    border: 1px solid #e5e7eb;
    padding: 10px;
    text-align: left;
    vertical-align: top;
}}
th {{
    background: #f3f4f6;
}}
.risk {{
    border: 1px solid #e5e7eb;
    border-left: 4px solid #cf8695;
    padding: 10px 12px;
    border-radius: 8px;
    margin: 8px 0;
}}
.print-button {{
    padding: 8px 14px;
    border: 1px solid #d88d7a;
    background: #fff;
    color: #d88d7a;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
}}
@media print {{
    body {{
        margin: 20mm;
    }}
    .no-print {{
        display: none;
    }}
}}
</style>
</head>
<body>

<button class="print-button no-print" onclick="window.print()">Print / Save as PDF</button>

<h1>{html_safe(APP_TITLE)} Report</h1>

<div class="meta">
    App: {html_safe(report.get("app"))} ·
    Version: {html_safe(report.get("version"))} ·
    Exported at: {html_safe(report.get("exported_at"))} ·
    Panel: {html_safe(report.get("panel_id"))}
</div>

<h2>Design Claim</h2>
<div class="box">{html_safe(report.get("claim"))}</div>

<h2>Active Query</h2>
<div class="box">{html_safe(report.get("active_query"))}</div>

<h2>Refined Query</h2>
<div class="box">{html_safe(report.get("refined_query"))}</div>

<h2>Evidence Snapshot</h2>
<table>
<tr><th>Total Records</th><td>{html_safe(snapshot.get("combined_count", 0))}</td></tr>
<tr><th>Direct Matches</th><td>{html_safe(snapshot.get("direct_hits", 0))}</td></tr>
<tr><th>Support Level</th><td>{html_safe(snapshot.get("support_level", "none"))}</td></tr>
<tr><th>Summary</th><td>{html_safe(snapshot.get("summary", "No summary available."))}</td></tr>
</table>

<h2>Top Retrieved Records</h2>
<ol>{top_records_html if top_records_html else "<li>No records available.</li>"}</ol>

<h2>Detected Translation Risk Patterns</h2>
{biases_html}

<h2>Generated Prompts</h2>
{prompt_sections if prompt_sections else "<p>No prompts generated.</p>"}

{look_for_html}

<h2>Multi-Lens Audit Matrix</h2>
<table>
<thead>
<tr>
    <th>Lens</th>
    <th>Support</th>
    <th>Risk Patterns</th>
    <th>Query Used</th>
</tr>
</thead>
<tbody>
{matrix_rows if matrix_rows else '<tr><td colspan="4">No multi-lens audit available.</td></tr>'}
</tbody>
</table>

<h2>Raw JSON Snapshot</h2>
<pre>{report_json}</pre>

</body>
</html>
"""
    return html


def render_print_button() -> None:
    """
    Trigger browser print when possible.
    In hosted environments, users can alternatively open the HTML report and print it.
    """
    components.html(
        """
        <button onclick="try { window.parent.print(); } catch(e) { window.print(); }"
            style="
                width:100%;
                padding:10px 14px;
                border-radius:10px;
                border:1px solid #d88d7a;
                background:rgba(216,141,122,0.10);
                color:#d88d7a;
                font-weight:600;
                cursor:pointer;
                font-family:Inter,Arial,sans-serif;
            ">
            Print / Save Page as PDF
        </button>
        """,
        height=52,
    )


def render_report_exports(pid: str) -> None:
    """
    Render complete report export controls for the current panel.
    """
    report = get_panel_state(pid)
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

def invalidate_panel_state(pid: str, claim_text: str) -> Dict[str, str]:
    keys = {
        "refined_query": f"refined_query_{pid}",
        "active_query": f"active_query_{pid}",
        "scan": f"scan_{pid}",
        "prompts": f"prompts_{pid}",
        "matrix": f"lens_matrix_{pid}",
        "claim_cache": f"claim_cache_{pid}",
    }

    if st.session_state.get(keys["claim_cache"]) != claim_text:
        st.session_state[keys["claim_cache"]] = claim_text
        delete_keys(
            [
                keys["refined_query"],
                keys["active_query"],
                keys["scan"],
                keys["prompts"],
                keys["matrix"],
            ]
        )
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
            theme["accent"],
        ),
        unsafe_allow_html=True,
    )

    render_note_box(
        "Evidence Snapshot",
        str(snapshot.get("summary", "No summary available.")),
    )

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
                    st.markdown(f"- [{html_safe(title)}]({url})")
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

    render_note_box(f"Support: {level.title()}", evidence_note)

    st.markdown(
        render_support_bar_html(level, theme["text"], theme["border"], theme["accent"]),
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
                    <span class="risk-title">{html_safe(name)}</span>
                    {html_safe(explanation)}
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        render_note_box("Risk Review", "No translation risk patterns detected.")

    st.markdown("#### Evaluation Prompts")

    prompt_meta = [
        ("Master Prompt", "master_prompt", True, "Primary evaluation prompt for direct LLM use."),
        ("Counter Prompt", "counter_prompt", False, "Challenges the validity of the design claim."),
        ("Uncertainty Mapping", "uncertainty_prompt", False, "Maps uncertainty and evidence gaps."),
        ("Redesign Prompt", "redesign_prompt", False, "Suggests evidence-grounded redesign directions."),
    ]

    for title, key, expanded, description in prompt_meta:
        with st.expander(title, expanded=expanded):
            st.caption(description)
            value = str(prompts.get(key, "") or "")
            if value:
                render_copy_button(value, theme["accent"], theme["border"], theme["accent"])
                st.code(value, language="text")

    look_for = ensure_list(prompts.get("look_for"))
    if look_for:
        checklist_items = "".join(f"<li>{html_safe(item)}</li>" for item in look_for)
        st.markdown(
            f"""
            <div class="checklist-box">
              <div class="checklist-title">Checklist for AI Response</div>
              <ul>{checklist_items}</ul>
            </div>
            """,
            unsafe_allow_html=True,
        )


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
        scan_state = ensure_dict(st.session_state[keys["scan"]])
        snapshot = ensure_dict(scan_state.get("snapshot"))

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
                except Exception as exc:
                    render_note_box("Prompt Generation Error", str(exc))

        if keys["prompts"] in st.session_state:
            prompts = ensure_dict(st.session_state[keys["prompts"]])

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
        matrix = ensure_dict(st.session_state[keys["matrix"]])
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
def main() -> None:
    ensure_session_defaults()

    api_health = get_api_health()
    theme = get_theme(st.session_state.dark_mode)

    inject_css(theme)
    render_sidebar(api_health, theme)
    render_header(theme)

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


if __name__ == "__main__":
    main()