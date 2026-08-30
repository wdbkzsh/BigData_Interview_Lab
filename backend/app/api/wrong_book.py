"""Wrong Book API — Phase 6.

Endpoints:
    GET  /api/v1/wrong-book
    PUT  /api/v1/questions/{question_id}/wrong-book-preference
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.question import Question
from app.db.session import get_db
from app.schemas.wrong_book import (
    WrongBookItem,
    WrongBookPreferenceRequest,
    WrongBookResponse,
)
from app.services.wrong_book_service import query_wrong_book, set_wrong_book_preference

router = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------------------
# GET /api/v1/wrong-book
# ---------------------------------------------------------------------------

@router.get("/wrong-book", response_model=WrongBookResponse)
def get_wrong_book(
    knowledge_point_id: Optional[str] = None,
    question_type: Optional[str] = None,
    mastery_state: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """Query wrong book with filters."""
    result = query_wrong_book(
        db,
        knowledge_point_id=knowledge_point_id,
        question_type=question_type,
        mastery_state=mastery_state,
        page=page,
        page_size=page_size,
    )
    return WrongBookResponse(
        items=[WrongBookItem(**item) for item in result["items"]],
        page=result["page"],
        page_size=result["page_size"],
        total=result["total"],
    )


# ---------------------------------------------------------------------------
# PUT /api/v1/questions/{question_id}/wrong-book-preference
# ---------------------------------------------------------------------------

@router.put(
    "/questions/{question_id}/wrong-book-preference",
    response_model=dict,
)
def update_wrong_book_preference(
    question_id: str,
    body: WrongBookPreferenceRequest,
    db: Session = Depends(get_db),
):
    """Set wrong book preference. Idempotent."""
    # Validate question exists
    q = db.query(Question.id).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "QUESTION_NOT_FOUND",
                "message": "题目不存在",
                "details": None,
            },
        )

    result = set_wrong_book_preference(
        db,
        question_id=question_id,
        mode=body.mode,
    )
    return result