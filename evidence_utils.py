# evidence_utils.py
from models import SnapshotModel

def classify_support_level(snapshot: SnapshotModel) -> str:
    count  = snapshot.combined_count
    direct = snapshot.direct_hits

    if count == 0:
        return "none"
    if direct >= 3:
        return "direct"
    if direct >= 1:
        return "moderate"
    if count >= 10:
        return "indirect"
    return "limited"

def build_evidence_note(snapshot: SnapshotModel, support_level: str) -> str:
    c = snapshot.combined_count
    d = snapshot.direct_hits

    messages = {
        "none": (
            "No records retrieved. The claim may use terminology not yet "
            "indexed, or the query needs revision before drawing conclusions."
        ),
        "limited": (
            f"{c} records retrieved with no close title matches. "
            "Treat this claim as speculative until targeted literature review is complete."
        ),
        "indirect": (
            f"{c} records retrieved, none directly matching the claim title tokens. "
            "Adjacent evidence exists — manual screening required to assess relevance."
        ),
        "moderate": (
            f"{c} records retrieved; {d} closely matched the claim. "
            "Partial support exists — key assumptions remain unvalidated."
        ),
        "direct": (
            f"{d} directly relevant records found (total pool: {c}). "
            "Core concept appears grounded — mechanism-level and safety gaps still require review."
        ),
    }
    return messages.get(support_level, "Evidence classification unavailable.")

def format_source_counts(source_counts: dict) -> str:
    if not source_counts:
        return "No source breakdown available."
    return " | ".join(f"{k}: {v}" for k, v in source_counts.items())