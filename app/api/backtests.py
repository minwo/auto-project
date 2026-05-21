from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from app.repository import CandidateRepository
from app.api.dependencies import get_repository

router = APIRouter(tags=["Backtests"])

@router.get("/backtests/summary")
def get_backtests_summary(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    repo: CandidateRepository = Depends(get_repository)
) -> dict[str, object]:
    summary = repo.get_backtest_summary(from_date, to_date)
    if summary is None:
        evaluations = repo.get_daily_scores(to_date)
        if not evaluations:
            raise HTTPException(status_code=404, detail="No backtest summary found for the requested range.")
        summary = repo.get_backtest_summary(to_date - timedelta(days=180), to_date)
        if summary is None:
            raise HTTPException(status_code=404, detail="No backtest summary found for the requested range.")
    return summary.as_dict()
