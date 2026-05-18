# api.py
<<<<<<< HEAD
"""
EcoSentia Evidence API — FastAPI backend.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any
=======
# FastAPI backend for the EcoSentia Evidence Layer v0.2
# Exposes four endpoints:
#   POST /evidence/refine-query     — NLP query builder
#   POST /evidence/scan             — single-lens literature scan
#   POST /evidence/prompts          — evidence-aware prompt generator
#   POST /evidence/scan-all-lenses  — full 5-lens matrix audit
>>>>>>> 49a4c8253654ebfc32bf4cfdbb214522ba140ad0

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import EvidencePayload, PromptPayload, SnapshotModel
from query_builder import build_refined_query
from literature import run_evidence_scan
from prompt_builder import build_evidence_aware_prompts
from bias_checker import detect_biases
<<<<<<< HEAD
from domain_config import ALL_LENSES
from logger import get_logger

log = get_logger(__name__)

app = FastAPI(title="EcoSentia Evidence API", version="0.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for parallel lens scanning
_executor = ThreadPoolExecutor(max_workers=3)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_mode(payload: EvidencePayload) -> str:
    return (payload.domain_mode or payload.preset or "fog").strip().lower()


def _build_query_from_payload(payload: EvidencePayload, lens_override: str = None) -> str:
    return build_refined_query(
        preset=payload.preset,
        project=payload.project,
        claim=payload.claim,
        lens=lens_override or payload.lens,
        domain_mode=_resolve_mode(payload),
        biological_model=payload.biological_model or "",
        target_function=payload.target_function or "",
        application_context=payload.application_context or "",
        mechanism_keywords=payload.mechanism_keywords or "",
        exclude_terms=payload.exclude_terms or "",
    )


def _scan_single_lens(payload: EvidencePayload, lens: str, mode: str) -> Dict[str, Any]:
    """Scan a single lens — used for parallel execution."""
    try:
        refined = _build_query_from_payload(payload, lens_override=lens)
        snapshot_raw = run_evidence_scan(
            query=refined,
            source=payload.source,
            max_results=3,
            claim_text=payload.claim,
            preset=mode,
            lens=lens,
            exclude_terms=payload.exclude_terms or "",
        )
        biases = detect_biases(payload.claim, lens=lens)
        return {
            "support_level": snapshot_raw.get("support_level", "none"),
            "detected_biases": biases,
            "query_used": refined,
        }
    except Exception as e:
        log.error(f"Lens scan error [{lens}]: {e}")
        return {"error": str(e), "support_level": "none", "detected_biases": [], "query_used": ""}


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"ok": True, "service": "EcoSentia Evidence API", "version": "0.3"}
=======
from evidence_utils import classify_support_level
>>>>>>> 49a4c8253654ebfc32bf4cfdbb214522ba140ad0


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
<<<<<<< HEAD
def refine_query(payload: EvidencePayload):
=======
def refine_evidence_query(payload: EvidencePayload):
    """
    Extract key entities from the design claim and return a Boolean
    search query optimized for PubMed and OpenAlex syntax.
    """
>>>>>>> 49a4c8253654ebfc32bf4cfdbb214522ba140ad0
    try:
        refined = _build_query_from_payload(payload)
        log.info(f"Query refined: {refined[:80]}...")
        return {"ok": True, "refined_query": refined}
    except Exception as e:
        log.error(f"refine-query error: {e}")
        raise HTTPException(status_code=500, detail={"stage": "refine-query", "message": str(e)})



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
<<<<<<< HEAD
def scan(payload: EvidencePayload):
    try:
        query = payload.query_text or _build_query_from_payload(payload)
        mode = _resolve_mode(payload)
=======
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
>>>>>>> 49a4c8253654ebfc32bf4cfdbb214522ba140ad0

        snapshot_raw = run_evidence_scan(
            query=query,
            source=payload.source,
            max_results=payload.max_results,
            claim_text=payload.claim,
            preset=mode,
            lens=payload.lens,
            exclude_terms=payload.exclude_terms or "",
        )

<<<<<<< HEAD
        snapshot = SnapshotModel(**snapshot_raw)
        log.info(f"Scan complete: {snapshot.combined_count} records, level={snapshot.support_level}")

        return {
            "ok": True,
            "query_text": query,
            "snapshot": snapshot.model_dump(),
=======
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
>>>>>>> 49a4c8253654ebfc32bf4cfdbb214522ba140ad0
        }
    except Exception as e:
        log.error(f"scan error: {e}")
        raise HTTPException(status_code=500, detail={"stage": "scan", "message": str(e)})



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
<<<<<<< HEAD
def prompts(payload: PromptPayload):
=======
def generate_prompts(payload: PromptPayload):
    """
    Build four structured LLM prompts grounded in the retrieved
    evidence snapshot and the selected evaluation lens.
    """
>>>>>>> 49a4c8253654ebfc32bf4cfdbb214522ba140ad0
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
        log.error(f"prompts error: {e}")
        raise HTTPException(status_code=500, detail={"stage": "prompts", "message": str(e)})



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
<<<<<<< HEAD
async def scan_all_lenses(payload: EvidencePayload):
    """
    Scan all analytical lenses. Uses thread pool for partial parallelism.
    Includes per-lens timeout protection.
    """
    mode = _resolve_mode(payload)
    matrix: Dict[str, Any] = {}
    loop = asyncio.get_event_loop()
=======
def scan_all_lenses(payload: EvidencePayload):
    """
    Execute evidence scans across all five analytical lenses and
    return a structured risk matrix.
    Each lens is scanned independently; partial failures are captured
    per-lens without aborting the full audit.
    """
    lenses = ["mechanism", "context", "scale", "manufacturability", "safety"]
    matrix = {}
>>>>>>> 49a4c8253654ebfc32bf4cfdbb214522ba140ad0

    log.info(f"Starting multi-lens scan for claim[:50]='{payload.claim[:50]}'")

    # Run lens scans with concurrency (limited to 3 parallel to respect rate limits)
    futures = {
        lens: loop.run_in_executor(_executor, _scan_single_lens, payload, lens, mode)
        for lens in ALL_LENSES
    }

    for lens, future in futures.items():
        try:
<<<<<<< HEAD
            result = await asyncio.wait_for(future, timeout=60)
            matrix[lens] = result
        except asyncio.TimeoutError:
            log.warning(f"Lens '{lens}' timed out after 60s")
            matrix[lens] = {
                "error": "Timeout (60s)",
                "support_level": "none",
                "detected_biases": [],
                "query_used": "",
=======
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
>>>>>>> 49a4c8253654ebfc32bf4cfdbb214522ba140ad0
            }

        except Exception as e:
<<<<<<< HEAD
            log.error(f"Lens '{lens}' unexpected error: {e}")
            matrix[lens] = {"error": str(e), "support_level": "none", "detected_biases": [], "query_used": ""}
=======
            # Capture per-lens failure without aborting the full matrix
            matrix[lens] = {"error": str(e)}
>>>>>>> 49a4c8253654ebfc32bf4cfdbb214522ba140ad0

    log.info(f"Multi-lens scan complete: {len(matrix)} lenses processed")
    return {"ok": True, "lens_matrix": matrix}