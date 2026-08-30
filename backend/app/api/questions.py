"""Question API — Task 4.2.

Endpoints:
    GET /api/v1/questions       — question list with filters
    GET /api/v1/questions/{id}  — single question detail (answer hidden)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.question import (
    QuestionDetailResponse,
    QuestionListItem,
    QuestionListResponse,
    KnowledgePointRef,
    ChoiceOption,
)
from app.services.question_service import get_question_detail, list_questions

router = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------------------
# GET /api/v1/questions — list
# ---------------------------------------------------------------------------

@router.get("/questions", response_model=QuestionListResponse)
def get_questions(
    knowledge_point_id: Optional[str] = None,
    question_type: Optional[str] = None,
    difficulty: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """Return a filtered, paginated list of questions."""
    result = list_questions(
        db,
        knowledge_point_id=knowledge_point_id,
        question_type=question_type,
        difficulty=difficulty,
        page=page,
        page_size=page_size,
    )
    return QuestionListResponse(
        items=[QuestionListItem(**item) for item in result["items"]],
        page=result["page"],
        page_size=result["page_size"],
        total=result["total"],
    )


# ---------------------------------------------------------------------------
# GET /api/v1/questions/{question_id} — detail
# ---------------------------------------------------------------------------

@router.get("/questions/{question_id}", response_model=QuestionDetailResponse)
def get_question(question_id: str, db: Session = Depends(get_db)):
    """Return a single question detail with answers hidden."""
    detail = get_question_detail(db, question_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "QUESTION_NOT_FOUND",
                "message": "题目不存在",
                "details": None,
            },
        )

    # Build response from service result
    kp = detail.get("primary_knowledge_point", {})
    return QuestionDetailResponse(
        id=detail["id"],
        revision=detail["revision"],
        question_type=detail["question_type"],
        difficulty=detail["difficulty"],
        primary_knowledge_point=KnowledgePointRef(
            id=kp.get("id", ""),
            name=kp.get("name"),
        ),
        content=detail.get("content"),
        options=(
            [ChoiceOption(**opt) for opt in detail["options"]]
            if "options" in detail
            else None
        ),
        table_schema=detail.get("table_schema"),
        field_description=detail.get("field_description"),
        business_requirement=detail.get("business_requirement"),
    )