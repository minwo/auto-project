from fastapi import APIRouter, Depends, Query
from app.repository import CandidateRepository
from app.api.dependencies import get_repository

router = APIRouter(tags=["Market"])

@router.get("/market/trading-dates")
def get_trading_dates(
    limit: int = Query(default=260, ge=1, le=520),
    repo: CandidateRepository = Depends(get_repository)
) -> dict[str, object]:
    loader = getattr(repo, "available_trade_dates", None)
    dates = loader(limit=limit) if callable(loader) else []
    latest = dates[0] if dates else None
    return {
        "latestDate": latest.isoformat() if latest else None,
        "dates": [item.isoformat() for item in dates],
    }
