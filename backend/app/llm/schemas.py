"""Structured schemas for SQL grading — Phase 8A.

Defines input/output structures for SQL AI grading.
Does NOT write to database — that is Phase 8B.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

class ScoringCriterionInput(BaseModel):
    """A single scoring criterion from the question."""

    id: str
    description: str
    points: int


class SQLGradingInput(BaseModel):
    """Input for SQL grading — passed to LLMService."""

    question_id: str
    content: str
    table_schema: Optional[str] = None
    field_description: Optional[str] = None
    business_requirement: str
    scoring_criteria: list[ScoringCriterionInput]
    expected_sql: Optional[str] = None
    user_sql: str
    max_score: int


# ---------------------------------------------------------------------------
# Output — Structured Result
# ---------------------------------------------------------------------------

class CriterionResult(BaseModel):
    """Result for a single scoring criterion."""

    id: str
    status: Literal["matched", "partial", "missing"]
    score: float = Field(ge=0)
    max_score: float = Field(ge=0)
    feedback: str = ""

    @field_validator("score")
    @classmethod
    def score_not_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("score must be >= 0")
        return v


class KnowledgeAnalysis(BaseModel):
    """Knowledge point analysis from grading."""

    mastered: list[str] = Field(default_factory=list)
    weak: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class SQLGradingResult(BaseModel):
    """Structured result from SQL grading."""

    score: float = Field(ge=0)
    max_score: float = Field(ge=0)
    criteria: list[CriterionResult] = Field(default_factory=list)
    knowledge_analysis: KnowledgeAnalysis = Field(default_factory=KnowledgeAnalysis)
    errors: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: float) -> float:
        if v < 0:
            raise ValueError("score must be >= 0")
        return v

    @model_validator(mode="after")
    def validate_score_bounds(self) -> "SQLGradingResult":
        if self.score > self.max_score:
            raise ValueError(f"score {self.score} exceeds max_score {self.max_score}")
        return self

    @field_validator("criteria")
    @classmethod
    def validate_criteria_scores(cls, v: list[CriterionResult]) -> list[CriterionResult]:
        for c in v:
            if c.score > c.max_score:
                raise ValueError(f"criterion '{c.id}': score {c.score} > max_score {c.max_score}")
        return v
