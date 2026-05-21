from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.main import create_app
from app.repository import CandidateRepository
from app.scoring import evaluate_snapshot
from tests.factories import make_repository, make_snapshot


class TopPickAsOfRepository:
    def __init__(self, repo, latest_trade_date):
        self.repo = repo
        self._latest_trade_date = latest_trade_date
        self.refresh_as_of = None

    def latest_score_date(self):
        return self.repo.latest_score_date()

    def latest_trade_date(self):
        return self._latest_trade_date

    def refresh_daily_top_picks(self, as_of, retention_days=92):
        self.refresh_as_of = as_of
        return self.repo.refresh_daily_top_picks(as_of, retention_days)


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
    assert body["results"][0]["close"] == 11220.0
    assert body["results"][0]["prevClose"] == 10000.0
    assert body["results"][0]["dayChangePct"] == 12.2
    assert body["results"][0]["targetPrice"] > body["results"][0]["close"]
    assert body["results"][0]["targetUpsidePct"] > 0


def test_system_status_endpoint_reports_repository_mode() -> None:
    repo = make_repository()
    client = TestClient(create_app(repo))

    response = client.get("/api/system/status")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "CandidateRepository"
    assert body["databaseConfigured"] is False
    assert body["latestScoreDate"] == "2026-04-23"


def test_trading_dates_endpoint_returns_candidate_score_dates_only() -> None:
    repo = make_repository()
    client = TestClient(create_app(repo))

    response = client.get("/api/market/trading-dates")

    assert response.status_code == 200
    body = response.json()
    assert body["latestDate"] == "2026-04-23"
    assert body["dates"] == ["2026-04-23"]


def test_daily_top_picks_endpoint_returns_one_pick_per_day() -> None:
    repo = make_repository()
    client = TestClient(create_app(repo))

    response = client.get("/api/top-picks/daily")

    assert response.status_code == 200
    body = response.json()
    assert body["asOf"] == "2026-04-23"
    assert body["retentionDays"] == 92
    assert len(body["items"]) == 1
    assert body["items"][0]["pickDate"] == "2026-04-23"
    assert body["items"][0]["recommendationStartDate"] == "2026-04-23"
    assert body["items"][0]["recommendationEndDate"] == "2026-04-23"
    assert body["items"][0]["code"] == "100001"
    assert body["items"][0]["baseClose"] == 11220.0
    assert body["items"][0]["latestClose"] == 11220.0
    assert body["items"][0]["changePct"] == 0.0


def test_daily_top_picks_endpoint_deduplicates_repeated_codes_by_first_pick_date() -> None:
    repo = CandidateRepository()
    first_date = date(2026, 4, 23)
    second_date = date(2026, 4, 24)
    generated_at = datetime(2026, 4, 24, 7, 5, tzinfo=timezone.utc)

    first_pick = make_snapshot("100001", "Repeat Leader", "Semiconductor", first_date)
    repeat_pick = replace(
        make_snapshot("100001", "Repeat Leader", "Semiconductor", second_date),
        close=12_000.0,
        high=12_200.0,
        low=11_600.0,
        open_price=11_800.0,
        prev_close=11_220.0,
    )
    next_new_pick = replace(
        make_snapshot("100002", "Fresh Candidate", "Battery", second_date),
        catalysts=[],
        turnover_ratio_20d=1.1,
        volume_ratio_20d=1.0,
        return_3d_pct=1.0,
        sector_rising_peers=0,
        sector_turnover_ratio=1.0,
    )

    first_eval = evaluate_snapshot(first_pick, generated_at=generated_at)
    repeat_eval = evaluate_snapshot(repeat_pick, generated_at=generated_at)
    next_eval = evaluate_snapshot(next_new_pick, generated_at=generated_at)
    assert first_eval is not None
    assert repeat_eval is not None
    assert next_eval is not None

    repo.upsert_daily_scores(first_date, [first_eval])
    repo.upsert_daily_scores(second_date, [repeat_eval, next_eval])

    client = TestClient(create_app(repo))
    response = client.get("/api/top-picks/daily")

    assert response.status_code == 200
    items = response.json()["items"]
    repeat_items = [item for item in items if item["code"] == "100001"]
    assert len(repeat_items) == 1
    assert repeat_items[0]["pickDate"] == "2026-04-23"
    assert repeat_items[0]["recommendationStartDate"] == "2026-04-23"
    assert repeat_items[0]["recommendationEndDate"] == "2026-04-24"
    assert repeat_items[0]["latestDate"] == "2026-04-24"
    assert repeat_items[0]["latestClose"] == 12000.0
    assert repeat_items[0]["changePct"] > 0
    assert any(item["pickDate"] == "2026-04-24" and item["code"] == "100002" for item in items)


def test_daily_top_picks_endpoint_uses_latest_trade_date_for_tracking_as_of() -> None:
    base_repo = make_repository()
    repo = TopPickAsOfRepository(base_repo, latest_trade_date=date(2026, 4, 24))
    client = TestClient(create_app(repo))

    response = client.get("/api/top-picks/daily")

    assert response.status_code == 200
    body = response.json()
    assert body["asOf"] == "2026-04-24"
    assert repo.refresh_as_of == date(2026, 4, 24)


def test_daily_candidates_endpoint_returns_empty_payload_for_no_candidates() -> None:
    repo = make_repository()
    client = TestClient(create_app(repo))

    response = client.get("/api/candidates/daily", params={"date": "2026-04-24"})

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-04-24"
    assert body["generatedAt"] is None
    assert body["emptyReason"] == "적정 점수 이상 종목이 없습니다."
    assert body["candidates"] == []


def test_price_chart_endpoint_returns_price_points() -> None:
    repo = make_repository()
    client = TestClient(create_app(repo))

    response = client.get("/api/stocks/100001/price-chart", params={"to": "2026-04-23", "limit": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "100001"
    assert body["items"]
    assert body["items"][0]["date"] == "2026-04-23"
    assert body["items"][0]["close"] == 11220.0
    assert body["items"][0]["volume"] > 0
