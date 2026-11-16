
from typing import Dict, Any


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
