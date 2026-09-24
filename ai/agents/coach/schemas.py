"""
Structured-output contracts for the Coach's individual LLM calls.

These are intentionally separate from ai/models/schemas.py: those are
domain/event contracts shared with the rest of the system (backend,
analytics), these are the raw shapes we ask the LLM to fill in during a
single graph node.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ai.models.schemas import DiagnosisCategory, InterventionType


class DiagnosisResult(BaseModel):
    """Raw structured output of the diagnosis LLM call."""

    category: DiagnosisCategory
    concept: Optional[str] = Field(default=None)
    explanation: str
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)


class InterventionDecision(BaseModel):
    """Raw structured output of the intervention-selection LLM call."""

    intervention_type: InterventionType
    rationale: str
    needs_course_material: bool = Field(
        default=False, description="Whether course material retrieval would improve the response."
    )
    needs_student_history: bool = Field(
        default=False, description="Whether prior learning history would improve the response."
    )


class GeneratedResponse(BaseModel):
    """Raw structured output of the response-generation LLM call."""

    response: str
    referenced_concepts: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Raw structured output of the response-validation LLM call."""

    passes: bool
    violations: list[str] = Field(default_factory=list)
    revised_response: Optional[str] = Field(
        default=None,
        description="A corrected response, only if `passes` is False and a safe fix exists.",
    )
