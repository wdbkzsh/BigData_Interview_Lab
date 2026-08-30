"""Attempt API — Task 4.4 + Step A feedback.

Endpoints:
    POST /api/v1/questions/{question_id}/attempts — submit an answer (idempotent)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.attempt import AttemptSubmitRequest, AttemptSubmitResponse
from app.services.attempt_service import (
    InvalidRevisionError,
    QuestionNotFoundError,
    create_attempt,
)

router = APIRouter(prefix="/api/v1")


def _build_submit_response(result: dict) -> AttemptSubmitResponse:
    """Build AttemptSubmitResponse from service result dict."""
    return AttemptSubmitResponse(
        attempt_id=result["attempt_id"],
        question_id=result["question_id"],
        question_revision=result["question_revision"],
        answer=result["answer"],
        status=result["status"],
        is_correct=result.get("is_correct"),
        score=result.get("score"),
        correct_answer=result.get("correct_answer"),
        reference_answer=result.get("reference_answer"),
        explanation=result.get("explanation"),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/questions/{question_id}/attempts
# ---------------------------------------------------------------------------

@router.post("/questions/{question_id}/attempts", response_model=AttemptSubmitResponse)
def submit_attempt(
    question_id: str,
    body: AttemptSubmitRequest,
    db: Session = Depends(get_db),
):
    """Submit an answer for a question. Idempotent via client_request_id."""
    if not body.answer or not body.answer.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_ANSWER",
                "message": "答案不能为空",
                "details": None,
            },
        )

    try:
        result = create_attempt(
            db,
            question_id=question_id,
            question_revision=body.question_revision,
            attempt_type=body.attempt_type,
            client_request_id=body.client_request_id,
            answer=body.answer,
        )
    except QuestionNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "QUESTION_NOT_FOUND",
                "message": "题目不存在",
                "details": None,
            },
        )
    except InvalidRevisionError:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_REVISION",
                "message": "指定的题目版本不存在",
                "details": None,
            },
        )

    response = _build_submit_response(result)

    # 200 if existed, 201 if new
    if result.get("existed"):
        return response

    return JSONResponse(status_code=201, content=response.model_dump())