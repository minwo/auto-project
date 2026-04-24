from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

import app.main as app_main
from app.main import build_repository, create_app
from app.repository import CandidateRepository, UnavailableRepository


def test_build_repository_returns_empty_repository_when_database_is_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    repo = build_repository()

    assert isinstance(repo, CandidateRepository)
    assert repo.latest_score_date() is None
    assert repo.search_daily_scores(score_date=date(2026, 4, 23)) == []


def test_dashboard_renders_html_without_real_data(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    client = TestClient(create_app(build_repository()))
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_build_repository_returns_unavailable_repository_when_database_connection_fails(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://bad:bad@localhost:5432/domestic_stock_mvp")

    def _raise(_url: str):
        raise RuntimeError("database connection failed")

    monkeypatch.setattr(app_main, "create_postgres_repository", _raise)

    repo = build_repository()

    assert isinstance(repo, UnavailableRepository)
    assert repo.database_configured is True
    assert "database connection failed" in repo.error_message
