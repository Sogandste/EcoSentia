# tests/conftest.py
"""Shared test fixtures."""

import pytest


@pytest.fixture
def fog_claim():
    return "A surface structure inspired by the Namib desert beetle for passive fog water collection via wettability gradient."


@pytest.fixture
def ev_claim():
    return "An extracellular vesicle-inspired nanoparticle for targeted drug delivery with immune evasion."


@pytest.fixture
def custom_claim():
    return "A gecko-inspired reversible adhesive patch for wet biomedical surfaces."


@pytest.fixture
def sample_snapshot():
    return {
        "combined_count": 8,
        "direct_hits": 3,
        "support_level": "moderate",
        "summary": "Moderate relevance with 3 direct hit(s). Matched: fog harvesting, wettability, biomimetic.",
        "top_titles": ["Paper A", "Paper B"],
        "top_records": [],
    }