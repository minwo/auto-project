from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from tests.factories import make_repository


def test_dashboard_page_renders_html() -> None:
    repo = make_repository()
    client = TestClient(create_app(repo))

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "종목을 검색하고" in response.text


def test_search_endpoint_returns_matching_stock() -> None:
    repo = make_repository()
    latest_date = repo.latest_score_date()
    assert latest_date is not None
    client = TestClient(create_app(repo))

    response = client.get(
        "/api/stocks/search",
        params={"date": latest_date.isoformat(), "q": "한빛"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["results"]
    assert body["results"][0]["code"] == "100001"


def test_system_status_endpoint_reports_repository_mode() -> None:
    repo = make_repository()
    client = TestClient(create_app(repo))

    response = client.get("/api/system/status")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "CandidateRepository"
    assert body["databaseConfigured"] is False
    assert body["latestScoreDate"] == "2026-04-23"
