# prompt_builder.py
"""
Generates evidence-aware prompts for LLM interrogation of biomimetic claims.
"""

from typing import Dict, Any
from bias_checker import detect_biases
from domain_config import LENS_CHECKLIST
from logger import get_logger

log = get_logger(__name__)

def _format_evidence_note(snap: Dict[str, Any]) -> str:
    support = snap.get("support_level", "none")
    combined = snap.get("combined_count", 0)
    direct_hits = snap.get("direct_hits", 0)
    summary = snap.get("summary", "")
    return (
        f"Support level: {support}. "
        f"Records: {combined}. Direct hits: {direct_hits}. "
        f"Summary: {summary}"
    )

def _build_master(claim: str, lens: str, query_text: str, snap: Dict[str, Any]) -> str:
    support = snap.get("support_level", "none")
    combined = snap.get("combined_count", 0)
    direct_hits = snap.get("direct_hits", 0)
    summary = snap.get("summary", "")

    return (
        f"You are evaluating a biomimetic design claim through the **{lens.title()}** lens.\n\n"
        f"## Claim\n{claim}\n\n"
        f"## Query Used\n{query_text}\n\n"
        f"## Evidence Snapshot\n"
        f"- Support level: {support}\n"
        f"- Combined records: {combined}\n"
        f"- Direct hits: {direct_hits}\n"
        f"- Summary: {summary}\n\n"
        f"## Your Task\n"
        f"1. Assess whether the claim is scientifically grounded given available evidence.\n"
        f"2. State the likely mechanism explicitly.\n"
        f"3. Distinguish biological analogy from validated functional transfer.\n"
        f"4. Identify what evidence directly supports the claim and what remains uncertain.\n"
        f"5. **Verdict:** Grounded / Partial / Speculative.\n"
        f"6. Confidence estimate (Low / Medium / High) with justification."
    )

def _build_counter(claim: str, lens: str, evidence_note: str) -> str:
    return (
        f"Challenge this biomimetic claim critically.\n\n"
        f"## Claim\n{claim}\n\n"
        f"## Lens: {lens.title()}\n"
        f"## Evidence: {evidence_note}\n\n"
        f"## Critical Questions\n"
        f"- What assumptions are untested?\n"
        f"- Where might the biological analogy be misleading?\n"
        f"- What contextual or scale mismatches could break the transfer?\n"
        f"- What experiments would be required before confidence is justified?\n"
        f"- What alternative explanations exist for the claimed performance?"
    )

def _build_uncertainty(claim: str, evidence_note: str) -> str:
    return (
        f"Map the uncertainties in this claim.\n\n"
        f"## Claim\n{claim}\n\n"
        f"## Evidence\n{evidence_note}\n\n"
        f"## Return Structure\n"
        f"1. **Known** - What is established from retrieved literature.\n"
        f"2. **Suggested** - What is only indirectly implied.\n"
        f"3. **Unknown** - What remains unsupported or speculative.\n"
        f"4. **Next Steps** - Priority list of evidence to seek.\n"
        f"5. **Risk Assessment** - What could go wrong if unknowns are ignored."
    )

def _build_redesign(claim: str, evidence_note: str) -> str:
    return (
        f"Redesign this claim into a more evidence-aware version.\n\n"
        f"## Original Claim\n{claim}\n\n"
        f"## Evidence Context\n{evidence_note}\n\n"
        f"## Instructions\n"
        f"- Preserve the useful biomimetic idea.\n"
        f"- Remove overclaiming or unsupported extrapolations.\n"
        f"- Narrow the mechanism if needed.\n"
        f"- Specify conditions, scale, or validation steps.\n"
        f"- State which aspects require further investigation.\n\n"
        f"## Output\n"
        f"- **Revised Claim** (1-3 sentences)\n"
        f"- **Rationale** (why changes were made)\n"
        f"- **Remaining Gaps** (what still needs validation)"
    )

def build_evidence_aware_prompts(
    preset: str,
    lens: str,
    claim: str,
    query_text: str,
    snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    snap = snapshot or {}
    lens_norm = (lens or "mechanism").lower()
    evidence_note = _format_evidence_note(snap)
    biases = detect_biases(claim, lens=lens_norm)
    look_for = LENS_CHECKLIST.get(lens_norm, LENS_CHECKLIST["mechanism"])

    result = {
        "support_level": snap.get("support_level", "none"),
        "evidence_note": evidence_note,
        "detected_biases": biases,
        "master_prompt": _build_master(claim, lens, query_text, snap),
        "counter_prompt": _build_counter(claim, lens, evidence_note),
        "uncertainty_prompt": _build_uncertainty(claim, evidence_note),
        "redesign_prompt": _build_redesign(claim, evidence_note),
        "look_for": look_for,
    }

    log.info(f"Built prompts for lens={lens_norm}, support={snap.get('support_level','none')}")
    return result