# api.py
"""
EcoSentia Evidence API - FastAPI backend.
Fixes applied:
- CORS: wildcard origin is incompatible with allow_credentials=True, now uses env var
- DRY: _safe_snapshot() helper eliminates repeated setdefault blocks
- Concurrency: scan_all_lenses now uses asyncio.gather for true parallel execution
- ThreadPoolExecutor: size controlled via environment variable
- Input validation: empty claim guard on /evidence/prompts
- asyncio: get_running_loop() with RuntimeError fallback for Python 3.10+ compatibility
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import EvidencePayload, PromptPayload, SnapshotModel
from query_builder import build_refined_query
from literature import run_evidence_scan
from prompt_builder import build_evidence_aware_prompts

# ---------------------------------------------------------------------------
# Optional imports with safe fallback
# Allows the API to boot even if a single module is temporarily unavailable
# ---------------------------------------------------------------------------

try:
    from bias_checker import detect_biases
except Exception:
    def detect_biases(claim: str, lens: str = None):
        return []

try:
    from domain_config import ALL_LENSES
except Exception:
    ALL_LENSES = ["mechanism", "context", "scale", "manufacturability", "safety"]

try:
    from logger import get_logger
    log = get_logger(__name__)
except Exception:
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App initialization
# ---------------------------------------------------------------------------

app = FastAPI(title="EcoSentia Evidence API", version="0.3")

# CORS: wildcard origin is incompatible with allow_credentials=True per the
# CORS spec. Browsers will reject preflight responses that combine both.
# Use an explicit comma-separated list via the environment variable.
# Example: ALLOWED_ORIGINS=https://ecosentia.hf.space,https://localhost:8501
_raw_origins = os.getenv("ALLOWED_ORIGINS", "https://ecosentia.hf.space")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# Thread pool size is configurable via environment variable.
# On Render free tier, keep this at 3 to avoid resource exhaustion
# when multiple users call scan_all_lenses concurrently.
_MAX_WORKERS = int(os.getenv("THREAD_POOL_SIZE", "3"))
_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_mode(payload: EvidencePayload) -> str:
    """Normalize domain mode to lowercase preset string."""
    return (payload.domain_mode or payload.preset or "fog").strip().lower()


def _build_query_from_payload(
    payload: EvidencePayload,
    lens_override: str = None
) -> str:
    """Construct a Boolean query from payload fields."""
    return build_refined_query(
        preset=payload.preset,
        project=payload.project,
        claim=payload.claim,
        lens=lens_override or payload.lens,
        domain_mode=payload.domain_mode or payload.preset,
        biological_model=payload.biological_model or "",
        target_function=payload.target_function or "",
        application_context=payload.application_context or "",
        mechanism_keywords=payload.mechanism_keywords or "",
        exclude_terms=payload.exclude_terms or "",
    )


def _safe_snapshot(raw: dict) -> SnapshotModel:
    """
    Normalize a raw dict from run_evidence_scan into a validated SnapshotModel.
    setdefault guards against missing keys if literature.py changes its output contract.
    Centralizing this logic eliminates the repeated setdefault blocks
    that previously appeared in both scan() and _scan_single_lens().
    """
    raw.setdefault("direct_hits", 0)
    raw.setdefault("combined_count", 0)
    raw.setdefault("support_level", "none")
    raw.setdefault("summary", "No summary available.")
    raw.setdefault("top_titles", [])
    raw.setdefault("top_records", [])
    return SnapshotModel(**raw)


def _call_detect_biases(claim: str, lens: str):
    """
    Compatibility wrapper for detect_biases.
    Supports both the legacy signature detect_biases(claim)
    and the current signature detect_biases(claim, lens=...).
    Falls back to an empty list on any unexpected failure.
    """
    try:
        return detect_biases(claim, lens=lens)
    except TypeError:
        return detect_biases(claim)
    except Exception as e:
        log.warning(f"Bias detection failed for lens={lens}: {e}")
        return []


def _scan_single_lens(
    payload: EvidencePayload,
    lens: str,
    mode: str
) -> Dict[str, Any]:
    """
    Execute a full evidence scan for a single lens.
    Designed to be called inside a ThreadPoolExecutor.
    Returns a result dict or an error dict on failure — never raises.
    """
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

        snapshot = _safe_snapshot(snapshot_raw)
        biases = _call_detect_biases(payload.claim, lens=lens)

        return {
            "support_level": snapshot.support_level,
            "detected_biases": biases,
            "query_used": refined,
        }

    except Exception as e:
        log.error(f"Lens scan error [{lens}]: {e}")
        return {
            "error": str(e),
            "support_level": "none",
            "detected_biases": [],
            "query_used": "",
        }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    """Liveness probe used by Render and Hugging Face to confirm the service is up."""
    return {
        "ok": True,
        "service": "EcoSentia Evidence API",
        "version": "0.3",
    }


@app.post("/evidence/refine-query")
def refine_query(payload: EvidencePayload):
    """
    Translate a natural-language design claim into a structured Boolean query.
    Returns the refined query string without executing any literature search.
    """
    try:
        refined = _build_query_from_payload(payload)
        log.info(f"Query refined: {refined[:120]}")
        return {"ok": True, "refined_query": refined}

    except Exception as e:
        log.error(f"refine-query error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"stage": "refine-query", "message": str(e)},
        )


@app.post("/evidence/scan")
def scan(payload: EvidencePayload):
    """
    Execute a literature scan against PubMed and/or OpenAlex.
    Accepts an optional pre-built query_text; builds one from payload if absent.
    Returns a normalized SnapshotModel with scoring and classification.
    """
    try:
        query = payload.query_text or _build_query_from_payload(payload)
        mode = _resolve_mode(payload)

        snapshot_raw = run_evidence_scan(
            query=query,
            source=payload.source,
            max_results=payload.max_results,
            claim_text=payload.claim,
            preset=mode,
            lens=payload.lens,
            exclude_terms=payload.exclude_terms or "",
        )

        snapshot = _safe_snapshot(snapshot_raw)

        log.info(
            f"Scan complete | records={snapshot.combined_count} | "
            f"direct_hits={snapshot.direct_hits} | level={snapshot.support_level}"
        )

        return {
            "ok": True,
            "query_text": query,
            "snapshot": snapshot.model_dump(),
        }

    except Exception as e:
        log.error(f"scan error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"stage": "scan", "message": str(e)},
        )


@app.post("/evidence/prompts")
def prompts(payload: PromptPayload):
    """
    Generate a suite of evidence-aware LLM prompts from a completed scan snapshot.
    Validates that claim is non-empty before processing to avoid silent 500 errors.
    """
    if not payload.claim or not payload.claim.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "stage": "prompts",
                "message": "claim field is required and cannot be empty.",
            },
        )

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
        raise HTTPException(
            status_code=500,
            detail={"stage": "prompts", "message": str(e)},
        )


@app.post("/evidence/scan-all-lenses")
async def scan_all_lenses(payload: EvidencePayload):
    """
    Run a full evidence scan across all analytical lenses in parallel.

    Architecture note:
    The previous implementation awaited futures sequentially inside a for-loop,
    meaning the total wall time equalled the sum of all lens times rather than
    the duration of the slowest one. asyncio.gather() corrects this by launching
    all futures concurrently and collecting results once all have resolved or
    timed out. Each future still runs in a thread (because run_evidence_scan
    uses blocking I/O), but the event loop does not block between them.

    Timeout is applied per-lens via asyncio.wait_for. A timed-out lens is
    recorded as an error entry rather than failing the entire matrix.
    """
    mode = _resolve_mode(payload)
    log.info(f"Multi-lens scan started | claim={payload.claim[:80]}")

    # Resolve the event loop safely for Python 3.10+ and 3.12+
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()

    # Build one future per lens
    lens_futures = {
        lens: loop.run_in_executor(_executor, _scan_single_lens, payload, lens, mode)
        for lens in ALL_LENSES
    }

    # Wrap each future with a per-lens timeout
    async def _guarded(lens: str, future):
        try:
            return lens, await asyncio.wait_for(future, timeout=60)
        except asyncio.TimeoutError:
            log.warning(f"Lens timed out: {lens}")
            return lens, {
                "error": "Timeout (60s)",
                "support_level": "none",
                "detected_biases": [],
                "query_used": "",
            }
        except Exception as e:
            log.error(f"Unexpected error in lens {lens}: {e}")
            return lens, {
                "error": str(e),
                "support_level": "none",
                "detected_biases": [],
                "query_used": "",
            }

    # Execute all lenses in true parallel and collect results
    gathered = await asyncio.gather(
        *[_guarded(lens, future) for lens, future in lens_futures.items()]
    )

    matrix = {lens: result for lens, result in gathered}

    log.info(f"Multi-lens scan complete | processed={len(matrix)}")
    return {"ok": True, "lens_matrix": matrix}