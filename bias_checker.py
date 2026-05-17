# bias_checker.py
from typing import List, Dict

BIAS_RULES: List[Dict] = [
    {
        "name": "Morphology Bias",
        "triggers":    ["structure", "shape", "geometry", "surface", "pattern",
                        "texture", "topology", "inspired by", "mimics"],
        "absence_of":  ["mechanism", "pathway", "interaction", "binding",
                        "force", "adhesion", "capillary", "wettability"],
        "explanation": (
            "Claim describes structural similarity without addressing the "
            "underlying mechanism. Morphology alone is rarely sufficient "
            "for functional transfer across biological and engineering contexts."
        ),
    },
    {
        "name": "Scale Mismatch",
        "triggers":    ["nano", "micro", "macro", "surface area", "roughness",
                        "hierarchical", "porous", "pore size"],
        "absence_of":  ["transport", "diffusion", "reynolds", "flow",
                        "thermodynamic", "capillary number", "knudsen"],
        "explanation": (
            "Claim references a scale-dependent phenomenon without addressing "
            "whether the governing physics transfers at the target scale. "
            "Properties valid at one scale often break down at another."
        ),
    },
    {
        "name": "Context Collapse",
        "triggers":    ["in vivo", "biological", "living", "organism",
                        "cell", "tissue", "physiological"],
        "absence_of":  ["temperature", "ph", "humidity", "pressure",
                        "buffer", "ionic", "environment", "conditions"],
        "explanation": (
            "Claim applies a biological concept to an engineered context "
            "without specifying the environmental boundary conditions under "
            "which the analogy holds. Biological functions are context-dependent."
        ),
    },
    {
        "name": "Manufacturability Gap",
        "triggers":    ["design", "fabricate", "produce", "create", "build",
                        "engineer", "construct", "synthesise", "synthesize"],
        "absence_of":  ["yield", "reproducibility", "cost", "scalable",
                        "purification", "batch", "protocol", "process"],
        "explanation": (
            "Claim describes a design concept without addressing whether it "
            "can be reliably produced at relevant scale. Many biomimetic "
            "designs are conceptually valid but practically unfeasible."
        ),
    },
    {
        "name": "Safety Omission",
        "triggers":    ["drug delivery", "therapeutic", "in vivo", "patient",
                        "clinical", "systemic", "inject", "implant"],
        "absence_of":  ["immunogenicity", "toxicity", "clearance",
                        "off-target", "biodistribution", "safety"],
        "explanation": (
            "Claim describes a biomedical application without addressing "
            "safety-critical properties. For in vivo contexts, immunogenicity, "
            "clearance, and off-target effects are not optional considerations."
        ),
    },
]

def detect_biases(claim: str) -> List[Dict]:
    if not claim:
        return []

    claim_lower = claim.lower()
    detected = []

    for rule in BIAS_RULES:
        has_trigger     = any(t in claim_lower for t in rule["triggers"])
        missing_anchor  = not any(a in claim_lower for a in rule["absence_of"])

        if has_trigger and missing_anchor:
            detected.append({
                "bias":        rule["name"],
                "explanation": rule["explanation"],
            })

    return detected