from __future__ import annotations

from datetime import date, datetime, timezone

from app.domain import CatalystItem, StockSnapshot
from app.repository import BacktestSummary, CandidateRepository
from app.scoring import evaluate_snapshot


def make_snapshot(
    code: str,
    name: str,
    sector: str = "Semiconductor",
    trade_date: date = date(2026, 4, 23),
) -> StockSnapshot:
    return StockSnapshot(
        date=trade_date,
        code=code,
        name=name,
        market="KOSDAQ",
        sector=sector,
        is_common_stock=True,
        listed_days=180,
        avg_turnover_20d=2_000_000_000,
        avg_volume_20d=200_000,
        close=11_220.0,
        high=11_400.0,
        low=10_100.0,
        open_price=10_200.0,
        prev_close=10_000.0,
        volume=440_000.0,
        turnover=6_000_000_000.0,
        turnover_ratio_20d=3.0,
        volume_ratio_20d=2.2,
        return_3d_pct=5.0,
        sector_rising_peers=4,
        sector_turnover_ratio=1.6,
        has_leading_move=True,
        catalysts=[CatalystItem(kind="contract", title="공급 계약", url="https://example.com/catalyst")],
    )


def make_repository() -> CandidateRepository:
    repo = CandidateRepository()
    trade_date = date(2026, 4, 23)
    generated_at = datetime(2026, 4, 23, 7, 5, tzinfo=timezone.utc)

    snapshots = [
        make_snapshot("100001", "한빛세미", "Semiconductor", trade_date),
        make_snapshot("100003", "블루배터리", "Battery", trade_date),
        make_snapshot("100008", "솔라그리드", "Energy", trade_date),
    ]
    evaluations = [evaluate_snapshot(snapshot, generated_at=generated_at) for snapshot in snapshots]
    repo.upsert_daily_scores(trade_date, [item for item in evaluations if item is not None])
    repo.set_backtest_summary(
        trade_date.replace(year=2025, month=10, day=25),
        trade_date,
        BacktestSummary(
            top10_hit_rate=0.47,
            median_max_return=5.8,
            false_positive_rate=0.31,
            sector_concentration=0.36,
            warning_hit_rate=0.08,
        ),
    )
    return repo
