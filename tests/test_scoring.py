from __future__ import annotations

from datetime import date, datetime, timezone

from app.domain import CatalystItem, StockSnapshot
from app.repository import select_top_candidates
from app.scoring import evaluate_snapshot


def make_snapshot(
    code: str,
    sector: str = "Semiconductor",
    warning_level: str | None = None,
    speculative_theme: bool = False,
    rumor_news: bool = False,
    turnover_ratio_20d: float = 3.0,
    volume_ratio_20d: float = 2.2,
    return_3d_pct: float = 5.0,
    sector_rising_peers: int = 4,
    sector_turnover_ratio: float = 1.6,
    high: float = 11_400.0,
    low: float = 10_100.0,
    close: float = 11_220.0,
    listed_days: int = 180,
    avg_turnover_20d: float = 2_000_000_000,
) -> StockSnapshot:
    return StockSnapshot(
        date=date(2026, 4, 22),
        code=code,
        name=f"Sample-{code}",
        market="KOSDAQ",
        sector=sector,
        is_common_stock=True,
        listed_days=listed_days,
        avg_turnover_20d=avg_turnover_20d,
        avg_volume_20d=200_000,
        close=close,
        high=high,
        low=low,
        prev_close=10_000.0,
        volume=200_000 * volume_ratio_20d,
        turnover=2_000_000_000 * turnover_ratio_20d,
        turnover_ratio_20d=turnover_ratio_20d,
        volume_ratio_20d=volume_ratio_20d,
        return_3d_pct=return_3d_pct,
        sector_rising_peers=sector_rising_peers,
        sector_turnover_ratio=sector_turnover_ratio,
        has_leading_move=True,
        warning_level=warning_level,
        speculative_theme=speculative_theme,
        rumor_news=rumor_news,
        catalysts=[CatalystItem(kind="contract", title="공급 계약", url="https://example.com/catalyst")],
    )


def test_positive_catalyst_and_liquidity_raise_score() -> None:
    snapshot = make_snapshot("100001")
    evaluation = evaluate_snapshot(snapshot, generated_at=datetime.now(timezone.utc))

    assert evaluation is not None
    assert evaluation.breakdown.liquidity_score >= 20.0
    assert evaluation.breakdown.catalyst_score >= 8.0
    assert evaluation.score >= 60.0


def test_warning_and_heat_signals_apply_heavy_penalty() -> None:
    baseline = evaluate_snapshot(make_snapshot("100002"), generated_at=datetime.now(timezone.utc))
    risky = evaluate_snapshot(
        make_snapshot(
            "100003",
            warning_level="warning",
            speculative_theme=True,
            rumor_news=True,
            high=11_800.0,
            low=10_100.0,
            close=10_900.0,
            return_3d_pct=16.0,
        ),
        generated_at=datetime.now(timezone.utc),
    )

    assert baseline is not None
    assert risky is not None
    assert risky.breakdown.risk_penalty <= -20.0
    assert risky.score < baseline.score
    assert risky.risk_flags


def test_universe_filter_rejects_low_liquidity_and_new_listing() -> None:
    evaluation = evaluate_snapshot(
        make_snapshot(
            "100004",
            listed_days=40,
            avg_turnover_20d=500_000_000,
        ),
        generated_at=datetime.now(timezone.utc),
    )

    assert evaluation is None


def test_sector_cap_limits_results_to_three_names_per_sector() -> None:
    generated_at = datetime.now(timezone.utc)
    evaluations = []

    for index in range(5):
        evaluation = evaluate_snapshot(
            make_snapshot(code=f"20000{index}", sector="Semiconductor", turnover_ratio_20d=3.5 - (index * 0.2)),
            generated_at=generated_at,
        )
        assert evaluation is not None
        evaluations.append(evaluation)

    for index in range(4):
        evaluation = evaluate_snapshot(
            make_snapshot(code=f"30000{index}", sector="Biotech", turnover_ratio_20d=2.5 - (index * 0.1)),
            generated_at=generated_at,
        )
        assert evaluation is not None
        evaluations.append(evaluation)

    selected = select_top_candidates(evaluations, min_score=60.0, max_per_sector=3, limit=10)
    semiconductor_count = sum(1 for item in selected if item.snapshot.sector == "Semiconductor")

    assert semiconductor_count == 3
    assert len(selected) <= 10
