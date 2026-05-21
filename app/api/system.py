from fastapi import APIRouter, Depends
from app.repository import CandidateRepository
from app.api.dependencies import get_repository

router = APIRouter(tags=["System"])

@router.get("/system/status")
def system_status(repo: CandidateRepository = Depends(get_repository)) -> dict[str, object]:
    latest_date = repo.latest_score_date()
    latest_trade_date = None
    latest_trade_date_loader = getattr(repo, "latest_trade_date", None)
    if callable(latest_trade_date_loader):
        latest_trade_date = latest_trade_date_loader()
    response: dict[str, object] = {
        "mode": repo.__class__.__name__,
        "databaseConfigured": getattr(repo, "database_configured", repo.__class__.__name__ == "PostgresCandidateRepository"),
        "latestScoreDate": latest_date.isoformat() if latest_date else None,
        "latestTradeDate": latest_trade_date.isoformat() if latest_trade_date else None,
    }
    error_message = getattr(repo, "error_message", None)
    if error_message:
        response["error"] = error_message
    ping = getattr(repo, "ping", None)
    table_counts = getattr(repo, "table_counts", None)
    if callable(ping):
        response["databaseConnected"] = ping()
    if callable(table_counts):
        response["tableCounts"] = table_counts()
    return response
