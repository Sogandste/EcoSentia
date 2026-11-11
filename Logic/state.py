import streamlit as st
from typing import Dict, Any
from datetime import datetime
import os

panelKeys = {
    "refined_query": "refined_query_{pid}",
    "active_query": "active_query_{pid}",
    "scan": "scan_{pid}",
    "prompts": "prompts_{pid}",
    "matrix": "lens_matrix_{pid}",
    "claim_cache": "claim_cache_{pid}",
}


def invalidate_panel_state(pid: str, claim_text: str, state: st.session_state) -> Dict[str, str]:
    if state.get(panelKeys["claim_cache"]) != claim_text:
        state[panelKeys["claim_cache"]] = claim_text
        for k, v in panelKeys.items():
            if k != "claim_cache":
                state.pop(panelKeys[k], None)
    return {name: template.format(pid=pid) for name, template in panelKeys.items()}



def get_panel_state(pid: str, state: st.session_state) -> Dict[str, Any]:
    """
    Collect all available outputs for a given panel into a structured report object.
    This export is intended for reproducibility and case documentation.
    """

    formattedKeys = {name: template.format(pid=pid) for name, template in panelKeys.items()}
    scan_state = state.get(formattedKeys["scan"]) if isinstance(state.get(formattedKeys["scan"]), dict) else {}
    prompts = state.get(formattedKeys["prompts"]) if isinstance(state.get(formattedKeys["prompts"]), dict) else {}
    matrix = state.get(formattedKeys["matrix"]) if isinstance(state.get(formattedKeys["matrix"]), dict) else {}

    return {
        "app": os.getenv("APP_TITLE"),
        "version": os.getenv("APP_VERSION"),
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "panel_id": pid,
        "claim": state.get(formattedKeys["claim_cache"], ""),
        "active_query": state.get(formattedKeys["active_query"], ""),
        "refined_query": state.get(formattedKeys["refined_query"], ""),
        "scan": scan_state,
        "prompts": prompts,
        "lens_matrix": matrix,
    }

