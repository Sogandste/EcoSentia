# tests/test_bias_checker.py
"""Unit tests for bias_checker module."""

import pytest
from bias_checker import detect_biases


class TestDetectBiases:
    def test_morphology_overreach(self):
        claim = "A bioinspired surface structure mimicking beetle bumps"
        biases = detect_biases(claim)
        names = [b["bias"] for b in biases]
        assert "Morphology Overreach" in names

    def test_mechanism_stated_no_overreach(self):
        claim = "A biomimetic surface using wettability gradient mechanism for fog collection"
        biases = detect_biases(claim)
        names = [b["bias"] for b in biases]
        assert "Morphology Overreach" not in names
        assert "Mechanism Gap" not in names

    def test_safety_blindspot(self):
        claim = "A nanoparticle for drug delivery in clinical applications"
        biases = detect_biases(claim)
        names = [b["bias"] for b in biases]
        assert "Safety Blindspot" in names

    def test_safety_mentioned_no_blindspot(self):
        claim = "A biocompatible nanoparticle for drug delivery with safety assessment"
        biases = detect_biases(claim)
        names = [b["bias"] for b in biases]
        assert "Safety Blindspot" not in names

    def test_scale_risk(self):
        claim = "A nano-scale patterned surface for enhanced condensation"
        biases = detect_biases(claim)
        names = [b["bias"] for b in biases]
        assert "Scale Translation Risk" in names

    def test_context_transfer(self):
        claim = "Inspired by desert beetle for clinical use"
        biases = detect_biases(claim)
        names = [b["bias"] for b in biases]
        assert "Context Transfer Risk" in names

    def test_no_bias_detected(self):
        claim = "A functional mechanism for fog harvesting using wettability gradient with safety data"
        biases = detect_biases(claim)
        names = [b["bias"] for b in biases]
        # Should at least have "No Strong Pattern Detected" or specific ones
        assert len(biases) >= 1

    def test_empty_claim(self):
        biases = detect_biases("")
        assert biases[0]["bias"] == "Empty Claim"

    def test_lens_specific_gap(self):
        claim = "A biomimetic surface for enhanced performance"
        biases = detect_biases(claim, lens="safety")
        names = [b["bias"] for b in biases]
        assert "Safety Lens Gap" in names