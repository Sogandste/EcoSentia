# models.py
from typing import Literal, Dict, List
from pydantic import BaseModel, Field

class SnapshotModel(BaseModel):
    combined_count: int       = Field(default=0, ge=0)
    direct_hits:    int       = Field(default=0, ge=0)
    source_counts:  Dict[str, int] = Field(default_factory=dict)
    summary:        str       = Field(default="")
    top_titles:     List[str] = Field(default_factory=list)
    query_used:     str       = Field(default="")

class EvidencePayload(BaseModel):
    session_id:  str
    preset:      Literal["fog", "ev"]                                                    = "fog"
    project:     str                                                                      = ""
    claim:       str                                                                      = ""
    lens:        Literal["mechanism", "context", "scale", "manufacturability", "safety"] = "mechanism"
    source:      Literal["Both", "PubMed", "OpenAlex"]                                   = "Both"
    query_text:  str                                                                      = ""
    max_results: int = Field(default=5, ge=1, le=20)

class PromptPayload(BaseModel):
    preset:     Literal["fog", "ev"]                                                    = "fog"
    lens:       Literal["mechanism", "context", "scale", "manufacturability", "safety"] = "mechanism"
    claim:      str
    query_text: str
    snapshot:   SnapshotModel
