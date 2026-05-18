# domain_config.py
"""
Centralized domain configuration.
All domain-specific terms, lenses, and checklist items live here.
"""

from typing import Dict, List, FrozenSet

FOG_ANCHORS: Dict[str, List[str]] = {
    "bio_model": [
        "Namib desert beetle", "desert beetle", "Stenocara",
    ],
    "function": [
        "fog harvesting", "water harvesting", "water collection",
        "dew collection", "atmospheric water harvesting",
    ],
    "mechanism": [
        "wettability", "hydrophilic", "hydrophobic",
        "wettability gradient", "condensation",
        "droplet transport", "droplet nucleation", "droplet coalescence",
    ],
    "design": [
        "biomimetic", "bioinspired", "coating",
        "microstructure", "patterned surface", "textured surface",
    ],
    "negative": [
        "mast cell", "interferon", "IFN", "antiviral", "vaccinal",
        "monoclonal antibody", "ferroptosis", "lung disease",
        "cloud removal", "remote sensing", "image restoration",
        "immunity", "immune", "cortical actin",
    ],
}

EV_ANCHORS: Dict[str, List[str]] = {
    "bio_model": [
        "extracellular vesicle", "exosome", "cell-derived vesicle",
    ],
    "function": [
        "drug delivery", "targeted delivery", "immune modulation", "cargo delivery",
    ],
    "mechanism": [
        "cellular uptake", "membrane fusion", "targeting",
        "biodistribution", "immune evasion", "biocompatibility",
    ],
    "design": [
        "biomimetic", "bioinspired", "nanomedicine", "nanoparticle",
        "vesicle-inspired", "membrane-coated nanoparticle",
    ],
    "negative": [
        "cloud removal", "fog harvesting", "water collection",
        "anti-fog coating", "surface wettability for condensation", "remote sensing",
    ],
}

KNOWN_PHRASES: FrozenSet[str] = frozenset([
    "fog harvesting", "water harvesting", "water collection",
    "namib desert beetle", "extracellular vesicle", "drug delivery",
    "surface wettability", "wettability gradient", "droplet transport",
    "bioinspired surface", "biomimetic coating", "reversible adhesion",
    "wet biomedical", "drag reduction", "anti-fouling", "self-cleaning",
    "shark skin", "lotus effect", "gecko adhesion", "mussel adhesive",
    "membrane-coated", "targeted delivery", "immune evasion",
    "nanoparticle", "cellular uptake", "membrane fusion",
])

LENS_TERMS: Dict[str, List[str]] = {
    "mechanism": ["mechanism", "functional", "causal", "biophysical", "surface energy"],
    "context": ["environment", "ecological", "operating condition", "boundary condition", "humidity"],
    "scale": ["scale", "scaling", "micro", "nano", "feature size", "dimensional"],
    "manufacturability": ["fabrication", "manufacturing", "coating process", "scalable", "lithography", "production"],
    "safety": ["safety", "toxicity", "biocompatibility", "risk", "regulatory", "immunogenicity"],
}

LENS_CHECKLIST: Dict[str, List[str]] = {
    "mechanism": [
        "Causal pathway stated explicitly",
        "Analogy goes beyond morphology",
        "Experimental evidence cited",
    ],
    "context": [
        "Source environment clearly stated",
        "Target environment conditions specified",
        "Transfer assumptions acknowledged",
    ],
    "scale": [
        "Feature dimensions quantified",
        "Scale-dependent behavior acknowledged",
        "Fabrication resolution discussed",
    ],
    "manufacturability": [
        "Fabrication method identified",
        "Cost and scalability addressed",
        "Material compatibility stated",
    ],
    "safety": [
        "Biocompatibility data referenced",
        "Degradation or clearance discussed",
        "Regulatory pathway acknowledged",
    ],
}

ALL_LENSES: List[str] = list(LENS_TERMS.keys())


def get_anchors(preset: str) -> Dict[str, List[str]]:
    p = (preset or "").strip().lower()
    if p == "fog":
        return FOG_ANCHORS
    if p == "ev":
        return EV_ANCHORS
    return {"bio_model": [], "function": [], "mechanism": [], "design": [], "negative": []}


def get_positive_terms(preset: str) -> List[str]:
    a = get_anchors(preset)
    return a["bio_model"] + a["function"] + a["mechanism"] + a["design"]


def get_negative_terms(preset: str) -> List[str]:
    return get_anchors(preset).get("negative", [])