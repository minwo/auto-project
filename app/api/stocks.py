from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from app.repository import CandidateRepository
from app.api.dependencies import get_repository
from app.api.market_payloads import market_regime_payload
from app.settings import load_settings

router = APIRouter(tags=["Stocks"])

@router.get("/stocks/{code}/signal-summary")
def get_signal_summary(
    code: str, 
    date_value: date = Query(alias="date"),
    repo: CandidateRepository = Depends(get_repository)
) -> dict[str, object]:
    evaluation = repo.get_signal_summary(code=code, score_date=date_value)
    if not evaluation:
        raise HTTPException(status_code=404, detail="No signal summary found for the requested stock/date.")
    return evaluation.to_signal_summary_payload()

@router.get("/stocks/{code}/price-chart")
def get_price_chart(
    code: str,
    to_date: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=60, ge=5, le=240),
    repo: CandidateRepository = Depends(get_repository)
) -> dict[str, object]:
    effective_date = to_date or repo.latest_score_date()
    if effective_date is None:
        raise HTTPException(status_code=404, detail="No price data found.")
    loader = getattr(repo, "get_price_chart", None)
    if not callable(loader):
        raise HTTPException(status_code=500, detail="Repository does not support price charts.")
    points = loader(code=code, to_date=effective_date, limit=limit)
    if not points:
        raise HTTPException(status_code=404, detail="No price chart data found for the requested stock.")
    return {
        "code": code,
        "to": effective_date.isoformat(),
        "items": [point.as_dict() for point in points],
    }

@router.get("/stocks/search")
def search_stocks(
    q: str = Query(default=""),
    date_value: date | None = Query(default=None, alias="date"),
    limit: int = Query(default=30, ge=1, le=50),
    auto_load: bool = Query(default=False, alias="autoLoad"),
    repo: CandidateRepository = Depends(get_repository)
) -> dict[str, object]:
    latest_trade_date = getattr(repo, "latest_trade_date", None)
    effective_date = date_value or repo.latest_score_date()
    if effective_date is None and callable(latest_trade_date):
        effective_date = latest_trade_date()
    if effective_date is None:
        raise HTTPException(status_code=404, detail="No daily candidate batch found for search.")

    evaluations = repo.search_daily_scores(score_date=effective_date, query=q, limit=limit)
    loaded = False
    load_error = None
    if auto_load and q.strip() and not evaluations:
        resolver = getattr(repo, "resolve_stock_codes", None)
        resolved_codes = []
        try:
            from app.on_demand_scoring import resolve_alias_codes, normalize_stock_code

            normalized_code = normalize_stock_code(q)
            resolved_codes = [normalized_code] if normalized_code else resolve_alias_codes(q)
            if not resolved_codes and callable(resolver):
                resolved_codes = list(resolver(q, limit=5))
        except Exception:
            resolved_codes = []

        if not resolved_codes:
            load_error = "종목명을 코드로 찾지 못했습니다. 별칭 파일에 종목코드를 추가해 주세요."
        elif not all(
            callable(getattr(repo, name, None))
            for name in [
                "upsert_daily_price_records",
                "fetch_price_history_for_batch",
                "fetch_market_warnings_for_date",
                "fetch_disclosures_for_date",
                "upsert_daily_scores",
            ]
        ):
            load_error = "On-demand scoring requires PostgreSQL repository."
        else:
            try:
                from app.on_demand_scoring import load_and_score_search_codes
                settings = load_settings()
                evaluations = load_and_score_search_codes(
                    repo=repo,
                    settings=settings,
                    query=q,
                    score_date=effective_date,
                )[:limit]
                loaded = bool(evaluations)
            except Exception as exc:
                load_error = str(exc)
    return {
        "date": effective_date.isoformat(),
        "query": q,
        "loaded": loaded,
        "loadError": load_error,
        "marketRegime": market_regime_payload(repo, effective_date, evaluations),
        "results": [item.to_search_payload() for item in evaluations],
    }
