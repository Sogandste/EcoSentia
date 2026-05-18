# models.py
"""
Pydantic v2 models for API payloads and responses.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

VALID_LENSES = ("mechanism", "context", "scale", "manufacturability", "safety")
VALID_SOURCES = ("Both", "PubMed", "OpenAlex")
VALID_PRESETS = ("fog", "ev", "custom")


class TopRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    source: str = ""
    url: Optional[str] = ""
    year: Optional[int] = None
    score: Optional[float] = None
    is_direct_hit: Optional[bool] = False
    matched_terms: List[str] = Field(default_factory=list)


class SnapshotModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    combined_count: int = 0
    direct_hits: int = 0
    support_level: str = "none"
    summary: str = "No summary available."
    top_titles: List[str] = Field(default_factory=list)
    top_records: List[TopRecord] = Field(default_factory=list)


class EvidencePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str = "streamlit"
    preset: str = "fog"
    project: str = ""
    claim: str
    lens: str = "mechanism"
    source: str = "Both"
    max_results: int = Field(default=5, ge=1, le=15)
    query_text: Optional[str] = None
    domain_mode: Optional[str] = "Fog"
    biological_model: Optional[str] = ""
    target_function: Optional[str] = ""
    application_context: Optional[str] = ""
    mechanism_keywords: Optional[str] = ""
    exclude_terms: Optional[str] = ""

    @field_validator("lens")
    @classmethod
    def normalize_lens(cls, v: str) -> str:
        v = (v or "mechanism").strip().lower()
        if v not in VALID_LENSES:
            return "mechanism"
        return v

    @field_validator("preset")
    @classmethod
    def normalize_preset(cls, v: str) -> str:
        v = (v or "fog").strip().lower()
        if v not in VALID_PRESETS:
            return "custom"
        return v


class PromptPayload(BaseModel):
    preset: str
    lens: str
    claim: str
    query_text: str
    snapshot: Dict[str, Any]


class ScanResult(BaseModel):
    """Response model for /evidence/scan."""
    ok: bool = True
    query_text: str
    snapshot: SnapshotModel


class LensMatrixEntry(BaseModel):
    support_level: str = "none"
    detected_biases: List[Dict[str, str]] = Field(default_factory=list)
    query_used: str = ""
    error: Optional[str] = None