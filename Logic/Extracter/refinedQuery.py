from typing import Dict, Any
from ..converter import first_non_empty
from ..converter import safe_get


def extract_refined_query(response: Dict[str, Any], fallback_claim: str) -> str:
    query = first_non_empty(
        response.get("refined_query"),
        response.get("query"),
        response.get("refined"),
        safe_get(response, "data", "refined_query"),
        safe_get(response, "data", "query"),
    )
    return str(query) if query else fallback_claim
