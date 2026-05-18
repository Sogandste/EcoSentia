# api.py
# FastAPI backend for the EcoSentia Evidence Layer v0.2
# Exposes four endpoints:
#   POST /evidence/refine-query     — NLP query builder
#   POST /evidence/scan             — single-lens literature scan
#   POST /evidence/prompts          — evidence-aware prompt generator
#   POST /evidence/scan-all-lenses  — full 5-lens matrix audit

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import EvidencePayload, PromptPayload, SnapshotModel
from query_builder import build_refined_query
from literature import run_evidence_scan
from prompt_builder import build_evidence_aware_prompts
from bias_checker import detect_biases
from evidence_utils import classify_support_level

app = FastAPI(title="EcoSentia Evidence API", version="0.2")

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow all origins during development.
# Restrict to your Streamlit Cloud domain in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 1 — Refine search query
# Input:  EvidencePayload (preset, project, claim, lens)
# Output: {"ok": true, "refined_query": "<boolean query string>"}
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/evidence/refine-query")
def refine_evidence_query(payload: EvidencePayload):
    """
    Extract key entities from the design claim and return a Boolean
    search query optimized for PubMed and OpenAlex syntax.
    """
    try:
        refined = build_refined_query(
            preset=payload.preset,
            project=payload.project,
            claim=payload.claim,
            lens=payload.lens,
        )
        return {"ok": True, "refined_query": refined}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 2 — Run evidence scan
# Input:  EvidencePayload (+ optional query_text override)
# Output: {"ok": true, "query_text": "...", "snapshot": {...}}
#
# snapshot fields expected by the frontend:
#   combined_count : int   — total records retrieved
#   direct_hits    : int   — records with high semantic overlap
#   support_level  : str   — one of: none/limited/indirect/moderate/direct
#   summary        : str   — human-readable evidence summary
#   top_titles     : list  — top retrieved article titles (optional)
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/evidence/scan")
def run_scan(payload: EvidencePayload):
    """
    Retrieve abstracts from PubMed and/or OpenAlex and compute
    semantic overlap with the original design claim.
    Falls back to auto-generated query if query_text is not provided.
    """
    try:
        # Use provided query or auto-generate from claim
        query = payload.query_text or build_refined_query(
            preset=payload.preset,
            project=payload.project,
            claim=payload.claim,
            lens=payload.lens,
        )

        snapshot_raw = run_evidence_scan(
            query=query,
            source=payload.source,
            max_results=payload.max_results,
            claim_text=payload.claim,
        )

        # Validate snapshot has required fields before returning
        # direct_hits defaults to 0 if the literature module omits it
        snapshot_raw.setdefault("direct_hits", 0)
        snapshot_raw.setdefault("combined_count", 0)
        snapshot_raw.setdefault("support_level", "none")
        snapshot_raw.setdefault("summary", "No summary available.")
        snapshot_raw.setdefault("top_titles", [])

        return {
            "ok":         True,
            "query_text": query,
            "snapshot":   snapshot_raw,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3 — Generate evidence-aware prompts
# Input:  PromptPayload (preset, lens, claim, query_text, snapshot)
# Output: {"ok": true, "prompts": {...}}
#
# prompts fields expected by the frontend:
#   support_level    : str
#   evidence_note    : str
#   detected_biases  : list of {bias: str, explanation: str}
#   master_prompt    : str
#   counter_prompt   : str
#   uncertainty_prompt: str
#   redesign_prompt  : str
#   look_for         : list of str
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/evidence/prompts")
def generate_prompts(payload: PromptPayload):
    """
    Build four structured LLM prompts grounded in the retrieved
    evidence snapshot and the selected evaluation lens.
    """
    try:
        result = build_evidence_aware_prompts(
            preset=payload.preset,
            lens=payload.lens,
            claim=payload.claim,
            query_text=payload.query_text,
            snapshot=payload.snapshot,
        )
        return {"ok": True, "prompts": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 4 — Full multi-lens audit
# Input:  EvidencePayload (preset, project, claim, source, max_results)
# Output: {"ok": true, "lens_matrix": {lens: {support_level, detected_biases, query_used}}}
#
# Runs 5 independent scans (one per lens) and returns a unified matrix.
# Per-lens errors are caught individually so one failure does not abort
# the entire matrix — the failed lens gets an {"error": "..."} entry.
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/evidence/scan-all-lenses")
def scan_all_lenses(payload: EvidencePayload):
    """
    Execute evidence scans across all five analytical lenses and
    return a structured risk matrix.
    Each lens is scanned independently; partial failures are captured
    per-lens without aborting the full audit.
    """
    lenses = ["mechanism", "context", "scale", "manufacturability", "safety"]
    matrix = {}

    for lens in lenses:
        try:
            # Build a lens-specific query for each pass
            refined = build_refined_query(
                preset=payload.preset,
                project=payload.project,
                claim=payload.claim,
                lens=lens,
            )

            # Limit to 3 results per lens to keep latency acceptable
            snapshot_raw = run_evidence_scan(
                query=refined,
                source=payload.source,
                max_results=3,
                claim_text=payload.claim,
            )

            # Ensure required fields are present before classification
            snapshot_raw.setdefault("direct_hits", 0)
            snapshot_raw.setdefault("combined_count", 0)
            snapshot_raw.setdefault("support_level", "none")

            # Validate snapshot shape with Pydantic model
            snapshot = SnapshotModel(**snapshot_raw)

            # Classify overall support level for this lens
            level = classify_support_level(snapshot)

            # Detect translation risk patterns from the raw claim text
            biases = detect_biases(payload.claim)

            # detected_biases stored as list of dicts {bias, explanation}
            # so the frontend can render both label and detail
            matrix[lens] = {
                "support_level":   level,
                "detected_biases": biases,
                "query_used":      refined,
            }

        except Exception as e:
            # Capture per-lens failure without aborting the full matrix
            matrix[lens] = {"error": str(e)}

    return {"ok": True, "lens_matrix": matrix}