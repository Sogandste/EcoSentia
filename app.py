# app.py
# EcoSentia Evidence Studio — Streamlit frontend
# Version: v0.5.1
# Fixes applied vs v0.5:
#   1. q_text now read from session_state instead of widget return value
#      (prevents stale query being sent when Refine + Scan happen in the same rerun)
#   2. render_copy_button escapes </ and " to prevent JS injection
#   3. render_panel calls ensure_session_defaults() as a guard for direct invocation
#   4. build_matrix_dataframe returns (display_df, levels) as separate objects
#      so _level never leaks into CSV / JSON exports

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

# ---------------------------------------------------------------------------
# Page config — must be the very first Streamlit call in the file
# ---------------------------------------------------------------------------
st.set_page_config(page_title="EcoSentia", layout="wide", page_icon="▪")

# ---------------------------------------------------------------------------
# Global constants
# ---------------------------------------------------------------------------
API_BASE       = os.getenv("ECOSENTIA_API_URL", "https://ecosentia.onrender.com")
APP_TITLE      = "EcoSentia"
APP_VERSION    = "v0.5.1"
HTTP_TIMEOUT   = 120   # seconds — generous for cold-start Render instances
HEALTH_TIMEOUT = 10    # seconds — health check only needs a fast response


# ---------------------------------------------------------------------------
# TypedDict schemas
# Used for IDE autocomplete and static analysis; not enforced at runtime.
# ---------------------------------------------------------------------------

class SupportLevelConfig(TypedDict):
    pct:   int    # fill percentage for the progress bar (0–100)
    color: str    # hex colour for the bar and badge
    label: str    # display label


class ThemeDict(TypedDict):
    # Base surfaces
    bg:           str
    panel:        str
    # Typography
    text:         str
    text_muted:   str
    # Borders and interaction
    border:       str
    hover:        str
    icon:         str
    shadow:       str
    focus_ring:   str
    # Form inputs
    input_bg:     str
    # Tooltip surfaces (always inverted for contrast)
    tooltip_bg:   str
    tooltip_text: str
    # Matrix cell background tints
    matrix_direct:   str
    matrix_moderate: str
    matrix_limited:  str
    matrix_none:     str
    matrix_error:    str
    # Badge foreground colours
    badge_direct:   str
    badge_moderate: str
    badge_limited:  str
    badge_none:     str


class HistoryEntry(TypedDict):
    time:    str
    claim:   str
    lens:    str
    support: str


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

# Maps a support level string to its visual config.
# pct drives the evidence bar fill; kept proportional, not linear.
SUPPORT_LEVELS: Dict[str, SupportLevelConfig] = {
    "none":     {"pct": 5,   "color": "#ef4444", "label": "None"},
    "limited":  {"pct": 30,  "color": "#f59e0b", "label": "Limited"},
    "indirect": {"pct": 50,  "color": "#f59e0b", "label": "Indirect"},
    "moderate": {"pct": 70,  "color": "#3b82f6", "label": "Moderate"},
    "direct":   {"pct": 100, "color": "#10b981", "label": "Direct"},
}

# Pre-filled design claims shown when a preset is selected.
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


# ===========================================================================
# Section 1 — HTTP and session utilities
# ===========================================================================

def get_http_session() -> requests.Session:
    """
    Return a persistent requests.Session stored in Streamlit session_state.

    Reusing a single Session object enables HTTP keep-alive and connection
    pooling across API calls within the same browser session, which reduces
    latency noticeably on Render's cold-start instances.
    """
    if "_http_session" not in st.session_state:
        st.session_state["_http_session"] = requests.Session()
    return cast(requests.Session, st.session_state["_http_session"])


def ensure_session_defaults() -> None:
    """
    Initialise session_state keys that must exist before any widget renders.

    This function is idempotent — calling it multiple times is safe.
    It is intentionally called at the top of both main() and render_panel()
    so that render_panel() can be invoked directly (e.g. in tests) without
    depending on main() having run first.
    """
    defaults: Dict[str, Any] = {
        "dark_mode":    False,
        "compare_mode": False,
        "history":      [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def delete_keys(keys: List[str]) -> None:
    """Remove a list of keys from session_state if they exist."""
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]


# ===========================================================================
# Section 2 — Defensive data accessors
# ===========================================================================

def safe_get(data: Any, *path: str, default: Any = None) -> Any:
    """
    Traverse a nested dict using a sequence of string keys.

    Returns `default` at any point where the path is missing or the current
    node is not a dict.  Never raises KeyError or TypeError.

    Example:
        safe_get(response, "data", "snapshot", "support_level", default="none")
    """
    current = data
    for key in path:
        if not isinstance(current, dict):
            return default
        if key not in current:
            return default
        current = current[key]
    return current


def first_non_empty(*values: Any) -> Any:
    """
    Return the first value that is not None, "", [], or {}.

    Used to probe multiple possible API response shapes without nested
    if/elif chains, making response extraction resilient to backend changes.
    """
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def ensure_dict(value: Any) -> Dict[str, Any]:
    """Return value if it is already a dict, otherwise return {}."""
    return value if isinstance(value, dict) else {}


def ensure_list(value: Any) -> List[Any]:
    """Return value if it is already a list, otherwise return []."""
    return value if isinstance(value, list) else []


def coerce_bias_list(value: Any) -> List[Any]:
    """
    Normalise a detected_biases field from the API into a plain list.

    The backend may return:
      - a list of dicts  → returned as-is
      - a single dict    → wrapped in a list
      - a non-empty str  → wrapped in a list
      - None / empty     → empty list
    """
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


# ===========================================================================
# Section 3 — API communication
# ===========================================================================

def api_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST JSON to the EcoSentia backend and return the parsed response dict.

    Error handling:
      - HTTPError:        parses FastAPI detail field and re-raises as RuntimeError
      - RequestException: wraps network-level errors as RuntimeError
      - ValueError:       catches malformed JSON responses
    """
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
            raise RuntimeError(
                f"Unexpected API response format at {path}: expected JSON object."
            )
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
    """
    Fetch the /health endpoint and return a formatted status string.

    The result is cached in session_state for the lifetime of the browser
    session.  Without caching, a network request would fire on every Streamlit
    rerun (theme toggle, slider move, etc.), adding unnecessary latency.
    """
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


# ===========================================================================
# Section 4 — API response extractors
# ===========================================================================

def extract_refined_query(response: Dict[str, Any], fallback_claim: str) -> str:
    """
    Pull the refined query string from any known response shape.

    Falls back to the original claim text so the UI always has something
    meaningful to display even if the backend returns an unexpected schema.
    """
    query = first_non_empty(
        response.get("refined_query"),
        response.get("query"),
        response.get("refined"),
        safe_get(response, "data", "refined_query"),
        safe_get(response, "data", "query"),
    )
    return str(query) if query else fallback_claim


def extract_scan_payload(
    response: Dict[str, Any],
    fallback_query: str,
) -> Tuple[Dict[str, Any], str]:
    """
    Extract the evidence snapshot and the query text actually used by the backend.

    Returns a (snapshot_dict, query_text) tuple.  Both fields fall back
    gracefully if the backend response structure changes.
    """
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
    """
    Extract the prompts dict from the /evidence/prompts response.

    Handles three known response shapes:
      - {"prompts": {...}}
      - {"data": {"prompts": {...}}}
      - flat dict with "master_prompt" at the top level
    """
    prompts = first_non_empty(
        response.get("prompts"),
        safe_get(response, "data", "prompts"),
        response if "master_prompt" in response else None,
    )
    return ensure_dict(prompts)


def extract_lens_matrix(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract the per-lens audit matrix from the /evidence/scan-all-lenses response.

    Probes several known key names so minor backend renames do not break the UI.
    """
    matrix = first_non_empty(
        response.get("lens_matrix"),
        response.get("matrix"),
        safe_get(response, "data", "lens_matrix"),
        safe_get(response, "results", "lens_matrix"),
    )
    return ensure_dict(matrix)


# ===========================================================================
# Section 5 — Theme system
# ===========================================================================

def get_theme(dark_mode: bool) -> ThemeDict:
    """
    Return a symmetrical ThemeDict for the requested colour scheme.

    Dark and light palettes use identical token names so all downstream
    CSS and HTML can reference the same keys without any branching logic.
    """
    if dark_mode:
        return {
            "bg":            "#0f172a",
            "panel":         "#1e293b",
            "text":          "#f1f5f9",
            "text_muted":    "#94a3b8",
            "border":        "#334155",
            "hover":         "#2d3f55",
            "icon":          "#f1f5f9",
            "shadow":        "rgba(0,0,0,0.40)",
            "focus_ring":    "rgba(148,163,184,0.30)",
            "input_bg":      "#1e293b",
            # Tooltip is always light-on-dark for maximum contrast
            "tooltip_bg":    "#f8fafc",
            "tooltip_text":  "#0f172a",
            # Matrix cell tints — semi-transparent so the panel colour shows through
            "matrix_direct":   "rgba(16,185,129,0.18)",
            "matrix_moderate": "rgba(59,130,246,0.18)",
            "matrix_limited":  "rgba(245,158,11,0.18)",
            "matrix_none":     "rgba(239,68,68,0.18)",
            "matrix_error":    "rgba(239,68,68,0.10)",
            # Badge foreground colours — lighter variants for dark backgrounds
            "badge_direct":   "#34d399",
            "badge_moderate": "#60a5fa",
            "badge_limited":  "#fbbf24",
            "badge_none":     "#f87171",
        }

    return {
        "bg":            "#f8fafc",
        "panel":         "#ffffff",
        "text":          "#0f172a",
        "text_muted":    "#475569",
        "border":        "#94a3b8",
        "hover":         "#f1f5f9",
        "icon":          "#0f172a",
        "shadow":        "rgba(15,23,42,0.10)",
        "focus_ring":    "rgba(15,23,42,0.12)",
        "input_bg":      "#ffffff",
        # Tooltip is always dark-on-light for maximum contrast
        "tooltip_bg":    "#0f172a",
        "tooltip_text":  "#f8fafc",
        # Matrix cell tints — lighter for white backgrounds
        "matrix_direct":   "rgba(4,120,87,0.10)",
        "matrix_moderate": "rgba(29,78,216,0.10)",
        "matrix_limited":  "rgba(180,83,9,0.10)",
        "matrix_none":     "rgba(185,28,28,0.10)",
        "matrix_error":    "rgba(185,28,28,0.05)",
        # Badge foreground colours — darker variants for light backgrounds
        "badge_direct":   "#065f46",
        "badge_moderate": "#1e3a8a",
        "badge_limited":  "#92400e",
        "badge_none":     "#991b1b",
    }


# ===========================================================================
# Section 6 — CSS injection
# ===========================================================================

def inject_css(theme: ThemeDict) -> None:
    """
    Inject a complete CSS layer that overrides Streamlit's default styling.

    All selectors use !important to win specificity races against Streamlit's
    own injected styles without needing to match their internal class names,
    which change between Streamlit versions.

    Custom classes (.risk-panel, .matrix-table, .badge-*) are defined here
    so they can be used safely in unsafe_allow_html blocks throughout the app.
    """
    st.markdown(
        f"""
<style>
/* ── CSS custom properties ───────────────────────────────────────────────── */
:root {{
  --text-color:{theme['text']}!important;
  --background-color:{theme['bg']}!important;
  --secondary-background-color:{theme['panel']}!important;
  --primary-color:{theme['text_muted']}!important;
}}

/* ── Base surfaces ───────────────────────────────────────────────────────── */
html, body, #root, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="stMainBlockContainer"] {{
  background:{theme['bg']}!important;
  color:{theme['text']}!important;
  font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif!important;
}}

/* ── Typography ──────────────────────────────────────────────────────────── */
.stMarkdown p, .stMarkdown span, .stMarkdown li,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4,
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

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"], [data-testid="stSidebar"] > div {{
  background:{theme['panel']}!important;
  border-right:1.5px solid {theme['border']}!important;
}}

/* Sidebar collapse / expand button — kept visible in both themes */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] button,
[data-testid="stSidebarCollapseButton"] button,
button[data-testid="baseButton-headerNoPadding"],
button[kind="headerNoPadding"] {{
  background:{theme['panel']}!important;
  border:2px solid {theme['border']}!important;
  border-radius:9px!important;
  box-shadow:0 3px 10px {theme['shadow']}!important;
  opacity:1!important;
  visibility:visible!important;
}}

[data-testid="collapsedControl"] svg,
[data-testid="stSidebarCollapseButton"] svg,
button[data-testid="baseButton-headerNoPadding"] svg,
button[kind="headerNoPadding"] svg {{
  fill:{theme['icon']}!important;
  stroke:{theme['icon']}!important;
  color:{theme['icon']}!important;
  opacity:1!important;
}}

/* ── Form inputs ─────────────────────────────────────────────────────────── */
input[type="text"], input[type="number"], input[type="search"],
textarea, div[data-baseweb="select"] > div {{
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

/* Dropdown caret — fill must match text so it stays visible in both themes */
div[data-baseweb="select"] svg {{
  fill:{theme['icon']}!important;
  color:{theme['icon']}!important;
}}

/* ── Dropdown popover ────────────────────────────────────────────────────── */
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

/* ── Expanders ───────────────────────────────────────────────────────────── */
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

/* ── Metrics ─────────────────────────────────────────────────────────────── */
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

/* ── Alerts ──────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {{
  background:{theme['panel']}!important;
  border:1.5px solid {theme['border']}!important;
  border-radius:8px!important;
}}

/* ── Tooltips ────────────────────────────────────────────────────────────── */
[data-testid="stTooltipContent"], div[role="tooltip"] {{
  background:{theme['tooltip_bg']}!important;
  border:1px solid {theme['border']}!important;
  border-radius:8px!important;
}}

[data-testid="stTooltipContent"] p,
[data-testid="stTooltipContent"] span,
div[role="tooltip"] p,
div[role="tooltip"] span {{
  color:{theme['tooltip_text']}!important;
}}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
.stButton > button, [data-testid="stDownloadButton"] > button {{
  background:{theme['panel']}!important;
  color:{theme['text']}!important;
  border:1.5px solid {theme['border']}!important;
  border-radius:8px!important;
  box-shadow:0 2px 5px {theme['shadow']}!important;
}}

/* ── Code blocks ─────────────────────────────────────────────────────────── */
.stCodeBlock {{
  background:{theme['bg']}!important;
  border:1.5px solid {theme['border']}!important;
  border-radius:8px!important;
}}

.stCodeBlock pre, .stCodeBlock code, .stCodeBlock span {{
  color:{theme['text']}!important;
}}

/* ── Custom component: risk panel ────────────────────────────────────────── */
/* Used by render_prompt_results() to display translation risk patterns */
.risk-panel {{
  background:linear-gradient(135deg,rgba(249,115,22,.08),rgba(239,68,68,.08))!important;
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

/* ── Custom component: lens matrix table ─────────────────────────────────── */
/* Used by render_matrix_table() — replaces st.dataframe for full theme control */
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

/* ── Custom component: support level badges ──────────────────────────────── */
/* Each modifier class matches a support level string from the API */
.badge {{
  display:inline-block;
  padding:3px 10px;
  border-radius:999px;
  font-size:12px;
  font-weight:700;
}}

.badge-direct {{
  background:{theme['matrix_direct']};
  color:{theme['badge_direct']}!important;
  border:1px solid {theme['badge_direct']};
}}
.badge-moderate {{
  background:{theme['matrix_moderate']};
  color:{theme['badge_moderate']}!important;
  border:1px solid {theme['badge_moderate']};
}}
.badge-limited {{
  background:{theme['matrix_limited']};
  color:{theme['badge_limited']}!important;
  border:1px solid {theme['badge_limited']};
}}
.badge-indirect {{
  background:{theme['matrix_limited']};
  color:{theme['badge_limited']}!important;
  border:1px solid {theme['badge_limited']};
}}
.badge-none {{
  background:{theme['matrix_none']};
  color:{theme['badge_none']}!important;
  border:1px solid {theme['badge_none']};
}}
.badge-error {{
  background:{theme['matrix_error']};
  color:{theme['badge_none']}!important;
  border:1px solid {theme['badge_none']};
}}

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar {{ width:7px; }}
::-webkit-scrollbar-track {{ background:{theme['bg']}; }}
::-webkit-scrollbar-thumb {{ background:{theme['border']}; border-radius:999px; }}
</style>
        """,
        unsafe_allow_html=True,
    )


# ===========================================================================
# Section 7 — UI rendering helpers
# ===========================================================================

def render_header(theme: ThemeDict) -> None:
    """Render the top-of-page logo and title block."""
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:16px;
                    margin-bottom:28px;margin-top:8px;">
          <svg width="40" height="40" viewBox="0 0 100 100"
               xmlns="http://www.w3.org/2000/svg">
            <circle cx="50" cy="50" r="45"
                    fill="none" stroke="{theme['text']}"
                    stroke-width="2" opacity="0.15"/>
            <path d="M50 85 C80 80, 85 45, 50 15 C65 40, 65 65, 50 85 Z"
                  fill="none" stroke="{theme['text']}"
                  stroke-width="2.5" stroke-linecap="round"/>
            <line x1="50" y1="35" x2="50" y2="85"
                  fill="none" stroke="{theme['text']}"
                  stroke-width="2.5" stroke-linecap="round" opacity="0.8"/>
            <path d="M30 25 L70 25 L60 35 L40 35 Z"
                  fill="none" stroke="{theme['text']}"
                  stroke-width="2.5" opacity="0.8"/>
          </svg>
          <div>
            <div style="font-size:22px;font-weight:600;letter-spacing:.4px;
                        color:{theme['text']};line-height:1.15;">
              {APP_TITLE}
            </div>
            <div style="font-size:11px;letter-spacing:1px;
                        color:{theme['text_muted']};margin-top:4px;
                        text-transform:uppercase;font-weight:500;">
              Evidence and Interrogation Layer {APP_VERSION}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_support_bar_html(level: str, text_color: str, border_color: str) -> str:
    """
    Return an HTML string for the horizontal evidence support bar.

    The bar uses inline styles only (no custom class) so it works wherever
    st.markdown(unsafe_allow_html=True) is called, independent of the CSS
    class definitions in inject_css().
    """
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
        <div style="width:{cfg['pct']}%;height:100%;
                    background:{cfg['color']};border-radius:999px;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:5px;
                  font-size:10px;color:{text_color};opacity:.45;">
        <span>None</span><span>Limited</span><span>Indirect</span>
        <span>Moderate</span><span>Direct</span>
      </div>
    </div>
    """


def _js_escape(text: str) -> str:
    """
    Escape a Python string for safe embedding inside a JS template literal.

    Handles the following attack / breakage vectors:
      \\      → \\\\ (literal backslash in template literal)
      `       → \\`  (closes the template literal prematurely)
      \\n      → \\n  (preserves newlines as JS escape, not raw newline)
      \\r      → removed (normalise line endings)
      </      → <\\/  (prevents </script> injection when embedded in HTML)
      "       → \\"  (defensive — protects onclick attribute boundary)
    """
    return (
        text
        .replace("\\", "\\\\")
        .replace("`",  "\\`")
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace("</", "<\\/")
        .replace('"',  '\\"')
    )


def render_copy_button(text: str, icon_color: str, border_color: str) -> None:
    """
    Render a small 'Copy to Clipboard' button using the browser Clipboard API.

    The button is injected via components.html() as a self-contained HTML
    snippet so it runs in its own iframe and avoids polluting the main DOM.

    Fix applied in v0.5.1:
        _js_escape() now escapes </ and " in addition to the original
        backslash / backtick / newline replacements, preventing HTML/JS
        injection when prompt text contains those characters.
    """
    escaped = _js_escape(text)
    components.html(
        f"""
        <button
          onclick="navigator.clipboard.writeText(`{escaped}`).then(() => {{
            this.innerText = 'Copied';
            this.style.borderColor = '#10b981';
            this.style.color = '#10b981';
            setTimeout(() => {{
              this.innerText = 'Copy to Clipboard';
              this.style.borderColor = '{border_color}';
              this.style.color = '{icon_color}';
            }}, 1800);
          }})"
          style="background:transparent;border:1px solid {border_color};
                 color:{icon_color};border-radius:6px;padding:5px 14px;
                 font-size:12px;font-family:Inter,-apple-system,sans-serif;
                 cursor:pointer;transition:all .2s;margin-bottom:8px;">
          Copy to Clipboard
        </button>
        """,
        height=42,
    )


def add_history_entry(claim: str, lens: str, support_level: str) -> None:
    """
    Prepend a scan result to the session history shown in the sidebar.

    Deduplication is based on (claim[:60], lens) so rescanning the same
    claim with the same lens after a configuration change does not create
    duplicate entries, but a different lens produces a new entry.

    The history list is capped at 5 entries (most recent first).
    """
    short_claim = claim[:60] + "..." if len(claim) > 60 else claim
    entry: HistoryEntry = {
        "time":    datetime.now().strftime("%H:%M"),
        "claim":   short_claim,
        "lens":    lens,
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
    """
    Render the application sidebar.

    Contains:
      - Dark / light mode toggle
      - Compare mode toggle
      - Recent scan history (last 5, most recent first)
      - About section and API status caption
    """
    with st.sidebar:
        st.markdown("## Appearance")
        is_dark = st.toggle("Dark Mode", value=st.session_state.dark_mode)
        if is_dark != st.session_state.dark_mode:
            # Persist the change and force a full rerun so inject_css()
            # is called again with the new theme before any widget renders.
            st.session_state.dark_mode = is_dark
            st.rerun()

        st.divider()
        st.markdown("## Tools")
        compare_toggle = st.toggle(
            "Claim Comparison Mode",
            value=st.session_state.compare_mode,
            help=(
                "Enable side-by-side evaluation of two design claims "
                "using identical configuration."
            ),
        )
        if compare_toggle != st.session_state.compare_mode:
            st.session_state.compare_mode = compare_toggle
            st.rerun()

        st.divider()
        st.markdown("## Recent Scans")

        history = cast(List[HistoryEntry], st.session_state["history"])
        if history:
            for h in history:
                # Resolve colours locally so the history cards always match
                # the current theme without importing theme tokens here.
                lc  = SUPPORT_LEVELS.get(h["support"].lower(), {"color": "#94a3b8"})
                bg  = "#1e293b" if st.session_state.dark_mode else "#f1f5f9"
                br  = "#334155" if st.session_state.dark_mode else "#cbd5e1"
                tc  = "#f1f5f9" if st.session_state.dark_mode else "#0f172a"
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
                        <span style="font-size:11px;padding:2px 8px;
                                     border-radius:999px;color:{lc['color']};
                                     border:1px solid {lc['color']};">
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
            "literature, detects translation risk patterns, and generates "
            "structured evidence-aware prompts."
        )
        st.caption(api_health)


# ===========================================================================
# Section 8 — PDF report generation
# ===========================================================================

def pdf_safe(text: Any) -> str:
    """
    Sanitise a value for fpdf2's latin-1 output stream.

    Replaces common Unicode typographic characters (smart quotes, em-dash,
    bullet, ellipsis) with ASCII equivalents, then encodes to latin-1 with
    replace error handling so any remaining non-latin characters become '?'
    rather than raising UnicodeEncodeError.
    """
    if text is None:
        return ""

    replacements = {
        "\u2014": "-",   # em dash
        "\u2013": "-",   # en dash
        "\u201c": '"',   # left double quotation mark
        "\u201d": '"',   # right double quotation mark
        "\u2018": "'",   # left single quotation mark
        "\u2019": "'",   # right single quotation mark
        "\u2022": "-",   # bullet
        "\u2026": "...", # horizontal ellipsis
        "\u00a0": " ",   # non-breaking space
    }
    s = str(text)
    for bad, good in replacements.items():
        s = s.replace(bad, good)
    return s.encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf_report(
    claim:   str,
    lens:    str,
    preset:  str,
    snap:    Optional[Dict[str, Any]],
    prompts: Optional[Dict[str, Any]],
    matrix:  Optional[Dict[str, Any]],
) -> bytes:
    """
    Build and return a PDF evidence report as a bytes object.

    Sections rendered (if data is available):
      1. Header — title, generation timestamp, lens, preset
      2. Design Claim
      3. Evidence Scan Snapshot (metrics + summary)
      4. Generated Prompts (master, counter, uncertainty, redesign)
      5. Multi-Lens Audit Matrix (per-lens support level and risks)

    Compatibility note:
      fpdf2 >= 2.7 returns bytes from pdf.output() with no arguments.
      Older versions require pdf.output(dest='S') and return a bytearray.
      Both cases are handled via the try/except block at the end.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # -- Header
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, pdf_safe("EcoSentia - Evidence Report"), ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 116, 139)  # muted grey for metadata line
    pdf.cell(
        0, 6,
        pdf_safe(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
            f"Lens: {lens.title()} | Preset: {preset.upper()}"
        ),
        ln=True,
    )
    pdf.set_text_color(15, 23, 42)
    pdf.ln(4)

    # -- Design Claim
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, pdf_safe("Design Claim"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, pdf_safe(claim))
    pdf.ln(4)

    # -- Evidence Snapshot
    if snap:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, pdf_safe("Evidence Scan Snapshot"), ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, pdf_safe(f"Total Records: {snap.get('combined_count', '—')}"), ln=True)
        pdf.cell(0, 6, pdf_safe(f"Direct Matches: {snap.get('direct_hits', '—')}"), ln=True)
        pdf.cell(
            0, 6,
            pdf_safe(f"Support Level: {str(snap.get('support_level', '—')).title()}"),
            ln=True,
        )
        pdf.multi_cell(0, 6, pdf_safe(f"Summary: {snap.get('summary', '')}"))
        pdf.ln(4)

    # -- Prompts
    if prompts:
        for title, key in [
            ("Master Prompt",      "master_prompt"),
            ("Counter Prompt",     "counter_prompt"),
            ("Uncertainty Mapping","uncertainty_prompt"),
            ("Redesign Prompt",    "redesign_prompt"),
        ]:
            value = prompts.get(key, "")
            if value:
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, pdf_safe(title), ln=True)
                pdf.set_font("Courier", "", 8)
                pdf.multi_cell(0, 5, pdf_safe(value))
                pdf.ln(3)

    # -- Lens matrix
    if matrix:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, pdf_safe("Multi-Lens Audit Matrix"), ln=True)
        pdf.set_font("Helvetica", "", 10)

        for lens_name, result in matrix.items():
            result_dict = ensure_dict(result)
            if "error" in result_dict:
                line = f"{lens_name.title()}: Error - {result_dict['error']}"
            else:
                biases   = coerce_bias_list(result_dict.get("detected_biases"))
                risk_str = (
                    ", ".join(
                        b.get("bias", "") if isinstance(b, dict) else str(b)
                        for b in biases
                    )
                    if biases else "None"
                )
                line = (
                    f"{lens_name.title()}: "
                    f"{str(result_dict.get('support_level', 'none')).title()} | "
                    f"Risks: {risk_str}"
                )
            pdf.multi_cell(0, 6, pdf_safe(line))

    # -- Output
    try:
        raw = pdf.output()
    except TypeError:
        # fpdf2 < 2.7 compatibility path
        raw = pdf.output(dest="S")

    return bytes(raw) if not isinstance(raw, bytes) else raw


# ===========================================================================
# Section 9 — Payload builders
# ===========================================================================

def build_base_payload(
    pid:         str,
    claim_text:  str,
    domain_mode: str,
    lens_ui:     str,
    source:      str,
    max_results: int,
    bio_model:   str,
    trg_func:    str,
    app_ctx:     str,
    mech_kw:     str,
    excl_kw:     str,
) -> Dict[str, Any]:
    """
    Construct the shared JSON payload sent to all four API endpoints.

    Having a single builder ensures that if the backend adds or renames
    a field, there is exactly one place to update in the frontend.
    """
    return {
        "session_id":          f"streamlit-{pid}",
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


def build_matrix_dataframe(
    matrix: Dict[str, Any],
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Convert the lens matrix dict into a display DataFrame and a parallel
    list of level strings used for badge CSS class selection.

    Returns:
        display_df  — DataFrame with columns ["Lens", "Support", "Risks"].
                      Contains no internal columns; safe to export directly.
        levels      — List of lowercase support level strings, one per row,
                      in the same order as display_df.  Used only by
                      render_matrix_table() to inject badge CSS classes.

    Fix applied in v0.5.1:
        Previously _level was stored as a column inside the DataFrame,
        which leaked into CSV / JSON exports when callers forgot to drop it.
        It is now returned as a separate list, completely decoupled from
        the exportable DataFrame.
    """
    rows:   List[Dict[str, str]] = []
    levels: List[str]            = []

    for lens_name, result in matrix.items():
        result_dict = ensure_dict(result)

        if "error" in result_dict:
            rows.append({
                "Lens":    lens_name.capitalize(),
                "Support": "Error",
                "Risks":   str(result_dict["error"]),
            })
            levels.append("error")
        else:
            biases   = coerce_bias_list(result_dict.get("detected_biases"))
            risk_str = (
                ", ".join(
                    b.get("bias", "") if isinstance(b, dict) else str(b)
                    for b in biases
                )
                if biases else "None"
            )
            rows.append({
                "Lens":    lens_name.capitalize(),
                "Support": str(result_dict.get("support_level", "none")).capitalize(),
                "Risks":   risk_str,
            })
            levels.append(str(result_dict.get("support_level", "none")).lower())

    return pd.DataFrame(rows), levels


def render_matrix_table(
    df:     pd.DataFrame,
    levels: List[str],
    theme:  ThemeDict,
) -> None:
    """
    Render the analytical lens matrix as a custom-styled HTML table.

    Uses the .matrix-table and .badge-* CSS classes defined in inject_css().
    The levels list drives badge class selection and is separate from df
    so df can be exported cleanly without internal columns.
    """
    rows_html = ""
    for i, (_, row) in enumerate(df.iterrows()):
        level = levels[i] if i < len(levels) else "none"
        rows_html += f"""
        <tr>
          <td style="font-weight:600;color:{theme['text']};">{row['Lens']}</td>
          <td><span class="badge badge-{level}">{row['Support']}</span></td>
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


# ===========================================================================
# Section 10 — Panel state management
# ===========================================================================

def invalidate_panel_state(pid: str, claim_text: str) -> Dict[str, str]:
    """
    Build the namespaced session_state key map for this panel.

    If the claim text has changed since the last render, all downstream
    keys (refined query, active query, scan, prompts, matrix, pdf cache)
    are deleted so the user cannot accidentally export a report that does
    not match the current claim.

    Returns:
        A dict mapping logical names to their session_state keys,
        e.g. {"scan": "scan_main", "prompts": "prompts_main", ...}.
        Callers use this dict everywhere instead of constructing key strings
        inline, which eliminates typo-related bugs.
    """
    keys = {
        "refined_query": f"refined_query_{pid}",
        "active_query":  f"active_query_{pid}",
        "scan":          f"scan_{pid}",
        "prompts":       f"prompts_{pid}",
        "matrix":        f"lens_matrix_{pid}",
        "claim_cache":   f"claim_cache_{pid}",
        "pdf_cache":     f"pdf_cache_{pid}",
    }

    if st.session_state.get(keys["claim_cache"]) != claim_text:
        # Claim changed — purge everything derived from the old claim
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


# ===========================================================================
# Section 11 — Step rendering helpers
# ===========================================================================

def render_scan_results(snapshot: Dict[str, Any], theme: ThemeDict) -> None:
    """
    Render the three metric cards, evidence bar, summary text, and
    top-titles expander for a completed literature scan.
    """
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Records",  snapshot.get("combined_count", 0))
    m2.metric("Direct Matches", snapshot.get("direct_hits",    0))
    m3.metric("Support Level",  str(snapshot.get("support_level", "—")).title())

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
    top_titles  = ensure_list(snapshot.get("top_titles"))

    if top_records:
        with st.expander("Top Retrieved Titles"):
            for record in top_records:
                record_dict   = ensure_dict(record)
                title         = str(record_dict.get("title",  "Untitled"))
                url           = str(record_dict.get("url",    ""))
                src           = str(record_dict.get("source", "")).title()
                score         = record_dict.get("score", "")
                meta          = src + (f" · Score: {score}" if score != "" else "")

                if url:
                    st.markdown(f"- [{title}]({url})")
                else:
                    st.write(f"- {title}")

                matched_terms = ensure_list(record_dict.get("matched_terms"))
                if matched_terms:
                    st.caption(
                        f"{meta} · Matched: {', '.join(map(str, matched_terms[:4]))}"
                    )
    elif top_titles:
        with st.expander("Top Retrieved Titles"):
            for title in top_titles:
                st.write(f"- {title}")


def render_prompt_results(prompts: Dict[str, Any], theme: ThemeDict) -> None:
    """
    Render the support level banner, evidence bar, translation risk panels,
    and the four prompt expanders for a completed prompt generation step.
    """
    level         = str(prompts.get("support_level", "none")).lower()
    evidence_note = str(prompts.get("evidence_note", ""))

    # Map support levels to Streamlit alert types
    level_map = {
        "none":     "error",
        "limited":  "warning",
        "indirect": "warning",
        "moderate": "info",
        "direct":   "success",
    }
    getattr(st, level_map.get(level, "info"))(
        f"**Support: {level.title()}**\n\n{evidence_note}"
    )

    st.markdown(
        render_support_bar_html(level, theme["text"], theme["border"]),
        unsafe_allow_html=True,
    )

    # Translation risk patterns
    biases = coerce_bias_list(prompts.get("detected_biases"))
    if biases:
        st.markdown("#### Detected Translation Risk Patterns")
        for bias in biases:
            name        = bias.get("bias",        "") if isinstance(bias, dict) else str(bias)
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

    # Prompt expanders
    st.markdown("#### Evaluation Prompts")
    prompt_meta = [
        ("Master Prompt",      "master_prompt",      True,  "Primary evaluation prompt for direct LLM use."),
        ("Counter Prompt",     "counter_prompt",     False, "Challenges the validity of the design claim."),
        ("Uncertainty Mapping","uncertainty_prompt", False, "Maps unknowns and contested areas in the literature."),
        ("Redesign Prompt",    "redesign_prompt",    False, "Suggests evidence-grounded modifications."),
    ]

    for title, key, expanded, description in prompt_meta:
        with st.expander(title, expanded=expanded):
            st.caption(description)
            value = str(prompts.get(key, "") or "")
            if value:
                render_copy_button(value, theme["icon"], theme["border"])
                st.code(value, language="text")

    # Optional checklist emitted by some backend lens configs
    look_for = ensure_list(prompts.get("look_for"))
    if look_for:
        st.markdown("**Checklist for AI Response:**")
        for item in look_for:
            st.markdown(f"- {str(item).capitalize()}")


# ===========================================================================
# Section 12 — Main panel renderer
# ===========================================================================

def render_panel(
    pid:         str,
    claim_text:  str,
    domain_mode: str,
    lens_ui:     str,
    source:      str,
    max_results: int,
    bio_model:   str,
    trg_func:    str,
    app_ctx:     str,
    mech_kw:     str,
    excl_kw:     str,
    theme:       ThemeDict,
) -> None:
    """
    Render the complete four-step evaluation workflow for a single claim panel.

    Parameters:
        pid         — Panel identifier ("main", "A", or "B").  All
                      session_state keys are prefixed with this value so
                      that compare mode panels operate with fully isolated
                      state and no bleed between them.
        claim_text  — The biomimetic design claim to evaluate.
        domain_mode — Selected preset ("Fog", "EV", or "Custom").
        lens_ui     — Selected analytical lens.
        source      — Literature source ("Both", "PubMed", "OpenAlex").
        max_results — Maximum records to retrieve per source.
        bio_model … excl_kw — Custom guidance fields (empty strings when
                      Custom preset is not active).
        theme       — ThemeDict for the current colour scheme.

    Fix applied in v0.5.1 — ensure_session_defaults() guard:
        Called at the top of render_panel() so the function can be invoked
        directly (e.g. in unit tests) without depending on main() having
        initialised session_state first.

    Fix applied in v0.5.1 — q_text source:
        q_text is now read from session_state[keys["active_query"]] rather
        than from the return value of st.text_area().  When Refine Query and
        Execute Scan are triggered in the same Streamlit rerun, the widget
        return value still holds the pre-refinement text; reading from
        session_state guarantees the freshly refined query is sent.
    """
    # Guard: initialise session defaults if render_panel is called directly
    ensure_session_defaults()

    keys         = invalidate_panel_state(pid, claim_text)
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

    # ── Step 1: Refine Search Query ───────────────────────────────────────────
    st.divider()
    st.markdown("### Step 1: Refine Search Query")
    st.caption(
        "Extracts key entities from the claim and builds a Boolean query "
        "optimised for the selected literature sources."
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Refine Query", key=f"refine_btn_{pid}", use_container_width=True):
            with st.spinner("Refining..."):
                try:
                    response      = api_post("/evidence/refine-query", payload_base)
                    refined_query = extract_refined_query(response, claim_text)
                    # Write to both the named store and the active_query widget key
                    st.session_state[keys["refined_query"]] = refined_query
                    st.session_state[keys["active_query"]]  = refined_query
                    st.success("Query refined.")
                except Exception as exc:
                    st.error(str(exc))

    with c2:
        if st.button("Use Claim", key=f"use_claim_btn_{pid}", use_container_width=True):
            # Bypass refinement and use the raw claim text as the query
            st.session_state[keys["refined_query"]] = claim_text
            st.session_state[keys["active_query"]]  = claim_text

    # Seed active_query from refined_query the first time this panel renders
    if keys["active_query"] not in st.session_state:
        st.session_state[keys["active_query"]] = st.session_state.get(
            keys["refined_query"], claim_text
        )

    # Render the editable query textarea — its value lives in session_state
    st.text_area(
        "Active Query (Editable)",
        key=keys["active_query"],
        height=80,
        help="You can manually edit the active query before scanning.",
    )

    # FIX (v0.5.1): Read q_text from session_state, not from the widget's
    # return value.  When Refine Query updates session_state[active_query] and
    # Execute Scan is pressed in the same rerun, the widget return