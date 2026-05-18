# query_builder.py
"""
Builds refined Boolean queries from domain anchors, claim analysis, and user fields.
"""

import re
from typing import List, Dict
from domain_config import FOG_ANCHORS, EV_ANCHORS, LENS_TERMS, KNOWN_PHRASES, get_anchors
from logger import get_logger

log = get_logger(__name__)

_STOP_WORDS = frozenset({
    "a", "an", "the", "for", "of", "and", "or", "to", "by", "with",
    "in", "on", "from", "inspired", "based", "structure", "system",
    "device", "application", "improved", "better", "passive", "using",
    "that", "this", "its", "their", "which", "are", "was", "been",
    "can", "may", "could", "would", "should", "has", "have", "had",
})

def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())

def _split_csv(text: str) -> List[str]:
    if not text:
        return []
    return [p.strip() for p in re.split(r"[,\n;]+", text) if p.strip()]

def _extract_claim_terms(claim: str) -> List[str]:
    claim = _clean_text(claim)
    if not claim:
        return []

    lowered = claim.lower()
    phrases = [p for p in KNOWN_PHRASES if p in lowered]
    
    tokens = re.findall(r"[A-Za-z0-9\-]+", lowered)
    tokens = [t for t in tokens if len(t) > 2 and t not in _STOP_WORDS]

    seen = set()
    out = []
    for x in phrases + tokens:
        if x not in seen:
            out.append(x)
            seen.add(x)

    return out[:14]

def _quote(term: str) -> str:
    term = term.strip()
    return f'"{term}"' if " " in term else term

def _or_block(terms: List[str], limit: int = 8) -> str:
    terms = [_quote(t) for t in terms if t][:limit]
    if not terms:
        return ""
    if len(terms) == 1:
        return terms[0]
    return "(" + " OR ".join(terms) + ")"

def build_refined_query(
    preset: str,
    project: str,
    claim: str,
    lens: str,
    domain_mode: str = "Fog",
    biological_model: str = "",
    target_function: str = "",
    application_context: str = "",
    mechanism_keywords: str = "",
    exclude_terms: str = "",
) -> str:
    
    mode = (domain_mode or preset or "fog").strip().lower()
    lens_norm = (lens or "mechanism").strip().lower()
    claim_terms = _extract_claim_terms(claim)
    l_terms = LENS_TERMS.get(lens_norm, [])

    bio = _split_csv(biological_model)
    func = _split_csv(target_function)
    ctx = _split_csv(application_context)
    mech = _split_csv(mechanism_keywords)
    excl = _split_csv(exclude_terms)

    anchors = get_anchors(mode)

    if mode in ("fog", "ev"):
        blocks = [
            _or_block(anchors["bio_model"] + bio, limit=6),
            _or_block(anchors["function"] + func, limit=6),
            _or_block(anchors["mechanism"] + mech + l_terms[:3], limit=8),
            _or_block(anchors["design"] + ctx, limit=6),
        ]
        neg = anchors["negative"] + excl
    else:
        blocks = [
            _or_block(bio + claim_terms[:3], limit=6),
            _or_block(func + claim_terms[2:6], limit=6),
            _or_block(mech + l_terms + claim_terms[5:9], limit=8),
            _or_block(ctx + claim_terms[8:12], limit=6),
        ]
        neg = excl

    blocks = [b for b in blocks if b]
    if not blocks:
        blocks = [_or_block(claim_terms[:8])]

    query = " AND ".join(blocks)

    if neg:
        neg_block = _or_block(neg, limit=12)
        if neg_block:
            query = f"{query} NOT {neg_block}"

    log.debug(f"Query generated: {query[:120]}...")
    return _clean_text(query)