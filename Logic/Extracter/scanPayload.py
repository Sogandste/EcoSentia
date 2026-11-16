from typing import Tuple, Dict, Any
from ..converter import safe_get, first_non_empty


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
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    return snapshot, str(query_text)
