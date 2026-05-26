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
    clean = [value for value in values if value > 0]
    return sum(clean) / len(clean) if clean else 0.0


def _pct(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return ((current - previous) / previous) * 100.0


def _moving_average(closes: list[float], period: int) -> float:
    if len(closes) < period:
        return 0.0
    return _safe_mean(closes[:period])


def _trend_context(rows_desc: list[PriceHistoryRow]) -> tuple[float, float, float, float]:
    closes = [row.close_price for row in rows_desc]
    ma20 = _moving_average(closes, 20)
    ma60 = _moving_average(closes, 60)
    ma20_prev = _safe_mean(closes[20:40]) if len(closes) >= 40 else ma20
    ma60_prev = _safe_mean(closes[60:90]) if len(closes) >= 90 else ma60
    return ma20, ma60, ma20_prev, ma60_prev


def _five_day_return(snapshot: StockSnapshot, rows_desc: list[PriceHistoryRow]) -> float:
    if len(rows_desc) <= 5:
        return 0.0
    return _pct(snapshot.close, rows_desc[5].close_price)


def _has_stabilizing_candle(snapshot: StockSnapshot) -> bool:
    is_doji = snapshot.body_ratio <= 0.22 and snapshot.close_position >= 0.4
    has_long_lower_wick = snapshot.lower_wick_ratio >= 0.35 and snapshot.close_position >= 0.45
    has_bullish_reclaim = snapshot.is_bullish and snapshot.close_position >= 0.6
    return is_doji or has_long_lower_wick or has_bullish_reclaim


def _liquidity_score(snapshot: StockSnapshot) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if snapshot.avg_turnover_20d >= 10_000_000_000:
        score += 12.0
        reasons.append("20일 평균 거래대금이 충분해 눌림 구간에서도 추적 가능한 유동성입니다.")
    elif snapshot.avg_turnover_20d >= 3_000_000_000:
        score += 10.0
        reasons.append("20일 평균 거래대금이 눌림 매매 기준을 충족합니다.")
    elif snapshot.avg_turnover_20d >= 1_000_000_000:
        score += 8.0
        reasons.append("20일 평균 거래대금이 최소 유동성 기준을 넘었습니다.")
    elif snapshot.avg_turnover_20d >= 500_000_000:
        score += 5.0

    if 0.8 <= snapshot.turnover_ratio_20d <= 3.0:
        score += 3.0
        reasons.append("거래대금이 과열되지 않고 평균 대비 유지되고 있습니다.")
    elif 3.0 < snapshot.turnover_ratio_20d <= 5.0:
        score += 2.0
    elif snapshot.turnover_ratio_20d > 7.0:
        score -= 2.0

    if 0.9 <= snapshot.volume_ratio_20d <= 3.5:
        score += 2.0

    return _clamp(score, 0.0, 15.0), reasons


def _pullback_depth_score(return_5d: float, snapshot: StockSnapshot) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if -10.0 <= return_5d <= -5.0:
        score += 18.0
        reasons.append(f"5거래일 수익률이 {return_5d:.1f}%로 눌림목 핵심 구간입니다.")
    elif -12.0 <= return_5d < -10.0:
        score += 13.0
        reasons.append(f"5거래일 수익률이 {return_5d:.1f}%로 깊은 눌림 구간입니다.")
    elif -5.0 < return_5d <= -3.0:
        score += 11.0
        reasons.append(f"5거래일 수익률이 {return_5d:.1f}%로 얕은 눌림 구간입니다.")
    elif -15.0 <= return_5d < -12.0:
        score += 7.0
        reasons.append(f"5거래일 수익률이 {return_5d:.1f}%로 낙폭이 커 확인이 필요합니다.")

    if -7.0 <= snapshot.return_3d_pct <= 1.0:
        score += 4.0
        reasons.append("최근 3거래일 하락 폭이 추세 훼손보다는 눌림에 가깝습니다.")
    if snapshot.day_change_pct > 3.0:
        score -= 3.0

    return _clamp(score, 0.0, 25.0), reasons


def _trend_score(snapshot: StockSnapshot, rows_desc: list[PriceHistoryRow]) -> tuple[float, list[str]]:
    ma20, ma60, ma20_prev, ma60_prev = _trend_context(rows_desc)
    score = 0.0
    reasons: list[str] = []

    if ma20 > ma60:
        score += 12.0
        reasons.append("20일선이 60일선 위에 있어 중기 정배열이 유지됩니다.")
    if ma20 > ma20_prev:
        score += 4.0
        reasons.append("20일 이동평균선 기울기가 우상향입니다.")
    if ma60 > ma60_prev:
        score += 3.0
        reasons.append("60일 이동평균선도 완만하게 개선되고 있습니다.")
    if ma20 > 0 and snapshot.close >= ma20 * 0.94:
        score += 3.0
        reasons.append("종가가 20일선 근처에서 버티고 있습니다.")
    if ma60 > 0 and snapshot.close >= ma60 * 1.02:
        score += 3.0
        reasons.append("종가가 60일선 위에서 장기 추세를 유지합니다.")

    return _clamp(score, 0.0, 25.0), reasons


def _candle_score(snapshot: StockSnapshot) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if snapshot.body_ratio <= 0.22 and snapshot.close_position >= 0.4:
        score += 6.0
        reasons.append("당일 캔들이 도지에 가까워 매도 압력 둔화 신호가 있습니다.")
    if snapshot.lower_wick_ratio >= 0.35 and snapshot.close_position >= 0.45:
        score += 8.0
        reasons.append("긴 밑꼬리로 장중 저가 매수세가 확인됩니다.")
    if snapshot.close_position >= 0.65:
        score += 4.0
        reasons.append("종가가 일중 상단권을 회복했습니다.")
    if snapshot.is_bullish:
        score += 2.0

    return _clamp(score, 0.0, 20.0), reasons


def _catalyst_score(snapshot: StockSnapshot) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    for catalyst in snapshot.catalysts:
        if catalyst.kind in NEGATIVE_CATALYST_KINDS:
            continue
        if catalyst.kind in {"earnings", "contract", "approval", "buyback"}:
            score += 4.0 * catalyst.trust_score
        else:
            score += 2.5 * catalyst.trust_score
        reasons.append(f"눌림 반등 보조 재료 확인: {catalyst.title}")
    return _clamp(score, 0.0, 10.0), reasons


def _risk_penalty(
    snapshot: StockSnapshot,
    rows_desc: list[PriceHistoryRow],
    return_5d: float,
) -> tuple[float, list[str]]:
    penalty = 0.0
    flags: list[str] = []
    ma20, ma60, _, _ = _trend_context(rows_desc)

    if snapshot.warning_level:
        applied = -20.0 if snapshot.warning_level.lower() in {"warning", "danger"} else -10.0
        penalty += applied
        flags.append(f"시장경보 상태: {snapshot.warning_level}")
    if snapshot.is_under_management or snapshot.is_trading_halted:
        penalty -= 25.0
        flags.append("관리종목 또는 거래정지 리스크가 있습니다.")
    if ma60 > 0 and snapshot.close < ma60 * 0.97:
        penalty -= 12.0
        flags.append("종가가 60일선 아래로 밀려 장기 추세 훼손 가능성이 있습니다.")
    elif ma20 > 0 and snapshot.close < ma20 * 0.9:
        penalty -= 6.0
        flags.append("20일선 대비 낙폭이 커 추세 회복 확인이 필요합니다.")
    if return_5d < -15.0:
        penalty -= 8.0
        flags.append("5거래일 낙폭이 커서 단순 눌림보다 추세 이탈 가능성이 있습니다.")
    if snapshot.close_position < 0.35:
        penalty -= 8.0
        flags.append("종가가 일중 저가권이라 반등 확인이 부족합니다.")
    if snapshot.upper_wick_ratio >= 0.45:
        penalty -= 5.0
        flags.append("윗꼬리가 길어 반등 매물 압력이 남아 있습니다.")
    if snapshot.gap_up_pct >= 4.0:
        penalty -= 8.0
        flags.append("눌림 프로필에서는 갭상승 출발 종목을 감점합니다.")
    if snapshot.turnover_ratio_20d >= 8.0:
        penalty -= 5.0
        flags.append("거래대금이 과도하게 급증해 변동성 리스크가 큽니다.")
    if snapshot.market_regime == "bear":
        penalty -= 5.0
        flags.append("하락장에서는 눌림 반등 실패 확률이 높아 보수적으로 감점합니다.")
    elif snapshot.market_regime == "weak":
        penalty -= 3.0
        flags.append("약세장에서는 반등 확인 전까지 보수적인 접근이 필요합니다.")

    negative_catalysts = [item for item in snapshot.catalysts if item.kind in NEGATIVE_CATALYST_KINDS]
    if negative_catalysts:
        penalty -= 15.0
        flags.append("희석/관리/재무 리스크성 공시 또는 뉴스가 확인됩니다.")

    return max(penalty, -35.0), flags


def evaluate_pullback_snapshot(
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
    if snapshot.avg_turnover_20d < 500_000_000 or len(rows_desc) < 60:
        return None

    ma20, ma60, _, _ = _trend_context(rows_desc)
    if ma20 <= 0 or ma60 <= 0 or ma20 <= ma60:
        return None
    if snapshot.close < ma60 * 0.97:
        return None

    return_5d = _five_day_return(snapshot, rows_desc)
    if return_5d > -3.0 or return_5d < -15.0:
        return None
    if not _has_stabilizing_candle(snapshot):
        return None
    if snapshot.close_position < 0.35:
        return None
    if snapshot.day_change_pct >= 6.0:
        return None

    profile_snapshot = replace(snapshot, candidate_profile="pullback")
    liquidity_score, liquidity_reasons = _liquidity_score(profile_snapshot)
    depth_score, depth_reasons = _pullback_depth_score(return_5d, profile_snapshot)
    trend_score, trend_reasons = _trend_score(profile_snapshot, rows_desc)
    candle_score, candle_reasons = _candle_score(profile_snapshot)
    catalyst_score, catalyst_reasons = _catalyst_score(profile_snapshot)
    penalty, risk_flags = _risk_penalty(profile_snapshot, rows_desc, return_5d)

    breakdown = ScoreBreakdown(
        liquidity_score=liquidity_score,
        close_strength_score=candle_score,
        catalyst_score=catalyst_score,
        sector_score=trend_score,
        continuity_score=depth_score,
        risk_penalty=penalty,
    )
    reasons = [
        *depth_reasons,
        *trend_reasons,
        *candle_reasons,
        *liquidity_reasons,
        *catalyst_reasons,
    ]
    if not reasons:
        reasons.append("눌림목 기본 조건을 충족합니다.")

    return CandidateEvaluation(
        date=profile_snapshot.date,
        generated_at=generated_at or datetime.now(timezone.utc),
        snapshot=profile_snapshot,
        breakdown=breakdown,
        reasons=reasons,
        risk_flags=risk_flags,
    )
