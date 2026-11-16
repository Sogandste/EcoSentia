import streamlit as st
from typing import cast, Dict, Any, List
from .session import get_http_session
import os
import requests
from UI.Model.History import HistoryEntry
from datetime import datetime
from envVariables import API_BASE, HEALTH_TIMEOUT, HTTP_TIMEOUT


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
    except Exception as e:
        message = f"API Not Reachable · {API_BASE} reason: {e}"

    st.session_state["api_health"] = message
    return message


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