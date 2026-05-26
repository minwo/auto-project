from __future__ import annotations

from datetime import date, datetime, timezone

from app.batch import (
    DisclosureRow,
    NewsRow,
    PriceHistoryRow,
    WarningRow,
    build_snapshots_for_date,
    evaluate_daily_batch,
    evaluate_daily_batch_with_surge,
)
from app.repository import select_top_candidates


def make_price_row(
    *,
    code: str,
    trade_date: date,
    close_price: float,
    turnover: float,
    volume: float,
    sector: str = "반도체",
    market: str = "KOSDAQ",
    name: str | None = None,
    listed_at: date | None = date(2025, 10, 1),
    is_common_stock: bool = True,
) -> PriceHistoryRow:
    return PriceHistoryRow(
        code=code,
        name=name or code,
        market=market,
        sector=sector,
        listed_at=listed_at,
        is_common_stock=is_common_stock,
        is_preferred=False,
        is_etf=False,
        is_etn=False,
        is_spac=False,
        trade_date=trade_date,
        open_price=close_price * 0.97,
        high_price=close_price * 1.03,
        low_price=close_price * 0.96,
        close_price=close_price,
        volume=volume,
        turnover=turnover,
    )


def test_build_snapshots_for_date_computes_ratios_and_sector_context() -> None:
    score_date = date(2026, 4, 24)
    rows = [
        make_price_row(code="111111", name="한빛세미", trade_date=score_date, close_price=12000, turnover=6_000_000_000, volume=500_000),
        make_price_row(code="111111", trade_date=date(2026, 4, 23), close_price=11200, turnover=2_000_000_000, volume=220_000),
        make_price_row(code="111111", trade_date=date(2026, 4, 22), close_price=10800, turnover=1_900_000_000, volume=210_000),
        make_price_row(code="111111", trade_date=date(2026, 4, 21), close_price=10400, turnover=1_800_000_000, volume=205_000),
        make_price_row(code="222222", name="칩웨이브", trade_date=score_date, close_price=8400, turnover=3_000_000_000, volume=260_000),
        make_price_row(code="222222", trade_date=date(2026, 4, 23), close_price=8000, turnover=1_500_000_000, volume=180_000),
        make_price_row(code="222222", trade_date=date(2026, 4, 22), close_price=7900, turnover=1_450_000_000, volume=176_000),
        make_price_row(code="222222", trade_date=date(2026, 4, 21), close_price=7800, turnover=1_400_000_000, volume=170_000),
    ]

    snapshots = build_snapshots_for_date(score_date=score_date, price_rows=rows)

    assert len(snapshots) == 2
    first = next(item for item in snapshots if item.code == "111111")
    assert first.turnover_ratio_20d > 2.0
    assert first.volume_ratio_20d > 2.0
    assert first.return_3d_pct > 10.0
    assert first.sector_rising_peers == 1
    assert first.has_leading_move is True


def test_evaluate_daily_batch_uses_disclosures_and_warnings() -> None:
    score_date = date(2026, 4, 24)
    rows = [
        make_price_row(code="333333", name="뉴로바이오", trade_date=score_date, close_price=15500, turnover=5_500_000_000, volume=440_000, sector="바이오"),
        make_price_row(code="333333", trade_date=date(2026, 4, 23), close_price=14900, turnover=2_000_000_000, volume=200_000, sector="바이오"),
        make_price_row(code="333333", trade_date=date(2026, 4, 22), close_price=14500, turnover=1_900_000_000, volume=190_000, sector="바이오"),
        make_price_row(code="333333", trade_date=date(2026, 4, 21), close_price=14100, turnover=1_850_000_000, volume=185_000, sector="바이오"),
    ]
    disclosures = [
        DisclosureRow(
            code="333333",
            report_name="단일판매ㆍ공급계약체결",
            report_type="contract",
            material_tag="contract",
            url="https://example.com/disclosure",
            is_material=True,
        )
    ]
    warnings = [
        WarningRow(code="333333", warning_level="attention", is_halted=False, is_under_management=False)
    ]

    evaluations = evaluate_daily_batch(
        score_date=score_date,
        price_rows=rows,
        warning_rows=warnings,
        disclosure_rows=disclosures,
        generated_at=datetime.now(timezone.utc),
    )

    assert len(evaluations) == 1
    evaluation = evaluations[0]
    assert evaluation.breakdown.catalyst_score >= 8.0
    assert evaluation.breakdown.risk_penalty <= -8.0
    assert evaluation.snapshot.disclosure_links
    assert any(item.kind == "contract" for item in evaluation.snapshot.catalysts)


def test_evaluate_daily_batch_uses_news_as_catalysts() -> None:
    score_date = date(2026, 5, 4)
    rows = [
        make_price_row(code="051910", name="LG Chem", trade_date=score_date, close_price=250000, turnover=5_500_000_000, volume=440_000, sector="Chemicals"),
        make_price_row(code="051910", trade_date=date(2026, 5, 3), close_price=240000, turnover=2_000_000_000, volume=200_000, sector="Chemicals"),
        make_price_row(code="051910", trade_date=date(2026, 5, 2), close_price=238000, turnover=1_900_000_000, volume=190_000, sector="Chemicals"),
        make_price_row(code="051910", trade_date=date(2026, 5, 1), close_price=235000, turnover=1_850_000_000, volume=185_000, sector="Chemicals"),
    ]
    news_rows = [
        NewsRow(
            code="051910",
            title="LG Chem signs battery material supply contract",
            url="https://example.com/news",
            source="example.com",
            published_at=None,
            summary="contract news",
            news_type="contract",
            trust_score=0.65,
        )
    ]

    evaluations = evaluate_daily_batch(
        score_date=score_date,
        price_rows=rows,
        news_rows=news_rows,
        generated_at=datetime.now(timezone.utc),
    )

    assert len(evaluations) == 1
    assert evaluations[0].snapshot.news_links
    assert any(item.kind == "contract" for item in evaluations[0].snapshot.catalysts)


def test_evaluate_daily_batch_with_surge_adds_separate_surge_profile() -> None:
    score_date = date(2026, 4, 24)
    rows = []
    close = 10_000.0
    for offset in range(65):
        trade_date = date.fromordinal(score_date.toordinal() - offset)
        if offset == 0:
            rows.append(
                make_price_row(
                    code="777777",
                    name="급등테크",
                    trade_date=trade_date,
                    close_price=11_600,
                    turnover=18_000_000_000,
                    volume=2_800_000,
                    sector="로봇",
                )
            )
            rows[-1].open_price = 10_600
            rows[-1].high_price = 11_700
            rows[-1].low_price = 10_500
        else:
            rows.append(
                make_price_row(
                    code="777777",
                    name="급등테크",
                    trade_date=trade_date,
                    close_price=close,
                    turnover=1_500_000_000,
                    volume=260_000,
                    sector="로봇",
                )
            )
            close = max(close - 15, 8_000)

    evaluations = evaluate_daily_batch_with_surge(
        score_date=score_date,
        price_rows=rows,
        disclosure_rows=[
            DisclosureRow(
                code="777777",
                report_name="single sales contract",
                report_type="contract",
                material_tag="contract",
                url="https://example.com/contract",
                is_material=True,
            )
        ],
        generated_at=datetime.now(timezone.utc),
    )

    surge = [item for item in evaluations if item.snapshot.candidate_profile == "surge"]

    assert surge
    assert surge[0].score >= 60.0
    assert any(("거래" in reason or "촉매" in reason) for reason in surge[0].reasons)

def test_evaluate_daily_batch_with_surge_adds_separate_trend_profile() -> None:
    score_date = date(2026, 4, 24)
    rows = []
    for offset in range(70):
        trade_date = date.fromordinal(score_date.toordinal() - offset)
        close_price = 16_000 - offset * 70
        rows.append(
            make_price_row(
                code="999999",
                name="Trend Leader",
                trade_date=trade_date,
                close_price=close_price,
                turnover=4_500_000_000,
                volume=300_000,
                sector="Growth",
            )
        )

    evaluations = evaluate_daily_batch_with_surge(
        score_date=score_date,
        price_rows=rows,
        generated_at=datetime.now(timezone.utc),
    )

    trend = [item for item in evaluations if item.snapshot.candidate_profile == "trend"]
    selected = select_top_candidates(evaluations, min_score=60.0, limit=10, separate_profiles=True)

    assert trend
    assert trend[0].score >= 45.0
    assert trend[0].target_price_payload()["baseUpsidePct"] >= 10.0
    assert trend[0].profile_scores_payload()["scoreMode"] == "trend_quality"
    assert trend[0].profile_scores_payload()["entryScore"] != trend[0].score
    assert any(item.snapshot.candidate_profile == "trend" for item in selected)
    assert trend[0].trade_plan_payload()["exit"]["maxHoldingDays"] == 60


def test_evaluate_daily_batch_with_surge_adds_separate_pullback_profile() -> None:
    score_date = date(2026, 4, 24)
    rows = []
    for offset in range(70):
        trade_date = date.fromordinal(score_date.toordinal() - offset)
        if offset == 0:
            close_price = 92.0
        elif offset <= 5:
            close_price = 92.0 + offset * 1.6
        else:
            close_price = 100.0 - (offset - 5) * 0.45
        rows.append(
            make_price_row(
                code="555555",
                name="Pullback Leader",
                trade_date=trade_date,
                close_price=close_price,
                turnover=2_600_000_000 if offset == 0 else 1_500_000_000,
                volume=300_000 if offset == 0 else 220_000,
                sector="Growth",
            )
        )

    rows[0].open_price = 92.5
    rows[0].high_price = 93.5
    rows[0].low_price = 88.0

    evaluations = evaluate_daily_batch_with_surge(
        score_date=score_date,
        price_rows=rows,
        disclosure_rows=[
            DisclosureRow(
                code="555555",
                report_name="single sales contract",
                report_type="contract",
                material_tag="contract",
                url="https://example.com/contract",
                is_material=True,
            )
        ],
        generated_at=datetime.now(timezone.utc),
    )

    pullback = [item for item in evaluations if item.snapshot.candidate_profile == "pullback"]
    selected = select_top_candidates(pullback, min_score=60.0, limit=10, separate_profiles=True)

    assert pullback
    assert pullback[0].score >= 52.0
    assert pullback[0].trade_plan_payload()["entryMode"] == "pullback_reversal"
    assert any(item.snapshot.candidate_profile == "pullback" for item in selected)


def test_select_top_candidates_deduplicates_stable_and_surge_profiles() -> None:
    score_date = date(2026, 4, 24)
    rows = []
    for offset in range(65):
        trade_date = date.fromordinal(score_date.toordinal() - offset)
        rows.append(
            make_price_row(
                code="888888",
                name="중복후보",
                trade_date=trade_date,
                close_price=13_000 if offset == 0 else 10_000 - offset,
                turnover=18_000_000_000 if offset == 0 else 1_500_000_000,
                volume=2_600_000 if offset == 0 else 250_000,
                sector="AI",
            )
        )

    evaluations = evaluate_daily_batch_with_surge(
        score_date=score_date,
        price_rows=rows,
        generated_at=datetime.now(timezone.utc),
    )
    selected = select_top_candidates(evaluations, min_score=0.0, limit=10)

    assert len([item for item in selected if item.snapshot.code == "888888"]) == 1


def test_build_snapshots_for_date_marks_weak_market_regime() -> None:
    score_date = date(2026, 4, 24)
    rows = []
    for index in range(6):
        code = f"44{index:04d}"
        rows.extend(
            [
                make_price_row(
                    code=code,
                    trade_date=score_date,
                    close_price=9000 - index * 100,
                    turnover=3_000_000_000,
                    volume=300_000,
                ),
                make_price_row(
                    code=code,
                    trade_date=date(2026, 4, 23),
                    close_price=10000,
                    turnover=1_500_000_000,
                    volume=150_000,
                ),
            ]
        )

    snapshots = build_snapshots_for_date(score_date=score_date, price_rows=rows)

    assert snapshots
    assert {item.market_regime for item in snapshots} == {"bear"}
    assert snapshots[0].market_breadth_pct == 0.0


def test_build_snapshots_for_date_prefers_index_regime_when_index_rows_exist() -> None:
    score_date = date(2026, 4, 24)
    rows = []
    for offset in range(70):
        trade_date = date(2026, 4, 24).fromordinal(score_date.toordinal() - offset)
        index_close = 3000 - offset * 3
        rows.append(
            make_price_row(
                code="KOSPI",
                name="KOSPI",
                market="INDEX",
                sector="INDEX",
                trade_date=trade_date,
                close_price=index_close,
                turnover=0,
                volume=0,
            )
        )
    rows.extend(
        [
            make_price_row(code="111111", name="한빛세미", trade_date=score_date, close_price=12000, turnover=6_000_000_000, volume=500_000),
            make_price_row(code="111111", trade_date=date(2026, 4, 23), close_price=11200, turnover=2_000_000_000, volume=220_000),
        ]
    )

    snapshots = build_snapshots_for_date(score_date=score_date, price_rows=rows)

    assert len(snapshots) == 1
    assert snapshots[0].market_regime_source == "index"
    assert snapshots[0].market_index_name == "KOSPI"
    assert snapshots[0].market_short_trend == "up"
    assert snapshots[0].market_mid_trend == "up"
    assert snapshots[0].market_long_trend == "up"
