from __future__ import annotations

from datetime import date, timedelta

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "FastAPI is required to run the API. Install dependencies with `pip install -e .`."
    ) from exc

from app.postgres_repository import create_postgres_repository
from app.repository import CandidateRepository, UnavailableRepository, select_top_candidates
from app.settings import load_settings
from app.ui import render_dashboard_html


def build_repository() -> CandidateRepository:
    settings = load_settings()
    if settings.use_database:
        try:
            return create_postgres_repository(settings.database_url)
        except Exception as exc:
            return UnavailableRepository(str(exc), database_configured=True)
    return CandidateRepository()


def create_app(repository: CandidateRepository | None = None) -> FastAPI:
    repo = repository or build_repository()
    app = FastAPI(
        title="Domestic Stock MVP",
        description="EOD-based next-day watchlist candidate selector for KOSPI/KOSDAQ equities.",
        version="0.1.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        latest_date = repo.latest_score_date()
        initial_date = latest_date or date.today()
        return render_dashboard_html(initial_date.isoformat())

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/system/status")
    def system_status() -> dict[str, object]:
        latest_date = repo.latest_score_date()
        response: dict[str, object] = {
            "mode": repo.__class__.__name__,
            "databaseConfigured": getattr(repo, "database_configured", repo.__class__.__name__ == "PostgresCandidateRepository"),
            "latestScoreDate": latest_date.isoformat() if latest_date else None,
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

    @app.get("/api/candidates/daily")
    def get_daily_candidates(
        date_value: date = Query(alias="date"),
    ) -> dict[str, object]:
        evaluations = repo.get_daily_scores(date_value)
        if not evaluations:
            raise HTTPException(status_code=404, detail="No daily candidate batch found for the requested date.")

        selected = select_top_candidates(evaluations)
        generated_at = max(item.generated_at for item in evaluations)
        return {
            "date": date_value.isoformat(),
            "horizon": "1-3d",
            "generatedAt": generated_at.isoformat(),
            "candidates": [
                item.to_candidate_payload(rank=index)
                for index, item in enumerate(selected, start=1)
            ],
        }

    @app.get("/api/stocks/{code}/signal-summary")
    def get_signal_summary(code: str, date_value: date = Query(alias="date")) -> dict[str, object]:
        evaluation = repo.get_signal_summary(code=code, score_date=date_value)
        if not evaluation:
            raise HTTPException(status_code=404, detail="No signal summary found for the requested stock/date.")
        return evaluation.to_signal_summary_payload()

    @app.get("/api/stocks/search")
    def search_stocks(
        q: str = Query(default=""),
        date_value: date | None = Query(default=None, alias="date"),
        limit: int = Query(default=30, ge=1, le=50),
    ) -> dict[str, object]:
        effective_date = date_value or repo.latest_score_date()
        if effective_date is None:
            raise HTTPException(status_code=404, detail="No daily candidate batch found for search.")

        evaluations = repo.search_daily_scores(score_date=effective_date, query=q, limit=limit)
        return {
            "date": effective_date.isoformat(),
            "query": q,
            "results": [item.to_search_payload() for item in evaluations],
        }

    @app.get("/api/backtests/summary")
    def get_backtests_summary(
        from_date: date = Query(alias="from"),
        to_date: date = Query(alias="to"),
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

    return app


app = create_app()
