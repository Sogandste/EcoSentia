# api.py
# FastAPI endpoints for the EcoSentia evidence layer.

from fastapi import FastAPI, HTTPException
from models import EvidencePayload, PromptPayload, SnapshotModel
from query_builder import build_refined_query
from literature import run_evidence_scan
from prompt_builder import build_evidence_aware_prompts
from bias_checker import detect_biases

app = FastAPI(title="EcoSentia Evidence API", version="0.2")

@app.post("/evidence/refine-query")
def refine_evidence_query(payload: EvidencePayload):
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

@app.post("/evidence/scan")
def run_scan(payload: EvidencePayload):
    try:
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
        return {
            "ok":        True,
            "query_text": query,
            "snapshot":  snapshot_raw,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evidence/prompts")
def generate_prompts(payload: PromptPayload):
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

@app.post("/evidence/scan-all-lenses")
def scan_all_lenses(payload: EvidencePayload):
    lenses = ["mechanism", "context", "scale", "manufacturability", "safety"]
    matrix = {}

    for lens in lenses:
        try:
            refined = build_refined_query(
                preset=payload.preset,
                project=payload.project,
                claim=payload.claim,
                lens=lens,
            )
            snapshot_raw = run_evidence_scan(
                query=refined,
                source=payload.source,
                max_results=3,
                claim_text=payload.claim,
            )
            snapshot = SnapshotModel(**snapshot_raw)
            from evidence_utils import classify_support_level
            level  = classify_support_level(snapshot)
            biases = detect_biases(payload.claim)

            matrix[lens] = {
                "support_level":   level,
                "detected_biases": [b["bias"] for b in biases],
                "query_used":      refined,
            }
        except Exception as e:
            matrix[lens] = {"error": str(e)}

    return {"ok": True, "lens_matrix": matrix}