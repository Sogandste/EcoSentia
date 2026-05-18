# literature.py
"""
Literature retrieval and scoring engine.
Fetches from PubMed (esearch + efetch for abstracts) and OpenAlex.
"""

import os
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from xml.etree import ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from domain_config import LENS_TERMS, get_positive_terms, get_negative_terms
from logger import get_logger

log = get_logger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
OPENALEX_WORKS = "https://api.openalex.org/works"

ECOSENTIA_EMAIL = os.getenv("ECOSENTIA_EMAIL", "shayesteh222sowgand@gmail.com")
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")  # Optional: raises rate limit to 10/sec

# Rate-limit: max 3 req/sec without key, 10 with key
_PUBMED_DELAY = 0.34 if not NCBI_API_KEY else 0.1


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9\-]+", (text or "").lower())


def _term_hits(text: str, terms: List[str]) -> List[str]:
    txt = (text or "").lower()
    return [t for t in terms if t.lower() in txt]


def _jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3, connect=2, read=2,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers["User-Agent"] = "EcoSentia/0.3 (academic-prototype)"
    return s


# ─── PubMed: esearch + efetch (XML for abstracts) ────────────────────────────

def _fetch_pubmed(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Two-step PubMed retrieval:
    1. esearch → get PMIDs
    2. efetch (XML) → get title + abstract
    """
    session = _session()

    # Step 1: Search
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
        "sort": "relevance",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    r = session.get(PUBMED_ESEARCH, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    pmids = (data.get("esearchresult") or {}).get("idlist") or []

    if not pmids:
        log.info("PubMed: 0 results for query")
        return []

    log.info(f"PubMed: found {len(pmids)} PMIDs")
    time.sleep(_PUBMED_DELAY)

    # Step 2: Fetch full records (XML for proper abstract parsing)
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    if NCBI_API_KEY:
        fetch_params["api_key"] = NCBI_API_KEY

    rf = session.get(PUBMED_EFETCH, params=fetch_params, timeout=25)
    rf.raise_for_status()

    records = _parse_pubmed_xml(rf.text, pmids)
    return records


def _parse_pubmed_xml(xml_text: str, pmids: List[str]) -> List[Dict[str, Any]]:
    """Parse PubMed efetch XML to extract title, abstract, year."""
    records = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log.error(f"PubMed XML parse error: {e}")
        return []

    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None else ""

        # Title
        title_el = article.find(".//ArticleTitle")
        title = _clean(title_el.text if title_el is not None else "")

        # Abstract (may have multiple AbstractText elements)
        abstract_parts = []
        for abs_el in article.findall(".//AbstractText"):
            label = abs_el.get("Label", "")
            text = "".join(abs_el.itertext())
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        abstract = _clean(" ".join(abstract_parts))

        # Year
        year = None
        year_el = article.find(".//PubDate/Year")
        if year_el is not None and year_el.text:
            try:
                year = int(year_el.text)
            except ValueError:
                pass
        if year is None:
            medline_el = article.find(".//MedlineDate")
            if medline_el is not None and medline_el.text:
                m = re.search(r"(19|20)\d{2}", medline_el.text)
                if m:
                    year = int(m.group(0))

        records.append({
            "id": pmid,
            "title": title,
            "abstract": abstract,
            "source": "pubmed",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "year": year,
        })

    log.info(f"PubMed XML parsed: {len(records)} records with abstracts")
    return records


# ─── OpenAlex ─────────────────────────────────────────────────────────────────

def _fetch_openalex(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    session = _session()

    params = {
        "search": query,
        "per_page": max_results,
        "mailto": ECOSENTIA_EMAIL,
    }
    r = session.get(OPENALEX_WORKS, params=params, timeout=20)
    r.raise_for_status()
    results = r.json().get("results") or []

    records = []
    for work in results:
        title = _clean(work.get("title", ""))

        # Reconstruct abstract from inverted index
        abstract = ""
        inv = work.get("abstract_inverted_index")
        if inv and isinstance(inv, dict):
            positions = []
            for word, idxs in inv.items():
                for idx in idxs:
                    positions.append((idx, word))
            positions.sort()
            abstract = " ".join(w for _, w in positions)

        year = work.get("publication_year")
        oa_id = work.get("id", "") or ""

        records.append({
            "id": oa_id.split("/")[-1] if oa_id else "",
            "title": title,
            "abstract": _clean(abstract),
            "source": "openalex",
            "url": oa_id,
            "year": year,
        })

    log.info(f"OpenAlex: retrieved {len(records)} records")
    return records


# ─── Scoring Engine ───────────────────────────────────────────────────────────

# Scoring weights (documented for transparency)
_W_JACCARD = 0.40       # Semantic overlap with claim
_W_POS_HIT = 0.12       # Per positive domain term (capped at 5)
_W_LENS_HIT = 0.06      # Per lens term (capped at 3)
_W_TITLE_BONUS = 0.08   # Per positive term in title (capped at 0.30)
_W_NEG_PENALTY = 0.22   # Per negative term (capped at 5)
_W_ABSTRACT_BONUS = 0.10  # Bonus if abstract available and has pos hits

_DIRECT_HIT_THRESHOLD = 0.42
_DIRECT_HIT_MIN_POS = 2


def _score_record(
    record: Dict[str, Any],
    claim_text: str,
    preset: str,
    lens: str,
    exclude_terms: str = "",
) -> Dict[str, Any]:
    """Score a single record against claim, domain, and lens."""
    title = record.get("title", "")
    abstract = record.get("abstract", "")
    combined = f"{title}. {abstract}".lower()

    claim_tokens = _tokens(claim_text)
    doc_tokens = _tokens(combined)
    sim = _jaccard(claim_tokens, doc_tokens)

    pos_terms = get_positive_terms(preset)
    neg_terms = get_negative_terms(preset)
    l_terms = LENS_TERMS.get((lens or "").lower(), [])
    extra_neg = [x.strip().lower() for x in re.split(r"[,\n;]+", exclude_terms or "") if x.strip()]

    pos_hits = _term_hits(combined, pos_terms)
    neg_hits = _term_hits(combined, neg_terms + extra_neg)
    lens_hits = _term_hits(combined, l_terms)

    # Title bonus
    title_lower = title.lower()
    title_bonus = sum(_W_TITLE_BONUS for t in pos_terms[:12] if t.lower() in title_lower)
    title_bonus = min(title_bonus, 0.30)

    # Abstract bonus: reward records that have abstracts with domain matches
    abstract_bonus = 0.0
    if abstract and len(abstract) > 50:
        abs_pos = _term_hits(abstract.lower(), pos_terms)
        if len(abs_pos) >= 2:
            abstract_bonus = _W_ABSTRACT_BONUS

    pos_score = min(len(pos_hits), 5) * _W_POS_HIT
    lens_score = min(len(lens_hits), 3) * _W_LENS_HIT
    neg_penalty = min(len(neg_hits), 5) * _W_NEG_PENALTY

    final = (
        _W_JACCARD * sim
        + pos_score
        + lens_score
        + title_bonus
        + abstract_bonus
        - neg_penalty
    )
    final = max(0.0, min(final, 1.0))

    is_direct = (
        final >= _DIRECT_HIT_THRESHOLD
        and len(pos_hits) >= _DIRECT_HIT_MIN_POS
        and len(neg_hits) == 0
    )

    return {
        **record,
        "score": round(final, 3),
        "matched_terms": sorted(set(pos_hits + lens_hits))[:8],
        "is_direct_hit": is_direct,
    }


# ─── Support Classification ──────────────────────────────────────────────────

def _classify_support(scored: List[Dict[str, Any]]) -> str:
    if not scored:
        return "none"
    direct = sum(1 for r in scored if r.get("is_direct_hit"))
    top = scored[0].get("score", 0.0)
    if direct >= 3 or top >= 0.75:
        return "direct"
    if direct >= 1 or top >= 0.55:
        return "moderate"
    if top >= 0.35:
        return "indirect"
    if top >= 0.15:
        return "limited"
    return "none"


def _build_summary(scored: List[Dict[str, Any]], level: str) -> str:
    if not scored:
        return "No relevant records were retrieved."
    direct = sum(1 for r in scored if r.get("is_direct_hit"))
    terms = []
    for r in scored[:3]:
        terms.extend(r.get("matched_terms", []))
    terms = list(dict.fromkeys(terms))[:5]
    t_str = ", ".join(terms) if terms else "general domain concepts"

    messages = {
        "direct": f"Strong relevance. {direct} direct-hit record(s). Key concepts: {t_str}.",
        "moderate": f"Moderate relevance with {direct} direct hit(s). Matched: {t_str}.",
        "indirect": f"Partial relevance; direct support limited. Related: {t_str}.",
        "limited": "Weak relevance. Most records are peripheral to the claim.",
    }
    return messages.get(level, "No meaningful relevance detected.")


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def run_evidence_scan(
    query: str,
    source: str,
    max_results: int,
    claim_text: str,
    preset: str = "fog",
    lens: str = "mechanism",
    exclude_terms: str = "",
) -> Dict[str, Any]:
    """
    Run a complete evidence scan: fetch → score → classify → summarize.
    """
    src = (source or "Both").lower()
    log.info(f"Evidence scan: source={src}, preset={preset}, lens={lens}, max={max_results}")

    pubmed_recs: List[Dict[str, Any]] = []
    openalex_recs: List[Dict[str, Any]] = []

    if src in ("both", "pubmed"):
        try:
            pubmed_recs = _fetch_pubmed(query, max_results)
        except Exception as e:
            log.warning(f"PubMed fetch failed: {e}")

    if src in ("both", "openalex"):
        try:
            openalex_recs = _fetch_openalex(query, max_results)
        except Exception as e:
            log.warning(f"OpenAlex fetch failed: {e}")

    all_recs = pubmed_recs + openalex_recs
    log.info(f"Total records fetched: {len(all_recs)} (PubMed: {len(pubmed_recs)}, OpenAlex: {len(openalex_recs)})")

    scored = [
        _score_record(r, claim_text, preset, lens, exclude_terms)
        for r in all_recs
    ]
    scored.sort(key=lambda x: x.get("score", 0), reverse=True)

    direct_hits = sum(1 for r in scored if r.get("is_direct_hit"))
    level = _classify_support(scored)
    summary = _build_summary(scored, level)

    top_records = [
        {
            "title": r.get("title", ""),
            "source": r.get("source", ""),
            "url": r.get("url", ""),
            "year": r.get("year"),
            "score": r.get("score"),
            "is_direct_hit": r.get("is_direct_hit", False),
            "matched_terms": r.get("matched_terms", []),
        }
        for r in scored[:max_results]
    ]

    return {
        "combined_count": len(scored),
        "direct_hits": direct_hits,
        "support_level": level,
        "summary": summary,
        "top_titles": [r["title"] for r in top_records],
        "top_records": top_records,
    }