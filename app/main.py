from __future__ import annotations

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "FastAPI is required to run the API. Install dependencies with `pip install -e .`."
    ) from exc

from app.repository import CandidateRepository
from app.api.dependencies import set_repository, get_repository, build_repository
from app.api.router import api_router

def create_app(repository: CandidateRepository | None = None) -> FastAPI:
    repo = repository or build_repository()
    set_repository(repo)

    app = FastAPI(
        title="Domestic Stock MVP",
        description="EOD-based next-day watchlist candidate selector for KOSPI/KOSDAQ equities.",
        version="0.1.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return """
        <!doctype html>
        <html lang="ko">
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <meta http-equiv="refresh" content="0; url=http://127.0.0.1:3000">
            <title>국내주식 후보 분석</title>
          </head>
          <body>
            <p hidden>종목을 검색하고 분석 결과를 확인합니다.</p>
            <a href="http://127.0.0.1:3000">국내주식 후보 분석 열기</a>
          </body>
        </html>
        """

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)

    return app

app = create_app()
