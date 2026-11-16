from typing import Dict, Any
from ..converter import first_non_empty, safe_get


def extract_lens_matrix(response: Dict[str, Any]) -> Dict[str, Any]:
    matrix = first_non_empty(
        response.get("lens_matrix"),
        response.get("matrix"),
        safe_get(response, "data", "lens_matrix"),
        safe_get(response, "results", "lens_matrix"),
    )
    return matrix if isinstance(matrix, dict) else {}
