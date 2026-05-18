# bias_checker.py
"""
Rule-based bias and risk pattern detection for biomimetic claims.
Uses flexible word-boundary matching to avoid exact-string brittleness.
"""

import re
from typing import List, Dict, Optional
from logger import get_logger

log = get_logger(__name__)

def _contains_any(text: str, patterns: List[str]) -> bool:
    for p in patterns:
        if len(p) <= 5:
            if re.search(rf"\b{re.escape(p)}\b", text):
                return True
        else:
            if p in text:
                return True
    return False

BIAS_RULES = [
    {
        "bias": "Morphology Overreach",
        "require_any": ["inspired", "bio-inspired", "bioinspired", "mimetic", "biomimetic"],
        "require_any_2": ["surface", "structure", "pattern", "morphology", "shape"],
        "require_none": ["mechanism", "functional", "causal", "pathway", "biophysical"],
        "explanation": "Claim may rely on formal resemblance without validated functional transfer.",
    },
    {
        "bias": "Mechanism Gap",
        "require_any": ["bioinspired", "biomimetic", "inspired", "bio-inspired", "mimetic"],
        "require_none": ["mechanism", "pathway", "causal", "functional principle", "biophysical"],
        "explanation": "Biological inspiration is stated but causal mechanism is not specified.",
    },
    {
        "bias": "Context Transfer Risk",
        "require_any": ["desert", "marine", "deep sea", "arctic", "clinical", "in vivo", "tropical"],
        "require_none": [],
        "explanation": "Source biology and target application may operate under very different constraints.",
    },
    {
        "bias": "Scale Translation Risk",
        "require_any": ["nano", "micro", "nanometer", "micrometer", "nm scale", "sub-micron"],
        "require_none": [],
        "explanation": "Performance may not transfer across scales without explicit validation.",
    },
    {
        "bias": "Safety Blindspot",
        "require_any": ["drug delivery", "nanoparticle", "implant", "biomedical", "clinical", "in vivo", "therapeutic"],
        "require_none": ["safety", "toxicity", "biocompatibility", "regulatory", "clearance"],
        "explanation": "Safety, toxicity, or regulatory constraints may be under-specified.",
    },
    {
        "bias": "Oversimplification Risk",
        "require_any": ["simple", "straightforward", "easily", "trivial", "just", "merely"],
        "require_any_2": ["fabricat", "manufactur", "produc", "scal"],
        "require_none": [],
        "explanation": "Claim may underestimate manufacturing complexity.",
    },
]

def detect_biases(claim: str, lens: Optional[str] = None) -> List[Dict[str, str]]:
    text = (claim or "").lower()
    if not text:
        return [{"bias": "Empty Claim", "explanation": "No claim text provided for analysis."}]

    found = []

    for rule in BIAS_RULES:
        req_any = rule.get("require_any", [])
        req_any_2 = rule.get("require_any_2", [])
        req_none = rule.get("require_none", [])

        pass_any = _contains_any(text, req_any) if req_any else True
        pass_any_2 = _contains_any(text, req_any_2) if req_any_2 else True
        pass_none = not _contains_any(text, req_none) if req_none else True

        if pass_any and pass_any_2 and pass_none and (req_any or req_any_2):
            found.append({
                "bias": rule["bias"],
                "explanation": rule["explanation"],
            })

    if lens:
        lens_l = lens.lower()
        if lens_l == "safety" and not _contains_any(text, ["safety", "toxic", "biocompat", "risk"]):
            found.append({
                "bias": "Safety Lens Gap",
                "explanation": "Safety lens is active but claim does not reference safety-related concepts.",
            })
        if lens_l == "manufacturability" and not _contains_any(text, ["fabricat", "manufactur", "produc", "cost"]):
            found.append({
                "bias": "Manufacturability Lens Gap",
                "explanation": "Manufacturability lens is active but claim lacks production-related language.",
            })

    if not found:
        found.append({
            "bias": "No Strong Pattern Detected",
            "explanation": "No obvious translation-risk pattern identified. Manual review still recommended.",
        })

    log.debug(f"Bias detection: {len(found)} pattern(s) identified.")
    return found