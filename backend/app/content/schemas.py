"""Pydantic 2.x schemas for content file validation."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator


# ---------------------------------------------------------------------------
# Knowledge Point
# ---------------------------------------------------------------------------

class KnowledgePointSchema(BaseModel):
    """Schema for a single knowledge point node (may contain children)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    sort_order: StrictInt = Field(ge=0)
    description: Optional[str] = None
    is_active: StrictBool = True
    children: list[KnowledgePointSchema] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("id 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("id 不能为空")
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._")
        if not set(v) <= allowed:
            raise ValueError(f"id '{v}' 格式不合法，只允许小写字母、数字、点、下划线")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("name 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("name 不能为空")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("description 必须是字符串")
            if not v.strip():
                raise ValueError("description 不能为空白字符串")
        return v


# ---------------------------------------------------------------------------
# Knowledge Card
# ---------------------------------------------------------------------------

class KnowledgeCardFrontMatter(BaseModel):
    """Front Matter schema for knowledge card Markdown files."""

    model_config = ConfigDict(extra="forbid")

    knowledge_point_id: str
    title: str
    is_active: StrictBool = True

    @field_validator("knowledge_point_id")
    @classmethod
    def validate_kp_id(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("knowledge_point_id 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("knowledge_point_id 不能为空")
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("title 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("title 不能为空")
        return v


# ---------------------------------------------------------------------------
# Choice Question
# ---------------------------------------------------------------------------

class ChoiceOption(BaseModel):
    """A single choice option."""

    model_config = ConfigDict(extra="forbid")

    key: str
    text: str

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("key 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("key 不能为空")
        return v

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("text 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("text 不能为空")
        return v


class ChoiceQuestionSchema(BaseModel):
    """Schema for choice question YAML files."""

    model_config = ConfigDict(extra="forbid")

    id: str
    question_type: str
    primary_knowledge_point_id: str
    title: Optional[str] = None
    difficulty: StrictInt = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    related_knowledge_points: list[str] = Field(default_factory=list)
    is_active: StrictBool = True
    content: str
    options: list[ChoiceOption]
    correct_answer: str
    explanation: str

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("id 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("id 不能为空")
        return v

    @field_validator("question_type")
    @classmethod
    def validate_question_type(cls, v: str) -> str:
        if v != "choice":
            raise ValueError("question_type 必须为 'choice'")
        return v

    @field_validator("primary_knowledge_point_id")
    @classmethod
    def validate_primary_kp(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("primary_knowledge_point_id 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("primary_knowledge_point_id 不能为空")
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("title 必须是字符串")
            if not v.strip():
                raise ValueError("title 不能为空白字符串")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        for i, tag in enumerate(v):
            if not isinstance(tag, str) or not tag.strip():
                raise ValueError(f"tags[{i}] 不能为空字符串")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("content 不能为空")
        return v

    @field_validator("correct_answer")
    @classmethod
    def validate_correct_answer(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("correct_answer 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("correct_answer 不能为空")
        return v

    @field_validator("explanation")
    @classmethod
    def validate_explanation(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("explanation 不能为空")
        return v


# ---------------------------------------------------------------------------
# Short Answer Question
# ---------------------------------------------------------------------------

class ShortAnswerQuestionSchema(BaseModel):
    """Schema for short answer question YAML files."""

    model_config = ConfigDict(extra="forbid")

    id: str
    question_type: str
    primary_knowledge_point_id: str
    title: Optional[str] = None
    difficulty: StrictInt = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    related_knowledge_points: list[str] = Field(default_factory=list)
    is_active: StrictBool = True
    content: str
    reference_answer: str
    explanation: str

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("id 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("id 不能为空")
        return v

    @field_validator("question_type")
    @classmethod
    def validate_question_type(cls, v: str) -> str:
        if v != "short_answer":
            raise ValueError("question_type 必须为 'short_answer'")
        return v

    @field_validator("primary_knowledge_point_id")
    @classmethod
    def validate_primary_kp(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("primary_knowledge_point_id 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("primary_knowledge_point_id 不能为空")
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("title 必须是字符串")
            if not v.strip():
                raise ValueError("title 不能为空白字符串")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        for i, tag in enumerate(v):
            if not isinstance(tag, str) or not tag.strip():
                raise ValueError(f"tags[{i}] 不能为空字符串")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("content 不能为空")
        return v

    @field_validator("reference_answer")
    @classmethod
    def validate_reference_answer(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("reference_answer 不能为空")
        return v

    @field_validator("explanation")
    @classmethod
    def validate_explanation(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("explanation 不能为空")
        return v


# ---------------------------------------------------------------------------
# SQL Question
# ---------------------------------------------------------------------------

class ScoringCriterion(BaseModel):
    """A single scoring criterion for SQL questions."""

    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    points: StrictInt = Field(gt=0)

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("id 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("id 不能为空")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("description 不能为空")
        return v


class SQLQuestionSchema(BaseModel):
    """Schema for SQL question YAML files."""

    model_config = ConfigDict(extra="forbid")

    id: str
    question_type: str
    primary_knowledge_point_id: str
    title: Optional[str] = None
    difficulty: StrictInt = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    related_knowledge_points: list[str] = Field(default_factory=list)
    is_active: StrictBool = True
    content: str
    table_schema: Optional[str] = None
    field_description: Optional[str] = None
    business_requirement: str
    expected_sql: Optional[str] = None
    scoring_criteria: list[ScoringCriterion]

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("id 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("id 不能为空")
        return v

    @field_validator("question_type")
    @classmethod
    def validate_question_type(cls, v: str) -> str:
        if v != "sql":
            raise ValueError("question_type 必须为 'sql'")
        return v

    @field_validator("primary_knowledge_point_id")
    @classmethod
    def validate_primary_kp(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("primary_knowledge_point_id 必须是字符串")
        v = v.strip()
        if not v:
            raise ValueError("primary_knowledge_point_id 不能为空")
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("title 必须是字符串")
            if not v.strip():
                raise ValueError("title 不能为空白字符串")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        for i, tag in enumerate(v):
            if not isinstance(tag, str) or not tag.strip():
                raise ValueError(f"tags[{i}] 不能为空字符串")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("content 不能为空")
        return v

    @field_validator("business_requirement")
    @classmethod
    def validate_business_requirement(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("business_requirement 不能为空")
        return v

    @field_validator("expected_sql")
    @classmethod
    def validate_expected_sql(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("expected_sql 必须是字符串")
            if not v.strip():
                raise ValueError("expected_sql 不能为空白字符串")
        return v

    @field_validator("table_schema")
    @classmethod
    def validate_table_schema(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("table_schema 必须是字符串")
            if not v.strip():
                raise ValueError("table_schema 不能为空白字符串")
        return v

    @field_validator("field_description")
    @classmethod
    def validate_field_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("field_description 必须是字符串")
            if not v.strip():
                raise ValueError("field_description 不能为空白字符串")
        return v
