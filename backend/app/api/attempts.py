"""Attempt API — Task 4.4 + Step A feedback + Phase 5 self-assessment.

Endpoints:
    POST /api/v1/questions/{question_id}/attempts — submit an answer (idempotent)
    POST /api/v1/attempts/{attempt_id}/self-assessment — self-assessment
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.attempt import (
    AttemptSubmitRequest,
    AttemptSubmitResponse,
    ReviewStateSnapshot,
    SelfAssessmentRequest,
    SelfAssessmentResponse,
)
from app.services.attempt_service import (
    AttemptNotFoundError,
    InvalidRevisionError,
    InvalidSelfAssessmentError,
    QuestionNotFoundError,
    SelfAssessmentConflictError,
    create_attempt,
    submit_self_assessment,
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


# ---------------------------------------------------------------------------
# POST /api/v1/attempts/{attempt_id}/self-assessment
# ---------------------------------------------------------------------------

@router.post(
    "/attempts/{attempt_id}/self-assessment",
    response_model=SelfAssessmentResponse,
)
def self_assessment(
    attempt_id: int,
    body: SelfAssessmentRequest,
    db: Session = Depends(get_db),
):
    """Submit self-assessment for a short-answer attempt."""
    try:
        result = submit_self_assessment(
            db,
            attempt_id=attempt_id,
            mastery_state=body.mastery_state,
        )
    except AttemptNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ATTEMPT_NOT_FOUND",
                "message": "Attempt 不存在",
                "details": None,
            },
        )
    except InvalidSelfAssessmentError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_SELF_ASSESSMENT",
                "message": str(e),
                "details": None,
            },
        )
    except SelfAssessmentConflictError:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SELF_ASSESSMENT_ALREADY_COMPLETED",
                "message": "该 Attempt 已完成自评，不能修改",
                "details": None,
            },
        )

    rs = result.get("review_state")
    response = SelfAssessmentResponse(
        attempt_id=result["attempt_id"],
        status=result["status"],
        self_assessed_mastery_state=result["self_assessed_mastery_state"],
        review_state=ReviewStateSnapshot(
            mastery_state=rs["mastery_state"],
            next_review_date=rs["next_review_date"],
            policy_version=rs["policy_version"],
        ),
    )

    # 200 if existed (idempotent), 201 if new
    if result.get("existed"):
        return response

    return JSONResponse(status_code=201, content=response.model_dump(mode="json"))