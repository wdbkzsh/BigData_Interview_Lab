"""Question API — Phase 7.

Endpoints:
    GET /api/v1/questions       — question list with filters + ReviewState + domain
    GET /api/v1/questions/{id}  — single question detail (answer hidden)
    GET /api/v1/domains         — list all domains (root KnowledgePoints)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.question import (
    ChoiceOption,
    KnowledgePointRef,
    QuestionDetailResponse,
    QuestionListItem,
    QuestionListResponse,
    ReviewStateSummary,
)
from app.services.question_service import (
    get_question_detail,
    list_domains,
    list_questions,
)

router = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------------------
# GET /api/v1/domains — list domains
# ---------------------------------------------------------------------------

@router.get("/domains")
def get_domains(db: Session = Depends(get_db)):
    """List all domains (root KnowledgePoints)."""
    return list_domains(db)


# ---------------------------------------------------------------------------
# GET /api/v1/questions — list
# ---------------------------------------------------------------------------

@router.get("/questions", response_model=QuestionListResponse)
def get_questions(
    knowledge_point_id: Optional[str] = None,
    question_type: Optional[str] = None,
    difficulty: Optional[int] = None,
    mastery_state: Optional[str] = None,
    domain_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """Return a filtered, paginated list of questions with ReviewState and domain."""
    result = list_questions(
        db,
        knowledge_point_id=knowledge_point_id,
        question_type=question_type,
        difficulty=difficulty,
        mastery_state=mastery_state,
        domain_id=domain_id,
        page=page,
        page_size=page_size,
    )

    items = []
    for item in result["items"]:
        rs = item.get("review_state")
        domain = item.get("domain")
        items.append(QuestionListItem(
            id=item["id"],
            title=item["title"],
            question_type=item["question_type"],
            difficulty=item["difficulty"],
            primary_knowledge_point=KnowledgePointRef(
                id=item["primary_knowledge_point"]["id"],
                name=item["primary_knowledge_point"]["name"],
            ),
            domain=KnowledgePointRef(
                id=domain["id"],
                name=domain["name"],
            ) if domain else None,
            review_state=ReviewStateSummary(
                mastery_state=rs["mastery_state"],
                next_review_date=rs["next_review_date"],
            ) if rs else None,
            pending_self_assessment_attempt_id=item.get("pending_self_assessment_attempt_id"),
        ))

    return QuestionListResponse(
        items=items,
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