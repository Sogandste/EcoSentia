# tests/test_literature.py
"""Unit tests for literature scoring (no network calls)."""

import pytest
from literature import _score_record, _classify_support, _jaccard, _term_hits


class TestJaccard:
    def test_identical(self):
        assert _jaccard(["a", "b", "c"], ["a", "b", "c"]) == 1.0

    def test_no_overlap(self):
        assert _jaccard(["a", "b"], ["c", "d"]) == 0.0

    def test_partial(self):
        result = _jaccard(["a", "b", "c"], ["a", "d", "e"])
        assert 0 < result < 1

    def test_empty(self):
        assert _jaccard([], ["a"]) == 0.0
        assert _jaccard(["a"], []) == 0.0


class TestTermHits:
    def test_basic(self):
        hits = _term_hits("fog harvesting on biomimetic surface", ["fog harvesting", "biomimetic"])
        assert "fog harvesting" in hits
        assert "biomimetic" in hits

    def test_no_hits(self):
        hits = _term_hits("something else entirely", ["fog", "beetle"])
        # "fog" is in "something"? No. Let's be specific
        hits = _term_hits("something else entirely", ["quantum", "nuclear"])
        assert hits == []


class TestScoreRecord:
    def test_high_relevance(self):
        record = {
            "title": "Namib desert beetle inspired fog harvesting surface",
            "abstract": "We designed a biomimetic surface using wettability gradient for fog harvesting water collection.",
            "source": "pubmed",
            "url": "",
            "year": 2023,
            "id": "123",
        }
        scored = _score_record(record, "Namib beetle fog harvesting", "fog", "mechanism")
        assert scored["score"] > 0.4
        assert scored["is_direct_hit"] is True
        assert len(scored["matched_terms"]) > 0

    def test_low_relevance(self):
        record = {
            "title": "Quantum computing algorithms for optimization",
            "abstract": "This paper discusses quantum gates and entanglement.",
            "source": "openalex",
            "url": "",
            "year": 2022,
            "id": "456",
        }
        scored = _score_record(record, "Namib beetle fog harvesting", "fog", "mechanism")
        assert scored["score"] < 0.2
        assert scored["is_direct_hit"] is False

    def test_negative_terms_penalty(self):
        record = {
            "title": "Mast cell interferon response in immune system",
            "abstract": "IFN antiviral immunity fog related terms.",
            "source": "pubmed",
            "url": "",
            "year": 2021,
            "id": "789",
        }
        scored = _score_record(record, "fog harvesting beetle", "fog", "mechanism")
        assert scored["is_direct_hit"] is False


class TestClassifySupport:
    def test_direct(self):
        scored = [{"score": 0.8, "is_direct_hit": True}] * 3
        assert _classify_support(scored) == "direct"

    def test_moderate(self):
        scored = [{"score": 0.6, "is_direct_hit": True}]
        assert _classify_support(scored) == "moderate"

    def test_none(self):
        assert _classify_support([]) == "none"
        scored = [{"score": 0.05, "is_direct_hit": False}]
        assert _classify_support(scored) == "none"