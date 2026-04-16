"""
backend/app/simulation/adapters/force_mix_adapter.py

투입 병력 편성(Force Mix) 평가 어댑터.

인터페이스:
    입력: mission_config, force_mix_candidates, risk_summary
    출력: ForceMixResult (candidate_scores, selected_recommendation)

현재는 더미 구현 (ugv_count가 많을수록 높은 점수).
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CandidateScore:
    candidate_id: int
    candidate_name: str
    score: float
    rationale: dict


@dataclass
class ForceMixResult:
    candidate_scores: list[CandidateScore] = field(default_factory=list)
    selected_candidate_id: int | None = None


def evaluate_force_mix(
    mission_config: dict,
    candidates: list[dict],
    risk_summary: dict[str, Any],
) -> ForceMixResult:
    """
    후보군 점수 계산.
    현재: ugv_count 기준 더미 점수.
    """
    if not candidates:
        return ForceMixResult()

    scores = []
    for c in candidates:
        score = min(1.0, c.get("ugv_count", 1) / 10.0)
        scores.append(
            CandidateScore(
                candidate_id=c["id"],
                candidate_name=c.get("candidate_name", ""),
                score=round(score, 3),
                rationale={"basis": "dummy_ugv_count_ratio"},
            )
        )

    scores.sort(key=lambda x: x.score, reverse=True)
    selected_id = scores[0].candidate_id if scores else None

    return ForceMixResult(candidate_scores=scores, selected_candidate_id=selected_id)
