from typing import Dict, Any
from ..converter import first_non_empty, safe_get


def extract_prompts_payload(response: Dict[str, Any]) -> Dict[str, Any]:
    prompts = first_non_empty(
        response.get("prompts"),
        safe_get(response, "data", "prompts"),
        response if "master_prompt" in response else None,
    )
    return prompts if isinstance(prompts, dict) else {}
