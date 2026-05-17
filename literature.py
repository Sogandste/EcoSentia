# literature.py
import os
import time
import logging
import requests
from typing import List

logger = logging.getLogger(__name__)

CONTACT_EMAIL: str = os.getenv("ECOSENTIA_EMAIL", "your.email@example.com")
TOOL_NAME:     str = os.getenv("ECOSENTIA_TOOL",  "EcosentiaApp")

if CONTACT_EMAIL == "your.email@example.com":
    logger.warning("[literature] ECOSENTIA_EMAIL not set in environment.")

_session = requests.Session()
_session.headers.update({
    "User-Agent": f"{TOOL_NAME}/0.2 (mailto:{CONTACT_EMAIL})"
})

PUBMED_DELAY:   float = 0.4
OPENALEX_DELAY: float = 0.2

PUBMED_SEARCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
OPENALEX_URL       = "https://api.openalex.org/works"

def search_pubmed(query: str, max_results: int = 5) -> dict:
    max_results = min(max_results, 20)
    params = {
        "db": "pubmed", "term": query, "retmax": max_results, "retmode": "json",
        "tool": TOOL_NAME, "email": CONTACT_EMAIL,
    }
    try:
        time.sleep(PUBMED_DELAY)
        resp = _session.get(PUBMED_SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ids = data.get("esearchresult", {}).get("idlist", [])
        total = int(data.get("esearchresult", {}).get("count", 0))
        return {"ids": ids, "count": total, "returned": len(ids), "query_used": query, "source": "PubMed"}
    except requests.RequestException as e:
        logger.error("[PubMed] search failed: %s", e)
        return {"ids": [], "count": 0, "returned": 0, "query_used": query, "source": "PubMed", "error": str(e)}

def fetch_pubmed_titles(pmids: List[str]) -> List[str]:
    if not pmids: return []
    params = {
        "db": "pubmed", "id": ",".join(pmids), "retmode": "json",
        "tool": TOOL_NAME, "email": CONTACT_EMAIL,
    }
    try:
        time.sleep(PUBMED_DELAY)
        resp = _session.get(PUBMED_SUMMARY_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        uids = data.get("result", {}).get("uids", [])
        titles = [data["result"][uid].get("title", "") for uid in uids if uid in data.get("result", {})]
        return [t for t in titles if t]
    except requests.RequestException as e:
        logger.error("[PubMed] title fetch failed: %s", e)
        return []

def search_openalex(query: str, max_results: int = 5) -> dict:
    max_results = min(max_results, 20)
    params = {"search": query, "per-page": max_results, "select": "id,title,publication_year,primary_location,cited_by_count"}
    try:
        time.sleep(OPENALEX_DELAY)
        resp = _session.get(OPENALEX_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("results", [])
        total = data.get("meta", {}).get("count", 0)
        results = []
        for work in raw:
            source_name = ((work.get("primary_location") or {}).get("source") or {}).get("display_name", "")
            results.append({
                "openalex_id": work.get("id", ""),
                "title": work.get("title", "") or "",
                "year": work.get("publication_year"),
                "venue": source_name,
                "citations": work.get("cited_by_count", 0),
            })
        return {"results": results, "count": total, "returned": len(results), "query_used": query, "source": "OpenAlex"}
    except requests.RequestException as e:
        logger.error("[OpenAlex] search failed: %s", e)
        return {"results": [], "count": 0, "returned": 0, "query_used": query, "source": "OpenAlex", "error": str(e)}

def _score_direct_hits(titles: List[str], claim: str) -> int:
    if not titles or not claim: return 0
    stop = {"a", "an", "the", "of", "in", "for", "and", "or", "to", "with", "by", "on", "is", "are", "was", "that", "this"}
    claim_tokens = {w.lower().strip(".,;:()") for w in claim.split() if len(w) > 3 and w.lower() not in stop}
    hits = 0
    for title in titles:
        title_tokens = {w.lower().strip(".,;:()") for w in title.split()}
        if len(claim_tokens & title_tokens) >= 2:
            hits += 1
    return hits

def run_evidence_scan(query: str, source: str = "Both", max_results: int = 5, claim_text: str = "") -> dict:
    pubmed_data = {"ids": [], "count": 0, "returned": 0}
    openalex_data = {"results": [], "count": 0, "returned": 0}

    if source in ("PubMed", "Both"):
        pubmed_data = search_pubmed(query, max_results)
    if source in ("OpenAlex", "Both"):
        openalex_data = search_openalex(query, max_results)

    openalex_titles = [r["title"] for r in openalex_data.get("results", []) if r.get("title")]
    pubmed_titles = []
    if pubmed_data.get("ids"):
        pubmed_titles = fetch_pubmed_titles(pubmed_data["ids"][:max_results])

    all_titles = pubmed_titles + openalex_titles
    direct_hits = _score_direct_hits(all_titles, claim_text)

    combined = pubmed_data["returned"] + openalex_data["returned"]
    source_counts = {}
    if pubmed_data["returned"]: source_counts["PubMed"] = pubmed_data["returned"]
    if openalex_data["returned"]: source_counts["OpenAlex"] = openalex_data["returned"]

    if combined == 0:
        summary = "No records retrieved. Consider revising the query or broadening the claim before drawing conclusions."
    elif direct_hits == 0:
        summary = f"{combined} records retrieved ({_fmt_sources(source_counts)}), none matched claim tokens directly. Manual screening required."
    else:
        summary = f"{combined} records retrieved ({_fmt_sources(source_counts)}); {direct_hits} matched claim tokens. Relevance and quality require manual verification."

    return {
        "combined_count": combined,
        "direct_hits": direct_hits,
        "source_counts": source_counts,
        "summary": summary,
        "top_titles": all_titles[:5],
        "query_used": query,
    }

def _fmt_sources(source_counts: dict) -> str:
    return "; ".join(f"{k}: {v}" for k, v in source_counts.items())