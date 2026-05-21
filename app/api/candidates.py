from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from app.repository import CandidateRepository, select_top_candidates
from app.api.dependencies import get_repository

router = APIRouter(tags=["Candidates"])

@router.get("/candidates/daily")
def get_daily_candidates(
    date_value: date = Query(alias="date"),
    repo: CandidateRepository = Depends(get_repository)
) -> dict[str, object]:
    evaluations = repo.get_daily_scores(date_value)
    selected = select_top_candidates(evaluations, separate_profiles=True) if evaluations else []
    generated_at = max((item.generated_at for item in evaluations), default=None)
    return {
        "date": date_value.isoformat(),
        "horizon": "1-60d",
        "generatedAt": generated_at.isoformat() if generated_at else None,
        "emptyReason": None if selected else "적정 점수 이상 종목이 없습니다.",
        "candidates": [
            item.to_candidate_payload(rank=index)
            for index, item in enumerate(selected, start=1)
        ],
    }

@router.get("/top-picks/daily")
def get_daily_top_picks(
    as_of: date | None = Query(default=None, alias="asOf"),
    repo: CandidateRepository = Depends(get_repository)
) -> dict[str, object]:
    latest_trade_date = getattr(repo, "latest_trade_date", None)
    effective_date = as_of
    if effective_date is None and callable(latest_trade_date):
        effective_date = latest_trade_date()
    if effective_date is None:
        effective_date = repo.latest_score_date()
    if effective_date is None:
        raise HTTPException(status_code=404, detail="No daily candidate batch found for top picks.")
    refresh_top_picks = getattr(repo, "refresh_daily_top_picks", None)
    if not callable(refresh_top_picks):
        raise HTTPException(status_code=500, detail="Repository does not support daily top picks.")
    picks = refresh_top_picks(effective_date, retention_days=92)
    return {
        "asOf": effective_date.isoformat(),
        "retentionDays": 92,
        "items": [pick.as_dict() for pick in picks],
    }
