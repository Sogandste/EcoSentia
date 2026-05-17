# prompt_builder.py
from models import SnapshotModel
from evidence_utils import classify_support_level, build_evidence_note, format_source_counts
from bias_checker import detect_biases

LENS_FOCUS: dict = {
    "mechanism":         "causal validity, mechanism plausibility, and the risk of superficial analogy",
    "context":           "environmental or microenvironmental dependencies and boundary conditions",
    "scale":             "transferability across size regimes, transport physics, and geometry",
    "manufacturability": "synthesis feasibility, purification, reproducibility, and durability",
    "safety":            "immunogenicity, toxicity, clearance, biodistribution, and off-target effects",
}

LENS_CHECKLIST: dict = {
    "mechanism":         ["causal pathway stated explicitly", "analogy goes beyond morphology", "experimental evidence cited"],
    "context":           ["boundary conditions defined", "microenvironment specified", "operational range stated"],
    "scale":             ["size regime addressed", "transport or diffusion limits discussed", "geometry dependence noted"],
    "manufacturability": ["fabrication route described", "purification yield realistic", "batch reproducibility addressed"],
    "safety":            ["immunogenicity profile discussed", "clearance mechanism identified", "off-target risk assessed"],
}

DOMAIN_LABEL: dict = {
    "fog": "bioinspired fog-harvesting surface design",
    "ev":  "extracellular vesicle-inspired nanomedicine",
}

def build_evidence_aware_prompts(preset: str, lens: str, claim: str, query_text: str, snapshot: SnapshotModel) -> dict:
    support_level   = classify_support_level(snapshot)
    evidence_note   = build_evidence_note(snapshot, support_level)
    source_summary  = format_source_counts(snapshot.source_counts)
    detected_biases = detect_biases(claim)
    domain          = DOMAIN_LABEL.get(preset, "biomimetic design")
    focus           = LENS_FOCUS.get(lens, "scientific plausibility")
    checklist       = LENS_CHECKLIST.get(lens, [])

    if detected_biases:
        bias_lines = "\n".join(f"  - {b['bias']}: {b['explanation']}" for b in detected_biases)
        bias_block = f"\nDetected translation risk patterns (rule-based flags — verify manually):\n{bias_lines}"
    else:
        bias_block = ""

    master_prompt = f"""
You are critically evaluating an AI-generated design concept in {domain}.

== CLAIM ==
{claim}

== EVIDENCE CONTEXT ==
Query used       : {query_text}
Total records    : {snapshot.combined_count}
Direct matches   : {snapshot.direct_hits}
Sources          : {source_summary}
Support level    : {support_level}
Note             : {evidence_note}{bias_block}

== TASK ==
Evaluate this claim under the lens of {focus}.

Structure your response as:
1. What appears grounded based on available evidence
2. What requires experimental validation before it can be stated as fact
3. Where the analogy may be superficial rather than mechanistic
4. One concrete gap that would change your assessment if filled

Do not treat record counts as quality signals.
If evidence is limited, say so explicitly. Avoid overconfidence.
""".strip()

    counter_prompt = f"""
Critique your previous evaluation of this biomimetic concept.

Lens: {lens}
Evidence pool: {snapshot.combined_count} records ({snapshot.direct_hits} direct matches)

Find specifically:
- Assumptions you accepted without evidence
- Contexts where the concept would fail
- Cases where the evidence pool is too small to support your conclusion
- The single most likely point of oversimplification in the original claim

State what you were too confident about and why.
""".strip()

    uncertainty_prompt = f"""
List the top unresolved uncertainties for this claim.

Claim : {claim}
Lens  : {lens}

For each uncertainty:
- State what is unknown
- Classify the next step:
    [ literature review | simulation/modeling | in vitro | in vivo | expert judgment ]
- Estimate resolution timeline:
    [ near-term < 1 yr | medium-term 1–3 yr | long-term > 3 yr ]

Keep answers concrete. Avoid generic scientific caveats.
""".strip()

    redesign_prompt = f"""
Rewrite this biomimetic design claim as a scientifically careful hypothesis.

Original claim:
{claim}

Requirements:
- Preserve the core design idea
- Replace absolute statements with conditional ones where evidence is absent
- Separate what is grounded from what is speculative
- Reflect the {lens} lens
- Use language appropriate for a methods section or grant proposal

Output format:
  Revised claim         : [one sentence]
  Grounded components   : [bullet list]
  Speculative components: [bullet list]
  Suggested validation  : [one sentence]
""".strip()

    return {
        "support_level":      support_level,
        "evidence_note":      evidence_note,
        "detected_biases":    detected_biases,
        "look_for":           checklist,
        "source_summary":     source_summary,
        "master_prompt":      master_prompt,
        "counter_prompt":     counter_prompt,
        "uncertainty_prompt": uncertainty_prompt,
        "redesign_prompt":    redesign_prompt,
    }