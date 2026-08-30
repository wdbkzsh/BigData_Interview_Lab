"""Review Policy — pure calculation, no DB access.

Implements review_v2 for both paths:
- Self-Assessment Policy (short-answer): REVIEW_ALGORITHM.md §8
- Score-Based Policy (choice, SQL): REVIEW_ALGORITHM.md §4-15
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional


@dataclass
class ReviewPolicyResult:
    """Result of applying a review policy."""

    mastery_state: str
    review_stage: int
    next_review_date: date
    consecutive_successes: int
    policy_version: str
    algorithm_state_json: str


# Self-Assessment mapping: mastery_state → (review_stage, interval_days)
_SELF_ASSESSMENT_MAP: dict[str, tuple[int, int]] = {
    "unmastered": (0, 1),
    "vague": (1, 2),
    "familiar": (3, 7),
    "mastered": (4, 14),
}


def apply_self_assessment(
    *,
    mastery_state: str,
    business_today: date,
    current_mastery_state: Optional[str] = None,
    current_consecutive_successes: int = 0,
    current_algorithm_state_json: Optional[str] = None,
) -> ReviewPolicyResult:
    """Apply self-assessment policy for short-answer questions.

    Args:
        mastery_state: User's self-assessed mastery (unmastered/vague/familiar/mastered)
        business_today: Current business date in APP_TIMEZONE
        current_mastery_state: Existing ReviewState mastery_state (None if first attempt)
        current_consecutive_successes: Existing consecutive_successes
        current_algorithm_state_json: Existing algorithm_state_json

    Returns:
        ReviewPolicyResult with all fields needed to upsert ReviewState
    """
    # Parse current review stage from algorithm_state_json
    current_stage = _parse_review_stage(current_algorithm_state_json)

    # Determine consecutive_successes
    if mastery_state in ("familiar", "mastered"):
        new_consecutive = current_consecutive_successes + 1
    else:
        new_consecutive = 0

    # Determine review_stage
    if mastery_state == "mastered":
        if current_mastery_state == "mastered" and current_stage >= 4:
            # Already mastered → mastered again → stage 5
            new_stage = 5
        else:
            # First time mastered or stage < 4
            new_stage = 4
    else:
        new_stage, _ = _SELF_ASSESSMENT_MAP[mastery_state]

    # Determine interval
    if new_stage == 5:
        interval_days = 30
    else:
        _, interval_days = _SELF_ASSESSMENT_MAP[mastery_state]

    next_review_date = business_today + timedelta(days=interval_days)

    # Build algorithm_state_json
    algo_state = {
        "review_stage": new_stage,
        "last_evaluation_mode": "self",
        "last_performance": None,
        "consecutive_excellent": 0,
    }

    return ReviewPolicyResult(
        mastery_state=mastery_state,
        review_stage=new_stage,
        next_review_date=next_review_date,
        consecutive_successes=new_consecutive,
        policy_version="review_v2",
        algorithm_state_json=json.dumps(algo_state),
    )


def _parse_review_stage(algorithm_state_json: Optional[str]) -> int:
    """Extract review_stage from algorithm_state_json, default 0."""
    if not algorithm_state_json:
        return 0
    try:
        data = json.loads(algorithm_state_json)
        return data.get("review_stage", 0)
    except (json.JSONDecodeError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Score-Based Policy (Choice / SQL)
# ---------------------------------------------------------------------------

_PERFORMANCE_THRESHOLDS = [
    (0.95, "excellent"),
    (0.80, "good"),
    (0.60, "partial"),
    (0.00, "fail"),
]

# stage → mastery_state (score-based path)
_STAGE_MASTERY: dict[int, str] = {
    0: "vague",
    1: "vague",
    2: "familiar",
    3: "familiar",
    4: "mastered",
    5: "mastered",
}

# performance → interval days
_PERFORMANCE_INTERVALS: dict[str, int] = {
    "fail": 1,
    "partial": 1,
    "good": 2,
    "excellent": 2,
}


def classify_score(score_ratio: float) -> str:
    """Classify score_ratio into performance level."""
    for threshold, label in _PERFORMANCE_THRESHOLDS:
        if score_ratio >= threshold:
            return label
    return "fail"


def apply_score_based(
    *,
    final_score: float,
    max_score: float,
    business_today: date,
    current_mastery_state: Optional[str] = None,
    current_consecutive_successes: int = 0,
    current_algorithm_state_json: Optional[str] = None,
) -> ReviewPolicyResult:
    """Apply score-based policy for choice/SQL questions.

    Args:
        final_score: Earned score
        max_score: Maximum possible score
        business_today: Current business date in APP_TIMEZONE
        current_mastery_state: Existing mastery_state (None if first attempt)
        current_consecutive_successes: Existing consecutive_successes
        current_algorithm_state_json: Existing algorithm_state_json

    Returns:
        ReviewPolicyResult with all fields needed to upsert ReviewState
    """
    score_ratio = final_score / max_score if max_score > 0 else 0.0
    performance = classify_score(score_ratio)

    current_stage = _parse_review_stage(current_algorithm_state_json)
    current_algo = _parse_algorithm_state(current_algorithm_state_json)
    consecutive_excellent = current_algo.get("consecutive_excellent", 0)

    # Determine new stage
    if performance == "fail":
        new_stage = 0
        new_consecutive = 0
        new_consecutive_excellent = 0
        mastery = "unmastered"

    elif performance == "partial":
        new_stage = max(0, current_stage - 1)
        new_consecutive = 0
        new_consecutive_excellent = 0
        mastery = "vague"

    elif performance == "good":
        new_stage = min(current_stage + 1, 5)
        new_consecutive = current_consecutive_successes + 1
        new_consecutive_excellent = 0
        mastery = _STAGE_MASTERY.get(new_stage, "vague")

    else:  # excellent
        # Consecutive excellent acceleration
        new_consecutive_excellent = consecutive_excellent + 1
        if new_consecutive_excellent >= 2:
            new_stage = min(current_stage + 2, 5)
        else:
            new_stage = min(current_stage + 1, 5)
        new_consecutive = current_consecutive_successes + 1
        mastery = _STAGE_MASTERY.get(new_stage, "vague")

    # Special: fail always → unmastered regardless of stage
    if performance == "fail":
        mastery = "unmastered"

    # Interval from stage
    interval_days = _STAGE_INTERVALS.get(new_stage, 1)

    next_review_date = business_today + timedelta(days=interval_days)

    algo_state = {
        "review_stage": new_stage,
        "last_evaluation_mode": "score",
        "last_performance": performance,
        "consecutive_excellent": new_consecutive_excellent,
    }

    return ReviewPolicyResult(
        mastery_state=mastery,
        review_stage=new_stage,
        next_review_date=next_review_date,
        consecutive_successes=new_consecutive,
        policy_version="review_v2",
        algorithm_state_json=json.dumps(algo_state),
    )


# stage → interval days (score-based)
_STAGE_INTERVALS: dict[int, int] = {
    0: 1,
    1: 2,
    2: 4,
    3: 7,
    4: 14,
    5: 30,
}


def _parse_algorithm_state(algorithm_state_json: Optional[str]) -> dict[str, Any]:
    """Parse full algorithm_state_json, default empty dict."""
    if not algorithm_state_json:
        return {}
    try:
        return json.loads(algorithm_state_json)
    except (json.JSONDecodeError, TypeError):
        return {}