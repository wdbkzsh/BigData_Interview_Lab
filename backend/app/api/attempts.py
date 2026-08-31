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
    AssessmentData,
    AttemptDetailResponse,
    AttemptSubmitRequest,
    AttemptSubmitResponse,
    PendingAttemptsResponse,
    ReviewStateSnapshot,
    SQLConfirmRequest,
    SQLConfirmResponse,
    SQLDisputeRequest,
    SQLDisputeResponse,
    SQLRegradeResponse,
    SelfAssessmentRequest,
    SelfAssessmentResponse,
)
from app.services.attempt_service import (
    AttemptNotFoundError,
    InvalidConfirmError,
    InvalidRevisionError,
    InvalidSelfAssessmentError,
    QuestionNotFoundError,
    SQLConfirmConflictError,
    SQLRegradeConflictError,
    SelfAssessmentConflictError,
    confirm_sql_attempt,
    create_attempt,
    dispute_sql_attempt,
    get_attempt_detail,
    get_pending_attempts,
    regrade_sql_attempt,
    submit_self_assessment,
)

router = APIRouter(prefix="/api/v1")


def _build_submit_response(result: dict) -> AttemptSubmitResponse:
    """Build AttemptSubmitResponse from service result dict."""
    assessment_data = None
    raw_assessment = result.get("assessment")
    if raw_assessment:
        assessment_data = AssessmentData(**raw_assessment)

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
        assessment=assessment_data,
        expected_sql=result.get("expected_sql"),
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


# ---------------------------------------------------------------------------
# POST /api/v1/attempts/{attempt_id}/confirm — SQL accept/adjust
# ---------------------------------------------------------------------------

@router.post(
    "/attempts/{attempt_id}/confirm",
    response_model=SQLConfirmResponse,
)
def confirm_attempt(
    attempt_id: int,
    body: SQLConfirmRequest,
    db: Session = Depends(get_db),
):
    """Confirm a SQL attempt (accept or adjust)."""
    try:
        result = confirm_sql_attempt(
            db,
            attempt_id=attempt_id,
            action=body.action,
            final_score=body.final_score,
        )
    except AttemptNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt 不存在", "details": None},
        )
    except InvalidConfirmError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_CONFIRM", "message": str(e), "details": None},
        )
    except SQLConfirmConflictError:
        raise HTTPException(
            status_code=409,
            detail={"code": "SQL_CONFIRM_ALREADY_COMPLETED", "message": "该 Attempt 已完成确认", "details": None},
        )

    response = SQLConfirmResponse(
        attempt_id=result["attempt_id"],
        status=result["status"],
        final_score=result.get("final_score"),
        max_score=result.get("max_score"),
        final_score_source=result.get("final_score_source"),
        mastery_state=result.get("mastery_state"),
        next_review_date=result.get("next_review_date"),
        policy_version=result.get("policy_version"),
    )

    if result.get("existed"):
        return response

    return JSONResponse(status_code=201, content=response.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# POST /api/v1/attempts/{attempt_id}/regrade — SQL regrade
# ---------------------------------------------------------------------------

@router.post(
    "/attempts/{attempt_id}/regrade",
    response_model=SQLRegradeResponse,
)
def regrade_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
):
    """Regrade a SQL attempt."""
    from app.llm.factory import create_provider
    from app.llm.service import LLMService

    try:
        provider = create_provider()
        llm_service = LLMService(provider)
        result = regrade_sql_attempt(db, attempt_id=attempt_id, llm_service=llm_service)
    except AttemptNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt 不存在", "details": None},
        )
    except InvalidConfirmError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_REGRADE", "message": str(e), "details": None},
        )
    except SQLRegradeConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "SQL_REGRADE_CONFLICT", "message": str(e), "details": None},
        )

    assessment_data = None
    raw = result.get("assessment")
    if raw:
        assessment_data = AssessmentData(**raw)

    return SQLRegradeResponse(
        attempt_id=result["attempt_id"],
        status=result["status"],
        assessment=assessment_data,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/attempts/{attempt_id}/dispute — SQL dispute
# ---------------------------------------------------------------------------

@router.post(
    "/attempts/{attempt_id}/dispute",
    response_model=SQLDisputeResponse,
)
def dispute_attempt(
    attempt_id: int,
    body: SQLDisputeRequest,
    db: Session = Depends(get_db),
):
    """Mark a SQL attempt as disputed."""
    if not body.reason or not body.reason.strip():
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_REASON", "message": "争议原因不能为空", "details": None},
        )

    try:
        result = dispute_sql_attempt(
            db,
            attempt_id=attempt_id,
            reason=body.reason.strip()[:500],
        )
    except AttemptNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt 不存在", "details": None},
        )
    except InvalidConfirmError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_DISPUTE", "message": str(e), "details": None},
        )
    except SQLRegradeConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "SQL_DISPUTE_CONFLICT", "message": str(e), "details": None},
        )

    return SQLDisputeResponse(
        attempt_id=result["attempt_id"],
        status=result["status"],
    )


# ---------------------------------------------------------------------------
# GET /api/v1/attempts/pending — pending self-assessments
# MUST be before /attempts/{attempt_id} to avoid route conflict
# ---------------------------------------------------------------------------

@router.get("/attempts/pending", response_model=PendingAttemptsResponse)
def list_pending(db: Session = Depends(get_db)):
    """List all attempts awaiting self-assessment."""
    result = get_pending_attempts(db)
    return PendingAttemptsResponse(**result)


# ---------------------------------------------------------------------------
# GET /api/v1/attempts/{attempt_id} — attempt detail
# ---------------------------------------------------------------------------

@router.get("/attempts/{attempt_id}", response_model=AttemptDetailResponse)
def get_attempt(attempt_id: int, db: Session = Depends(get_db)):
    """Get attempt detail. For awaiting SA, includes reference_answer."""
    detail = get_attempt_detail(db, attempt_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ATTEMPT_NOT_FOUND",
                "message": "Attempt 不存在",
                "details": None,
            },
        )
    return AttemptDetailResponse(**detail)