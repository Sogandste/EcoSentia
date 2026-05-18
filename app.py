from __future__ import annotations

import json
import os
import textwrap
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
APP_VERSION = "v0.5.2"
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
    accent: str
    accent_soft: str
    accent_bg: str
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
    "none": {"pct": 5, "color": "#e58b95", "label": "None"},
    "limited": {"pct": 30, "color": "#e7a774", "label": "Limited"},
    "indirect": {"pct": 50, "color": "#d39a68", "label": "Indirect"},
    "moderate": {"pct": 70, "color": "#d8b7حتماً. این هم **نسخه نهایی، یکپارچه و production-ready `app.py`** با اصلاحاتی که خواستی:

## شامل این اصلاحات
- رفع قطعی خطای PDF برای `str` / `bytes` / `bytearray`
- حذف کامل حالت `System` و نگه داشتن فقط `Light / Dark`
- یکدست شدن hover / focus / border با accent **رز-هلویی**
- خوانا شدن tooltipها در هر دو حالت دارک و لایت
- تفکیک بهتر `Checklist for AI Response`
- رز-هلویی شدن بخش `Evidence Support Level`
- حذف باکس‌های رنگی پیش‌فرض Streamlit
- clean, no emoji, no Persian comments

---

## فایل نهایی `app.py`

```python
from __future__ import annotations

import json
import os
import textwrap
from datetime import datetime
from html import escape
from typing import Any, Dict, List, Optional, Tuple, TypedDict, cast

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from fpdf import FPDF

st.set_page_config(page_title="EcoSentia", layout="wide", page_icon="▪")

API_BASE = os.getenv("ECOSENTIA_API_URL", "https://ecosentia.onrender.com")
APP_TITLE = "EcoSentia"
APP_VERSION = "v0.5.2"
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
        response = session.post(f"{API_BASE}{path}", json=payload, timeout=HTTP_TIMEOUT)
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
            "tooltip_bg": "#232730",
            "tooltip_text": "#fafafa",
            "focus_ring": "rgba(231,163,143,0.22)",
            "input_bg": "#11141a",
            "accent": "#e7a38f",
            "accent_soft": "#e7a0ab",
            "accent_bg": "rgba(231,163,143,0.12)",
            "matrix_direct": "rgba(217,221,229,0.10)",
            "matrix_moderate": "rgba(194,201,212,0.12)",
            "matrix_limited": "rgba(235,177,132,0.12)",
            "matrix_none": "rgba(229,154,165,0.12)",
            "matrix_error": "rgba(229,154,165,0.05)",
            "badge_direct": "#d9dde5",
            "badge_moderate": "#c2c9d4",
            "badge_limited": "#ebb184",
            "badge_none": "#e59aa5",
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
        "tooltip_bg": "#17191d",
        "tooltip_text": "#f9fafb",
        "focus_ring": "rgba(216,141,122,0.18)",
        "input_bg": "#ffffff",
        "accent": "#d88d7a",
        "accent_soft": "#cf8695",
        "accent_bg": "rgba(216,141,122,0.10)",
        "matrix_direct": "rgba(125,138,157,0.08)",
        "matrix_moderate": "rgba(156,165,177,0.10)",
        "matrix_limited": "rgba(216,141,122,0.10)",
        "matrix_none": "rgba(207,134,149,0.10)",
        "matrix_error": "rgba(207,134,149,0.05)",
        "badge_direct": "#627084",
        "badge_moderate": "#798392",
        "badge_limited": "#c97f6d",
        "badge_none": "#bf7282",
    }


def inject_css(theme: ThemeDict) -> None:
    st.markdown(
        f"""
<style>
:root {{
  --text-color:{theme['text']}!important;
  --background-color:{theme['bg']}!important;
  --secondary-background-color:{theme['panel']}!important;
  --primary-color:{theme['accent']}!important;
}}

html, body, #root, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="stMainBlockContainer"] {{
  background:{theme['bg']}!important;
  color:{theme['text']}!important;
  font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif!important;
}}

.stMarkdown p, .stMarkdown span, .stMarkdown li, .stMarkdown h1,
.stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5,
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] span, label {{
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
  border-right:1px solid {theme['border']}!important;
}}

[data-testid="collapsedControl"], [data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] button, [data-testid="stSidebarCollapseButton"] button,
button[data-testid="baseButton-headerNoPadding"], button[kind="headerNoPadding"] {{
  background:{theme['panel']}!important;
  border:1px solid {theme['border']}!important;
  border-radius:8px!important;
  box-shadow:0 2px 8px {theme['shadow']}!important;
  opacity:1!important;
  visibility:visible!important;
}}

[data-testid="collapsedControl"] svg, [data-testid="stSidebarCollapseButton"] svg,
button[data-testid="baseButton-headerNoPadding"] svg, button[kind="headerNoPadding"] svg {{
  fill:{theme['icon']}!important;
  stroke:{theme['icon']}!important;
  color:{theme['icon']}!important;
}}

input[type="text"], input[type="number"], input[type="search"], textarea,
div[data-baseweb="select"] > div {{
  background:{theme['input_bg']}!important;
  color:{theme['text']}!important;
  border:1px solid {theme['border']}!important;
  border-radius:10px!important;
  transition:all .16s ease!important;
}}

input::placeholder, textarea::placeholder {{
  color:{theme['text_muted']}!important;
  opacity:.78!important;
}}

input:hover, textarea:hover, input:focus, textarea:focus,
input:focus-visible, textarea:focus-visible,
div[data-baseweb="select"] > div:hover,
div[data-baseweb="select"] > div:focus-within {{
  border-color:{theme['accent']}!important;
  box-shadow:0 0 0 3px {theme['focus_ring']}!important;
  outline:none!important;
}}

div[data-baseweb="select"] svg {{
  fill:{theme['icon']}!important;
  color:{theme['icon']}!important;
}}

div[data-baseweb="popover"] {{
  background:{theme['panel']}!important;
  border:1px solid {theme['accent']}!important;
  border-radius:10px!important;
  box-shadow:0 12px 28px {theme['shadow']}!important;
}}

div[data-baseweb="popover"] ul, div[data-baseweb="popover"] [role="listbox"],
div[data-baseweb="popover"] li, li[role="option"] {{
  background:{theme['panel']}!important;
  color:{theme['text']}!important;
}}

li[role="option"]:hover, li[aria-selected="true"] {{
  background:{theme['hover']}!important;
}}

[data-testid="stExpander"] {{
  background:{theme['panel']}!important;
  border:1px solid {theme['border']}!important;
  border-radius:12px!important;
  box-shadow:0 2px 8px {theme['shadow']}!important;
  overflow:hidden!important;
  margin-bottom:12px!important;
  transition:all .18s ease!important;
}}

[data-testid="stExpander"]:hover {{
  border-color:{theme['accent']}!important;
}}

[data-testid="stExpander"] summary {{
  background:{theme['panel']}!important;
  padding:14px 16px!important;
}}

[data-testid="stExpander"] summary p, [data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary div {{
  color:{theme['text']}!important;
  font-weight:600!important;
}}

[data-testid="stExpander"] > div > div {{
  background:{theme['bg']}!important;
  padding:16px!important;
}}

[data-testid="metric-container"] {{
  background:{theme['panel']}!important;
  border:1px solid {theme['border']}!important;
  border-radius:12px!important;
  box-shadow:0 2px 8px {theme['shadow']}!important;
  transition:all .18s ease!important;
}}

[data-testid="metric-container"]:hover {{
  border-color:{theme['accent']}!important;
  box-shadow:0 0 0 2px {theme['accent_bg']}!important;
}}

[data-testid="stMetricValue"] > div {{
  color:{theme['text']}!important;
  font-weight:700!important;
}}

[data-testid="stMetricLabel"] > div {{
  color:{theme['text_muted']}!important;
}}

.stButton > button, [data-testid="stDownloadButton"] > button {{
  background:{theme['panel']}!important;
  color:{theme['text']}!important;
  border:1px solid {theme['border']}!important;
  border-radius:10px!important;
  box-shadow:0 1px 4px {theme['shadow']}!important;
  transition:all .18s ease!important;
  font-weight:600!important;
}}

.stButton > button:hover, [data-testid="stDownloadButton"] > button:hover,
.stButton > button:focus, [data-testid="stDownloadButton"] > button:focus,
.stButton > button:focus-visible, [data-testid="stDownloadButton"] > button:focus-visible {{
  border-color:{theme['accent']}!important;
  box-shadow:0 0 0 3px {theme['focus_ring']}!important;
  color:{theme['text']}!important;
  outline:none!important;
}}

[data-testid="stTooltipContent"], div[role="tooltip"] {{
  background:{theme['tooltip_bg']}!important;
  color:{theme['tooltip_text']}!important;
  border:1px solid {theme['accent']}!important;
  border-radius:8px!important;
  box-shadow:0 10px 24px {theme['shadow']}!important;
  padding:8px 10px!important;
}}

[data-testid="stTooltipContent"] p, [data-testid="stTooltipContent"] span,
div[role="tooltip"] p, div[role="tooltip"] span {{
  color:{theme['tooltip_text']}!important;
  opacity:1!important;
}}

.stCodeBlock {{
  background:{theme['bg']}!important;
  border:1px solid {theme['accent']}!important;
  border-radius:10px!important;
}}

.stCodeBlock pre, .stCodeBlock code, .stCodeBlock span {{
  color:{theme['text']}!important;
}}

.note-box {{
  background:{theme['panel']};
  border:1px solid {theme['border']};
  border-left:3px solid {theme['accent']};
  border-radius:12px;
  padding:12px 14px;
  margin:8px 0 16px 0;
}}

.note-title {{
  color:{theme['accent']};
  font-size:12px;
  font-weight:700;
  letter-spacing:.45px;
  text-transform:uppercase;
  margin-bottom:6px;
}}

.note-body {{
  color:{theme['text_muted']};
  line-height:1.65;
  font-size:13px;
}}

.risk-panel {{
  background:{theme['panel']}!important;
  border:1px solid {theme['accent']}!important;
  border-left:3px solid {theme['accent_soft']}!important;
  border-radius:10px!important;
  padding:12px 14px!important;
  margin-bottom:10px!important;
  line-height:1.65!important;
}}

.risk-title {{
  color:{theme['accent']}!important;
  font-weight:700!important;
  margin-bottom:5px!important;
  display:block!important;
  font-size:12px!important;
  text-transform:uppercase!important;
  letter-spacing:.45px!important;
}}

.matrix-table {{
  width:100%;
  border-collapse:separate;
  border-spacing:0;
  border:1px solid {theme['accent']}33;
  border-radius:12px;
  overflow:hidden;
  box-shadow:0 2px 8px {theme['shadow']};
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
  border-top:1px solid {theme['border']};
}}

.badge {{
  display:inline-block;
  padding:3px 10px;
  border-radius:999px;
  font-size:11px;
  font-weight:700;
  letter-spacing:.35px;
  text-transform:uppercase;
  background:{theme['accent_bg']}!important;
  color:{theme['accent']}!important;
  border:1px solid {theme['accent']}!important;
}}

.step-title-wrap {{
  display:flex;
  align-items:center;
  gap:8px;
  margin:8px 0 4px 0;
}}

.step-title-text {{
  font-size:1.06rem;
  font-weight:700;
  color:{theme['text']};
}}

.step-tooltip-dot {{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  width:18px;
  height:18px;
  border-radius:999px;
  border:1px solid {theme['accent']};
  color:{theme['accent']};
  font-size:11px;
  cursor:help;
  line-height:1;
  user-select:none;
}}

.checklist-box {{
  background:{theme['panel']};
  border:1px solid {theme['accent']};
  border-radius:12px;
  padding:14px 16px;
  margin-top:10px;
  margin-bottom:14px;
}}

.checklist-title {{
  color:{theme['accent']};
  font-size:12px;
  font-weight:700;
  text-transform:uppercase;
  letter-spacing:.5px;
  margin-bottom:10px;
}}

.checklist-box ul {{
  margin:0;
  padding-left:18px;
}}

.checklist-box li {{
  margin:0 0 8px 0;
  color:{theme['text']};
  line-height:1.6;
}}

::-webkit-scrollbar {{
  width:7px;
}}

::-webkit-scrollbar-track {{
  background:{theme['bg']};
}}

::-webkit-scrollbar-thumb {{
  background:{theme['border']};
  border-radius:999px;
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


def render_note_box(title: str, body: str, theme: ThemeDict) -> None:
    st.markdown(
        f"""
        <div class="note-box">
          <div class="note-title">{html_safe(title)}</div>
          <div class="note-body">{html_safe(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def step_title(title: str, tooltip: str, theme: ThemeDict) -> None:
    st.markdown(
        f"""
        <div class="step-title-wrap">
          <div class="step-title-text">{html_safe(title)}</div>
          <span class="step-tooltip-dot" title="{html_safe(tooltip)}">i</span>
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


def render_copy_button(text: str, icon_color: str, border_color: str) -> None:
    escaped = _js_escape(text)
    components.html(
        f"""
        <button onclick="navigator.clipboard.writeText(`{escaped}`).then(() => {{
            this.innerText = 'Copied';
            this.style.borderColor = '{icon_color}';
            this.style.color = '{icon_color}';
            setTimeout(() => {{
                this.innerText = 'Copy to Clipboard';
                this.style.borderColor = '{border_color}';
                this.style.color = '{icon_color}';
            }}, 1600);
        }})"
        style="background:transparent;border:1px solid {border_color};color:{icon_color};
               border-radius:8px;padding:6px 14px;font-size:12px;
               font-family:Inter,-apple-system,sans-serif;cursor:pointer;
               transition:all .2s;margin-bottom:8px;">
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


def render_sidebar(api_health: str) -> None:
    with st.sidebar:
        st.markdown("## Appearance")
        is_dark = st.radio("Theme", ["Dark", "Light"], horizontal=True, index=0 if st.session_state.dark_mode else 1)
        desired_dark = is_dark == "Dark"
        if desired_dark != st.session_state.dark_mode:
            st.session_state.dark_mode = desired_dark
            st.rerun()

        st.divider()

        st.markdown("## Tools")
        compare_toggle = st.toggle(
            "Claim Comparison Mode",
            value=st.session_state.compare_mode,
            help="Run the same workflow side by side for two claims.",
        )
        if compare_toggle != st.session_state.compare_mode:
            st.session_state.compare_mode = compare_toggle
            st.rerun()

        st.divider()

        st.markdown("## Recent Scans")
        history = cast(List[HistoryEntry], st.session_state["history"])
        if history:
            for h in history:
                bg = "#15171d" if st.session_state.dark_mode else "#ffffff"
                br = "#e7a38f" if st.session_state.dark_mode else "#d88d7a"
                tc = "#f4f4f5" if st.session_state.dark_mode else "#17191d"
                tc2 = "#a7afb9" if st.session_state.dark_mode else "#6e7683"
                st.markdown(
                    f"""
                    <div style="padding:9px 11px;margin-bottom:8px;border-radius:10px;
                                border:1px solid {br};background:{bg};">
                      <div style="font-size:11px;font-weight:600;color:{tc2};">
                        {html_safe(h['time'])} · {html_safe(h['lens']).title()}
                      </div>
                      <div style="font-size:12px;margin-top:4px;color:{tc};line-height:1.45;">
                        {html_safe(h['claim'])}
                      </div>
                      <div style="margin-top:7px;">
                        <span style="font-size:10px;padding:2px 8px;border-radius:999px;
                                     color:{br};border:1px solid {br};">
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


def _wrap_for_pdf(text: str, width: int = 95) -> str:
    safe = pdf_safe(text)
    lines: List[str] = []
    raw_lines = safe.splitlines() or [safe]
    for raw_line in raw_lines:
        if not raw_line.strip():
            lines.append("")
            continue
        lines.append(
            textwrap.fill(
                raw_line,
                width=width,
                break_long_words=True,
                break_on_hyphens=True,
            )
        )
    return "\n".join(lines)


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
    epw = pdf.w - pdf.l_margin - pdf.r_margin

    def safe_multi(text: str, font: str = "Helvetica", style: str = "", size: int = 10, line_h: int = 6) -> None:
        pdf.set_font(font, style, size)
        wrapped = _wrap_for_pdf(text, width=95)
        pdf.multi_cell(epw, line_h, wrapped)

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, pdf_safe("EcoSentia - Evidence Report"), ln=1)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(
        0,
        6,
        pdf_safe(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
            f"Lens: {lens.title()} | Preset: {preset.upper()}"
        ),
        ln=1,
    )
    pdf.set_text_color(15, 23, 42)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, pdf_safe("Design Claim"), ln=1)
    safe_multi(claim)
    pdf.ln(4)

    if snap:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, pdf_safe("Evidence Scan Snapshot"), ln=1)
        safe_multi(f"Total Records: {snap.get('combined_count', '—')}")
        safe_multi(f"Direct Matches: {snap.get('direct_hits', '—')}")
        safe_multi(f"Support Level: {str(snap.get('support_level', '—')).title()}")
        safe_multi(f"Summary: {snap.get('summary', '')}")
        pdf.ln(4)

    if prompts:
        for title, key in [
            ("Master Prompt", "master_prompt"),
            ("Counter Prompt", "counter_prompt"),
            ("Uncertainty Mapping", "uncertainty_prompt"),
            ("Redesign Prompt", "redesign_prompt"),
        ]:
            value = str(prompts.get(key, "") or "")
            if value:
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, pdf_safe(title), ln=1)
                safe_multi(value, font="Courier", size=8, line_h=5)
                pdf.ln(3)

    if matrix:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, pdf_safe("Multi-Lens Audit Matrix"), ln=1)
        pdf.set_font("Helvetica", "", 10)

        for lens_name, result in matrix.items():
            result_dict = ensure_dict(result)
            if result_dict.get("error"):
                line = f"{lens_name.title()}: Error - {result_dict['error']}"
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
                line = (
                    f"{lens_name.title()}: "
                    f"{str(result_dict.get('support_level', 'none')).title()} | "
                    f"Risks: {risk_str}"
                )
            safe_multi(line)

    raw = pdf.output(dest="S")

    if isinstance(raw, bytearray):
        return bytes(raw)
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, str):
        return raw.encode("latin-1", errors="replace")
    return bytes(raw)


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


def render_matrix_table(df: pd.DataFrame, levels: List[str], theme: ThemeDict) -> None:
    rows_html = ""
    for i, (_, row) in enumerate(df.iterrows()):
        _ = levels[i] if i < len(levels) else "none"
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
        delete_keys(
            [
                keys["refined_query"],
                keys["active_query"],
                keys["scan"],
                keys["prompts"],
                keys["matrix"],
                keys["pdf_cache"],
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
        theme,
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

    render_note_box(f"Support: {level.title()}", evidence_note, theme)

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
        render_note_box("Risk Review", "No translation risk patterns detected.", theme)

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
                render_copy_button(value, theme["accent"], theme["accent"])
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

    step_title(
        "Step 1: Refine Search Query",
        "Extract key concepts from the claim and build a retrieval-oriented Boolean query.",
        theme,
    )
    st.caption("Builds a literature-oriented query from the current claim and configuration.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Refine Query", key=f"refine_btn_{pid}", use_container_width=True, help="Generate a refined query from the current claim."):
            with st.spinner("Refining query..."):
                try:
                    response = api_post("/evidence/refine-query", payload_base)
                    refined_query = extract_refined_query(response, claim_text)
                    st.session_state[keys["refined_query"]] = refined_query
                    st.session_state[keys["active_query"]] = refined_query
                except Exception as exc:
                    render_note_box("Refine Query Error", str(exc), theme)

    with c2:
        if st.button("Use Claim As Query", key=f"use_claim_btn_{pid}", use_container_width=True, help="Skip refinement and use the claim directly as query text."):
            st.session_state[keys["refined_query"]] = claim_text
            st.session_state[keys["active_query"]] = claim_text

    if keys["active_query"] not in st.session_state:
        st.session_state[keys["active_query"]] = st.session_state.get(keys["refined_query"], claim_text)

    st.text_area(
        "Active Query",
        key=keys["active_query"],
        height=100,
        help="Editable query used for the next scan.",
    )
    q_text = str(st.session_state.get(keys["active_query"], claim_text))

    st.divider()

    step_title(
        "Step 2: Run Evidence Scan",
        "Retrieve literature for the active query and score the current claim against the evidence snapshot.",
        theme,
    )
    st.caption("Queries the selected literature source and builds an evidence snapshot.")

    if st.button("Execute Scan", key=f"scan_btn_{pid}", use_container_width=True, help="Run the main evidence scan with the active query."):
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
                delete_keys([keys["pdf_cache"]])
            except Exception as exc:
                render_note_box("Scan Error", str(exc), theme)

    if keys["scan"] in st.session_state:
        scan_state = ensure_dict(st.session_state[keys["scan"]])
        snapshot = ensure_dict(scan_state.get("snapshot"))
        render_scan_results(snapshot, theme)

    st.divider()

    step_title(
        "Step 3: Generate Evidence-Aware Prompts",
        "Create structured prompts that explicitly reflect support strength, uncertainty, and redesign direction.",
        theme,
    )
    st.caption("Turns the current evidence state into reusable LLM prompts.")

    if keys["scan"] not in st.session_state:
        render_note_box("Step Incomplete", "Please complete Step 2 before generating prompts.", theme)
    else:
        if st.button("Generate Prompts", key=f"prompts_btn_{pid}", use_container_width=True, help="Generate master, counter, uncertainty, and redesign prompts."):
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
                    delete_keys([keys["pdf_cache"]])
                except Exception as exc:
                    render_note_box("Prompt Generation Error", str(exc), theme)

        if keys["prompts"] in st.session_state:
            prompts = ensure_dict(st.session_state[keys["prompts"]])
            render_prompt_results(prompts, theme)

    st.divider()

    step_title(
        "Step 4: Full Multi-Lens Audit",
        "Run the evidence pipeline across all analytical lenses and return a comparative matrix.",
        theme,
    )
    st.caption("Produces a multi-lens summary suitable for export and reporting.")

    if st.button("Execute Full Audit", key=f"audit_btn_{pid}", use_container_width=True, help="Run the current claim across all configured lenses."):
        with st.spinner("Scanning all lenses..."):
            try:
                response = api_post("/evidence/scan-all-lenses", payload_base)
                matrix = extract_lens_matrix(response)
                st.session_state[keys["matrix"]] = matrix
                delete_keys([keys["pdf_cache"]])
            except Exception as exc:
                render_note_box("Audit Error", str(exc), theme)

    if keys["matrix"] in st.session_state:
        matrix = ensure_dict(st.session_state[keys["matrix"]])
        df, levels = build_matrix_dataframe(matrix)

        st.markdown("#### Analytical Lens Matrix")
        render_matrix_table(df, levels, theme)

        d1, d2, d3 = st.columns(3)

        with d1:
            st.download_button(
                "Download CSV",
                df.to_csv(index=False).encode("utf-8"),
                f"ecosentia_matrix_{pid}.csv",
                "text/csv",
                key=f"csv_btn_{pid}",
                use_container_width=True,
                help="Export the lens matrix as CSV.",
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
                help="Export the lens matrix as JSON.",
            )

        with d3:
            if keys["pdf_cache"] not in st.session_state:
                try:
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
                except Exception as exc:
                    render_note_box("PDF Generation Error", str(exc), theme)
                    st.session_state[keys["pdf_cache"]] = b""

            if st.session_state.get(keys["pdf_cache"]):
                st.download_button(
                    "Download PDF",
                    st.session_state[keys["pdf_cache"]],
                    f"ecosentia_report_{pid}.pdf",
                    "application/pdf",
                    key=f"pdf_btn_{pid}",
                    use_container_width=True,
                    help="Export a compact PDF report.",
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
        domain_mode = st.radio(
            "Preset",
            ["Fog", "EV", "Custom"],
            horizontal=True,
            help="Select the primary problem framing used for query refinement and prompting.",
        )
    with c2:
        lens_ui = st.selectbox(
            "Evaluation Lens",
            ["Mechanism", "Context", "Scale", "Manufacturability", "Safety"],
            help="Select the active analytical lens for the main workflow.",
        )

    c3, c4 = st.columns(2)
    with c3:
        source = st.radio(
            "Literature Source",
            ["Both", "PubMed", "OpenAlex"],
            horizontal=True,
            help="Choose the source used for literature retrieval.",
        )
    with c4:
        max_results = st.slider(
            "Max Results Per Source",
            1,
            10,
            5,
            help="Maximum number of records requested from each selected source.",
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
                    help="Optional biological source or analogue.",
                )
                app_ctx = st.text_input(
                    "Application Context",
                    placeholder="e.g., Wet biomedical surfaces",
                    help="Optional use context that helps disambiguate the search.",
                )
            with x2:
                trg_func = st.text_input(
                    "Target Function",
                    placeholder="e.g., Reversible adhesion",
                    help="Optional target function of the design claim.",
                )
                mech_kw = st.text_input(
                    "Mechanism Keywords",
                    placeholder="e.g., microstructure, van der Waals",
                    help="Optional mechanism hints for better refinement.",
                )
            excl_kw = st.text_input(
                "Exclude Terms",
                placeholder="e.g., vaccine, remote sensing",
                help="Optional exclusion terms to reduce noisy retrieval.",
            )

    if not st.session_state.compare_mode:
        claim_main = st.text_area(
            "Design Claim",
            value=DEFAULT_CLAIMS.get(domain_mode, ""),
            height=120,
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
                height=120,
                key="claim_a",
                help="First claim for side-by-side comparison.",
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
                height=120,
                key="claim_b",
                help="Second claim for side-by-side comparison.",
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