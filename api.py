from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from domain_config import ALL_LENSES
from logger import get_logger
from models import EvidencePayload, PromptPayload, ScanResult, SnapshotModel
from prompt_builder import build_evidence_aware_prompts
from query_builder import build_refined_query
from literature import run_evidence_scan
from bias_checker import detect_biases

APP_VERSION = "0.5.1"
SERVICE_NAME = "EcoSentia Evidence API"

log = get_logger(__name__, level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(title=SERVICE_NAME, version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_WORKERS = int(os.getenv("ECOSENTIA_MAX_WORKERS", "3"))
LENS_SCAN_TIMEOUT = int(os.getenv("ECOSENTIA_LENS_TIMEOUT", "60"))

_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)


def _resolve_mode(payload: EvidencePayload) -> str:
    return (payload.domain_mode or payload.preset or "fog").strip().lower()


def _build_query_from_payload(payload: EvidencePayload, lens_override: str | None = None) -> str:
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


def _run_scan(payload: EvidencePayload, query_text: str, lens_override: str | None = None) -> Dict[str, Any]:
    mode = _resolve_mode(payload)
    lens = lens_override or payload.lens

    return run_evidence_scan(
        query=query_text,
        source=payload.source,
        max_results=payload.max_results,
        claim_text=payload.claim,
        preset=mode,
        lens=lens,
        exclude_terms=payload.exclude_terms or "",
    )


def _scan_single_lens(payload: EvidencePayload, lens: str, mode: str) -> Dict[str, Any]:
    try:
        refined_query = _build_query_from_payload(payload, lens_override=lens)

        snapshot_raw = run_evidence_scan(
            query=refined_query,
            source=payload.source,
            max_results=min(payload.max_results, 3),
            claim_text=payload.claim,
            preset=mode,
            lens=lens,
            exclude_terms=payload.exclude_terms or "",
        )

        biases = detect_biases(payload.claim, lens=lens)

        return {
            "support_level": snapshot_raw.get("support_level", "none"),
            "detected_biases": biases,
            "query_used": refined_query,
            "error": None,
        }

    except Exception as exc:
        log.exception("Lens scan failed", extra={"lens": lens, "error": str(exc)})
        return {
            "support_level": "none",
            "detected_biases": [],
            "query_used": "",
            "error": str(exc),
        }


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "version": APP_VERSION,
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "version": APP_VERSION,
        "config": {
            "max_workers": MAX_WORKERS,
            "lens_scan_timeout_sec": LENS_SCAN_TIMEOUT,
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "ncbi_api_key_configured": bool(os.getenv("NCBI_API_KEY")),
            "ecosentia_email_configured": bool(os.getenv("ECOSENTIA_EMAIL")),
        },
        "lenses": ALL_LENSES,
    }


@app.post("/evidence/refine-query")
def refine_query(payload: EvidencePayload) -> Dict[str, Any]:
    try:
        refined = _build_query_from_payload(payload)
        log.info("Query refined")
        return {
            "ok": True,
            "refined_query": refined,
        }
    except Exception as exc:
        log.exception("refine-query failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=500,
            detail={"stage": "refine-query", "message": str(exc)},
        ) from exc


@app.post("/evidence/scan", response_model=ScanResult)
def scan(payload: EvidencePayload) -> ScanResult:
    try:
        query_text = (payload.query_text or "").strip() or _build_query_from_payload(payload)
        snapshot_raw = _run_scan(payload, query_text=query_text)
        snapshot = SnapshotModel(**snapshot_raw)

        log.info(
            "Scan complete",
            extra={
                "support_level": snapshot.support_level,
                "combined_count": snapshot.combined_count,
                "direct_hits": snapshot.direct_hits,
            },
        )

        return ScanResult(
            ok=True,
            query_text=query_text,
            snapshot=snapshot,
        )

    except Exception as exc:
        log.exception("scan failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=500,
            detail={"stage": "scan", "message": str(exc)},
        ) from exc


@app.post("/evidence/prompts")
def prompts(payload: PromptPayload) -> Dict[str, Any]:
    try:
        result = build_evidence_aware_prompts(
            preset=payload.preset,
            lens=payload.lens,
            claim=payload.claim,
            query_text=payload.query_text,
            snapshot=payload.snapshot,
        )

        log.info(
            "Prompts generated",
            extra={
                "lens": payload.lens,
                "support_level": result.get("support_level", "none"),
            },
        )

        return {
            "ok": True,
            "prompts": result,
        }

    except Exception as exc:
        log.exception("prompts failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=500,
            detail={"stage": "prompts", "message": str(exc)},
        ) from exc


@app.post("/evidence/scan-all-lenses")
async def scan_all_lenses(payload: EvidencePayload) -> Dict[str, Any]:
    mode = _resolve_mode(payload)
    matrix: Dict[str, Any] = {}

    try:
        claim_preview = payload.claim[:80] if payload.claim else ""
        log.info(
            "Starting multi-lens scan",
            extra={"claim_preview": claim_preview, "mode": mode},
        )

        loop = asyncio.get_running_loop()
        futures = {
            lens: loop.run_in_executor(_executor, _scan_single_lens, payload, lens, mode)
            for lens in ALL_LENSES
        }

        for lens, future in futures.items():
            try:
                result = await asyncio.wait_for(future, timeout=LENS_SCAN_TIMEOUT)
                matrix[lens] = result
            except asyncio.TimeoutError:
                log.warning("Lens scan timeout", extra={"lens": lens, "timeout": LENS_SCAN_TIMEOUT})
                matrix[lens] = {
                    "support_level": "none",
                    "detected_biases": [],
                    "query_used": "",
                    "error": f"Timeout ({LENS_SCAN_TIMEOUT}s)",
                }
            except Exception as exc:
                log.exception("Lens scan unexpected failure", extra={"lens": lens, "error": str(exc)})
                matrix[lens] = {
                    "support_level": "none",
                    "detected_biases": [],
                    "query_used": "",
                    "error": str(exc),
                }

        log.info("Multi-lens scan complete", extra={"lens_count": len(matrix)})

        return {
            "ok": True,
            "lens_matrix": matrix,
        }

    except Exception as exc:
        log.exception("scan-all-lenses failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=500,
            detail={"stage": "scan-all-lenses", "message": str(exc)},
        ) from exc