# query_builder.py
from typing import Dict, List

STOP_TERMS = {
    "a", "an", "the", "for", "with", "and", "or", "of",
    "to", "in", "on", "by", "at", "is", "are", "was",
}

LENS_TERMS: Dict[str, List[str]] = {
    "mechanism":         ["mechanism", "pathway", "binding", "uptake"],
    "context":           ["microenvironment", "boundary conditions", "humidity", "pH"],
    "scale":             ["scaling", "transport", "diffusion", "geometry"],
    "manufacturability": ["fabrication", "synthesis", "reproducibility", "purification"],
    "safety":            ["immunogenicity", "toxicity", "clearance", "biodistribution"],
}

PRESET_TERMS: Dict[str, List[str]] = {
    "fog": ["fog harvesting", "wettability", "surface structure", "water collection",
            "biomimetic surface", "Namib beetle"],
    "ev":  ["extracellular vesicle", "exosome", "drug delivery", "nanoparticle",
            "targeted therapy", "membrane vesicle"],
}

def tokenize_claim(claim: str) -> List[str]:
    if not claim: return []
    for char in ",.;:()/":
        claim = claim.replace(char, " ")
    tokens = claim.lower().split()
    return [t for t in tokens if t not in STOP_TERMS and len(t) > 3]

def build_query(preset: str = "fog", project: str = "", claim: str = "", lens: str = "mechanism") -> str:
    base_terms = PRESET_TERMS.get(preset, [])
    claim_tokens = tokenize_claim(claim)
    extra_tokens = [t for t in claim_tokens if t not in " ".join(base_terms).lower()][:3]
    all_terms = base_terms + extra_tokens

    if not all_terms: return claim or ""

    formatted = [f'"{t}"' if " " in t else t for t in all_terms]
    return " OR ".join(formatted)

def refine_query(query: str, lens: str = "mechanism", max_terms: int = 3) -> str:
    terms = LENS_TERMS.get(lens, [])[:max_terms]
    if not terms: return query
    if any(f'"{t}"' in query or t in query for t in terms): return query
    group = "(" + " OR ".join(f'"{t}"' for t in terms) + ")"
    return f"({query}) AND {group}"

def build_refined_query(preset: str = "fog", project: str = "", claim: str = "", lens: str = "mechanism") -> str:
    base = build_query(preset=preset, project=project, claim=claim, lens=lens)
    return refine_query(base, lens=lens)