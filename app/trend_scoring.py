from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.domain import CandidateEvaluation, ScoreBreakdown, StockSnapshot
from app.scoring import NEGATIVE_CATALYST_KINDS

if TYPE_CHECKING:
    from app.batch import PriceHistoryRow


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _pct(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return ((current - previous) / previous) * 100.0


def _linear_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    x_mean = (len(values) - 1) / 2.0
    y_mean = _safe_mean(values)
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    if denominator <= 0:
        return 0.0
    return sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values)) / denominator


def _obv_values(rows_desc: list[PriceHistoryRow]) -> list[float]:
    chronological = list(reversed(rows_desc))
    values: list[float] = []
    current = 0.0
    previous_close: float | None = None
    for row in chronological:
        if previous_close is None:
            values.append(current)
        elif row.close_price > previous_close:
            current += row.volume
            values.append(current)
        elif row.close_price < previous_close:
            current -= row.volume
            values.append(current)
        else:
            values.append(current)
        previous_close = row.close_price
    return values


def _liquidity_score(snapshot: StockSnapshot, rows_desc: list[PriceHistoryRow]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if snapshot.avg_turnover_20d >= 10_000_000_000:
        score += 14.0
        reasons.append("20일 평균 거래대금이 100억원 이상으로 추세 추적 유동성이 충분합니다.")
    elif snapshot.avg_turnover_20d >= 3_000_000_000:
        score += 11.0
        reasons.append("20일 평균 거래대금이 30억원 이상으로 추세 매매 유동성이 확보됐습니다.")
    elif snapshot.avg_turnover_20d >= 1_000_000_000:
        score += 8.0
        reasons.append("20일 평균 거래대금이 추세 추적 최소 기준을 충족합니다.")

    obv_tail = _obv_values(rows_desc)[-20:]
    if len(obv_tail) >= 10 and _linear_slope(obv_tail) > 0:
        score += 6.0
        reasons.append("OBV 기울기가 상승해 중기 매집 흐름이 확인됩니다.")

    return _clamp(score, 0.0, 20.0), reasons


def _trend_price_score(snapshot: StockSnapshot, rows_desc: list[PriceHistoryRow]) -> tuple[float, list[str]]:
    closes = [row.close_price for row in rows_desc]
    score = 0.0
    reasons: list[str] = []
    if len(closes) < 60:
        return 0.0, reasons

    ma20 = _safe_mean(closes[:20])
    ma60 = _safe_mean(closes[:60])
    ma20_prev = _safe_mean(closes[20:40]) if len(closes) >= 40 else ma20
    ma60_prev = _safe_mean(closes[60:90]) if len(closes) >= 90 else ma60
    high_60d = max(closes[1:61]) if len(closes) > 60 else max(closes[1:] or closes)
    low_60d = min(closes[1:61]) if len(closes) > 60 else min(closes[1:] or closes)

    if snapshot.close > ma20 > ma60:
        score += 14.0
        reasons.append("종가가 20일선 위에 있고 20일선이 60일선 위에 있는 상승 추세입니다.")
    elif snapshot.close > ma60 and ma20 >= ma60 * 0.98:
        score += 8.0
        reasons.append("종가가 60일선 위에서 중기 추세 회복 구간에 있습니다.")

    if ma20 > ma20_prev:
        score += 6.0
        reasons.append("20일 이동평균선의 기울기가 우상향입니다.")
    if ma60 > ma60_prev:
        score += 4.0
        reasons.append("60일 이동평균선도 완만하게 개선되고 있습니다.")

    if high_60d > 0 and snapshot.close >= high_60d * 0.97:
        score += 4.0
        reasons.append("60일 고점권에 근접해 추세 돌파 후보입니다.")
    elif high_60d > 0 and snapshot.close >= high_60d * 0.90:
        score += 2.0
        reasons.append("60일 고점 대비 10% 이내에서 추세가 유지됩니다.")

    if low_60d > 0 and _pct(snapshot.close, low_60d) >= 12.0:
        score += 3.0
        reasons.append("60일 저점 대비 회복 폭이 있어 추세 전환/확장 가능성이 있습니다.")

    return _clamp(score, 0.0, 30.0), reasons


def _durable_catalyst_score(snapshot: StockSnapshot) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    for catalyst in snapshot.catalysts:
        if catalyst.kind in NEGATIVE_CATALYST_KINDS:
            continue
        if catalyst.kind in {"earnings", "contract", "approval", "capex"}:
            score += 2.0 * catalyst.trust_score
        elif catalyst.kind in {"buyback", "dividend", "policy", "corporate_action"}:
            score += 1.5 * catalyst.trust_score
        else:
            score += 1.0 * catalyst.trust_score
        reasons.append(f"추세 보조 재료 확인: {catalyst.title}")
    return _clamp(score, 0.0, 5.0), reasons


def _market_trend_score(snapshot: StockSnapshot) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if snapshot.market_mid_trend == "up":
        score += 5.0
        reasons.append("지수 중기 추세가 상승입니다.")
    if snapshot.market_long_trend == "up":
        score += 5.0
        reasons.append("지수 장기 추세가 상승입니다.")

    return _clamp(score, 0.0, 10.0), reasons


def _continuity_score(snapshot: StockSnapshot, rows_desc: list[PriceHistoryRow]) -> tuple[float, list[str]]:
    closes = [row.close_price for row in rows_desc]
    score = 0.0
    reasons: list[str] = []
    if len(closes) < 60:
        return 0.0, reasons

    return_20d = _pct(snapshot.close, closes[20]) if len(closes) > 20 else 0.0
    return_60d = _pct(snapshot.close, closes[60]) if len(closes) > 60 else _pct(snapshot.close, closes[-1])
    high_20d = max(closes[1:21]) if len(closes) > 20 else max(closes)
    pullback_from_20d_high = _pct(snapshot.close, high_20d)

    if 3.0 <= return_20d <= 25.0:
        score += 8.0
        reasons.append(f"20일 수익률이 {return_20d:.1f}%로 추세 지속 구간입니다.")
    elif return_20d > 25.0:
        score += 4.0
        reasons.append(f"20일 수익률이 {return_20d:.1f}%로 강하지만 단기 과열 가능성은 별도 확인이 필요합니다.")
    if return_60d >= 5.0:
        score += 8.0
        reasons.append(f"60일 수익률이 {return_60d:.1f}%로 장기 방향성이 양호합니다.")
    if pullback_from_20d_high >= -10.0:
        score += 5.0
        reasons.append("20일 고점 대비 낙폭이 제한적이어서 추세 훼손이 작습니다.")

    return _clamp(score, 0.0, 20.0), reasons


def _trend_risk_penalty(snapshot: StockSnapshot, rows_desc: list[PriceHistoryRow]) -> tuple[float, list[str]]:
    penalty = 0.0
    flags: list[str] = []
    closes = [row.close_price for row in rows_desc]

    if snapshot.warning_level:
        penalty -= 12.0
        flags.append(f"시장경보 상태: {snapshot.warning_level}")
    if snapshot.is_under_management or snapshot.is_trading_halted:
        penalty -= 25.0
        flags.append("관리종목 또는 거래정지 리스크가 있습니다.")

    if len(closes) >= 60:
        ma20 = _safe_mean(closes[:20])
        ma60 = _safe_mean(closes[:60])
        if snapshot.close < ma60:
            penalty -= 12.0
            flags.append("종가가 60일선 아래라 장기 추세 기준을 약하게 봅니다.")
        if ma20 < ma60:
            penalty -= 8.0
            flags.append("20일선이 60일선 아래라 중기 추세 정배열이 아닙니다.")

    if snapshot.market_long_trend == "down":
        penalty -= 8.0
        flags.append("지수 장기 추세가 하락입니다.")
    elif snapshot.market_mid_trend == "down":
        penalty -= 5.0
        flags.append("지수 중기 추세가 하락입니다.")

    negative_catalysts = [item for item in snapshot.catalysts if item.kind in NEGATIVE_CATALYST_KINDS]
    if negative_catalysts:
        penalty -= 15.0
        flags.append("재무/관리/거래 리스크성 공시 또는 뉴스가 확인됐습니다.")

    return max(penalty, -35.0), flags


def evaluate_trend_snapshot(
    snapshot: StockSnapshot,
    rows_desc: list[PriceHistoryRow],
    generated_at: datetime | None = None,
) -> CandidateEvaluation | None:
    if snapshot.market not in {"KOSPI", "KOSDAQ"}:
        return None
    if not snapshot.is_common_stock or snapshot.is_etf or snapshot.is_etn or snapshot.is_preferred or snapshot.is_spac:
        return None
    if snapshot.is_under_management or snapshot.is_trading_halted or snapshot.listed_days < 90:
        return None
    if snapshot.avg_turnover_20d < 1_000_000_000 or len(rows_desc) < 60:
        return None

    profile_snapshot = replace(snapshot, candidate_profile="trend")
    liquidity_score, liquidity_reasons = _liquidity_score(profile_snapshot, rows_desc)
    price_score, price_reasons = _trend_price_score(profile_snapshot, rows_desc)
    catalyst_score, catalyst_reasons = _durable_catalyst_score(profile_snapshot)
    market_score, market_reasons = _market_trend_score(profile_snapshot)
    continuity_score, continuity_reasons = _continuity_score(profile_snapshot, rows_desc)
    penalty, risk_flags = _trend_risk_penalty(profile_snapshot, rows_desc)

    breakdown = ScoreBreakdown(
        liquidity_score=liquidity_score,
        close_strength_score=price_score,
        catalyst_score=catalyst_score,
        sector_score=market_score,
        continuity_score=continuity_score,
        risk_penalty=penalty,
    )
    reasons = [
        *liquidity_reasons,
        *price_reasons,
        *catalyst_reasons,
        *market_reasons,
        *continuity_reasons,
    ]
    if not reasons:
        reasons.append("장기 추세 기본 조건을 충족합니다.")

    return CandidateEvaluation(
        date=profile_snapshot.date,
        generated_at=generated_at or datetime.now(timezone.utc),
        snapshot=profile_snapshot,
        breakdown=breakdown,
        reasons=reasons,
        risk_flags=risk_flags,
    )
