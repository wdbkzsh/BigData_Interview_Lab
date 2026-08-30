"""Review Policy — pure calculation, no DB access.

Implements review_v2 Self-Assessment Policy for short-answer questions.
See REVIEW_ALGORITHM.md §8 for the full specification.
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