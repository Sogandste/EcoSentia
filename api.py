# api.py
"""
EcoSentia Evidence API — FastAPI backend.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import EvidencePayload, PromptPayload, SnapshotModel
from query_builder import build_refined_query
from literature import run_evidence_scan
from prompt_builder import build_evidence_aware_prompts
from bias_checker import detect_biases
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


@app.post("/evidence/refine-query")
def refine_query(payload: EvidencePayload):
    try:
        refined = _build_query_from_payload(payload)
        log.info(f"Query refined: {refined[:80]}...")
        return {"ok": True, "refined_query": refined}
    except Exception as e:
        log.error(f"refine-query error: {e}")
        raise HTTPException(status_code=500, detail={"stage": "refine-query", "message": str(e)})


@app.post("/evidence/scan")
def scan(payload: EvidencePayload):
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

        snapshot = SnapshotModel(**snapshot_raw)
        log.info(f"Scan complete: {snapshot.combined_count} records, level={snapshot.support_level}")

        return {
            "ok": True,
            "query_text": query,
            "snapshot": snapshot.model_dump(),
        }
    except Exception as e:
        log.error(f"scan error: {e}")
        raise HTTPException(status_code=500, detail={"stage": "scan", "message": str(e)})


@app.post("/evidence/prompts")
def prompts(payload: PromptPayload):
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


@app.post("/evidence/scan-all-lenses")
async def scan_all_lenses(payload: EvidencePayload):
    """
    Scan all analytical lenses. Uses thread pool for partial parallelism.
    Includes per-lens timeout protection.
    """
    mode = _resolve_mode(payload)
    matrix: Dict[str, Any] = {}
    loop = asyncio.get_event_loop()

    log.info(f"Starting multi-lens scan for claim[:50]='{payload.claim[:50]}'")

    # Run lens scans with concurrency (limited to 3 parallel to respect rate limits)
    futures = {
        lens: loop.run_in_executor(_executor, _scan_single_lens, payload, lens, mode)
        for lens in ALL_LENSES
    }

    for lens, future in futures.items():
        try:
            result = await asyncio.wait_for(future, timeout=60)
            matrix[lens] = result
        except asyncio.TimeoutError:
            log.warning(f"Lens '{lens}' timed out after 60s")
            matrix[lens] = {
                "error": "Timeout (60s)",
                "support_level": "none",
                "detected_biases": [],
                "query_used": "",
            }
        except Exception as e:
            log.error(f"Lens '{lens}' unexpected error: {e}")
            matrix[lens] = {"error": str(e), "support_level": "none", "detected_biases": [], "query_used": ""}

    log.info(f"Multi-lens scan complete: {len(matrix)} lenses processed")
    return {"ok": True, "lens_matrix": matrix}