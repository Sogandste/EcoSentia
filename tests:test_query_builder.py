# tests/test_query_builder.py
"""Unit tests for query_builder module."""

import pytest
from query_builder import build_refined_query, _extract_claim_terms, _or_block


class TestExtractClaimTerms:
    def test_basic_extraction(self):
        terms = _extract_claim_terms("A surface inspired by the Namib desert beetle for fog harvesting")
        assert "fog harvesting" in terms
        assert "namib desert beetle" in terms

    def test_empty_input(self):
        assert _extract_claim_terms("") == []
        assert _extract_claim_terms(None) == []

    def test_stop_words_removed(self):
        terms = _extract_claim_terms("the for and with")
        assert len(terms) == 0

    def test_max_terms_limit(self):
        long_claim = " ".join([f"term{i}" for i in range(50)])
        terms = _extract_claim_terms(long_claim)
        assert len(terms) <= 14


class TestOrBlock:
    def test_single_term(self):
        assert _or_block(["hello"]) == "hello"

    def test_multiple_terms(self):
        result = _or_block(["a", "b", "c"])
        assert result == "(a OR b OR c)"

    def test_quoted_phrases(self):
        result = _or_block(["fog harvesting", "water"])
        assert '"fog harvesting"' in result
        assert "water" in result

    def test_empty(self):
        assert _or_block([]) == ""

    def test_limit(self):
        terms = [f"t{i}" for i in range(20)]
        result = _or_block(terms, limit=3)
        assert result.count("OR") == 2


class TestBuildRefinedQuery:
    def test_fog_mode(self):
        q = build_refined_query(
            preset="fog", project="", claim="beetle water collection",
            lens="mechanism", domain_mode="Fog",
        )
        assert "Namib" in q or "beetle" in q
        assert "NOT" in q  # negative terms

    def test_ev_mode(self):
        q = build_refined_query(
            preset="ev", project="", claim="exosome drug delivery",
            lens="safety", domain_mode="EV",
        )
        assert "extracellular" in q or "exosome" in q

    def test_custom_mode(self):
        q = build_refined_query(
            preset="custom", project="", claim="gecko adhesion",
            lens="mechanism", domain_mode="Custom",
            biological_model="Gecko",
            target_function="adhesion",
        )
        assert "Gecko" in q or "gecko" in q

    def test_exclude_terms_included(self):
        q = build_refined_query(
            preset="fog", project="", claim="beetle water",
            lens="mechanism", domain_mode="Fog",
            exclude_terms="vaccine, cancer",
        )
        assert "vaccine" in q or "cancer" in q