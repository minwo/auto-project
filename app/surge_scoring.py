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


def _linear_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    x_mean = (len(values) - 1) / 2.0
    y_mean = _safe_mean(values)
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    if denominator <= 0:
        return 0.0
    return sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values)) / denominator


def _is_bullish(row: PriceHistoryRow) -> bool:
    return row.close_price >= row.open_price


def _consecutive_bullish_days(rows_desc: list[PriceHistoryRow]) -> int:
    count = 0
    for row in rows_desc:
        if not _is_bullish(row):
            break
        count += 1
    return count


def _rsi_from_chronological_closes(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(closes[-period - 1:-1], closes[-period:]):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    average_gain = _safe_mean(gains)
    average_loss = _safe_mean(losses)
    if average_loss <= 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def _rsi_pair(rows_desc: list[PriceHistoryRow], period: int = 14) -> tuple[float | None, float | None]:
    chronological = [row.close_price for row in reversed(rows_desc)]
    if len(chronological) <= period + 1:
        return None, None
    return (
        _rsi_from_chronological_closes(chronological[:-1], period),
        _rsi_from_chronological_closes(chronological, period),
    )


def _stochastic_pair(
    rows_desc: list[PriceHistoryRow],
    period: int = 14,
) -> tuple[float | None, float | None, float | None, float | None]:
    chronological = list(reversed(rows_desc))
    if len(chronological) < period + 4:
        return None, None, None, None

    k_values: list[float] = []
    for end_index in range(period - 1, len(chronological)):
        window = chronological[end_index - period + 1:end_index + 1]
        high = max(row.high_price for row in window)
        low = min(row.low_price for row in window)
        close = chronological[end_index].close_price
        k_values.append(50.0 if high <= low else ((close - low) / (high - low)) * 100.0)

    if len(k_values) < 4:
        return None, None, None, None
    d_values = [_safe_mean(k_values[index - 2:index + 1]) for index in range(2, len(k_values))]
    if len(d_values) < 2:
        return None, None, None, None
    return k_values[-2], k_values[-1], d_values[-2], d_values[-1]


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


def _volume_score(snapshot: StockSnapshot, rows_desc: list[PriceHistoryRow]) -> tuple[float, list[str]]:
    previous_volume = rows_desc[1].volume if len(rows_desc) > 1 else 0.0
    prev_volume_ratio = snapshot.volume / previous_volume if previous_volume > 0 else 0.0
    volume_ratio = max(prev_volume_ratio, snapshot.volume_ratio_20d)
    score = 0.0
    reasons: list[str] = []

    if volume_ratio >= 10.0:
        score += 10.0
        reasons.append("거래량이 기준 대비 10배 이상 폭증했습니다.")
    elif volume_ratio >= 5.0:
        score += 7.0
        reasons.append("거래량이 기준 대비 5배 이상 증가했습니다.")
    elif volume_ratio >= 3.0:
        score += 5.0
        reasons.append("거래량이 기준 대비 3배 이상 증가했습니다.")

    if snapshot.turnover_ratio_20d >= 10.0:
        score += 10.0
        reasons.append("거래대금이 20일 평균 대비 10배 이상 유입됐습니다.")
    elif snapshot.turnover_ratio_20d >= 5.0:
        score += 7.0
        reasons.append("거래대금이 20일 평균 대비 5배 이상 유입됐습니다.")
    elif snapshot.turnover_ratio_20d >= 3.0:
        score += 4.0
        reasons.append("거래대금이 20일 평균 대비 3배 이상 유입됐습니다.")

    if snapshot.turnover >= 10_000_000_000 and snapshot.turnover_ratio_20d >= 3.0:
        score += 5.0
        reasons.append("당일 거래대금 100억원 이상으로 추적 가능한 유동성이 확인됩니다.")
    if snapshot.turnover >= 30_000_000_000 and snapshot.turnover_ratio_20d >= 5.0:
        score += 5.0
        reasons.append("당일 거래대금 300억원 이상으로 수급 규모가 커졌습니다.")

    return _clamp(score, 0.0, 30.0), reasons


def _price_score(snapshot: StockSnapshot, rows_desc: list[PriceHistoryRow]) -> tuple[float, list[str]]:
    previous_rows = rows_desc[1:]
    previous_closes = [row.close_price for row in previous_rows]
    recent_rows = rows_desc[:5]
    score = 0.0
    reasons: list[str] = []

    if len(previous_closes) >= 20:
        box_top = max(previous_closes[:20])
        if box_top > 0 and snapshot.close > box_top * 1.01:
            score += 5.0
            reasons.append("직전 20거래일 박스권 상단을 종가로 돌파했습니다.")
        high_60d = max(previous_closes[:60]) if len(previous_closes) >= 60 else max(previous_closes)
        if high_60d > 0 and snapshot.close >= high_60d:
            score += 5.0
            reasons.append("최근 고점 구간을 새로 돌파했습니다.")
        elif high_60d > 0 and snapshot.close >= high_60d * 0.9:
            score += 2.0
            reasons.append("최근 고점권에 재진입했습니다.")

    if snapshot.gap_up_pct >= 5.0:
        score += 3.0
        reasons.append("갭 상승 출발 후 종가를 유지했습니다.")
    elif snapshot.gap_up_pct >= 3.0:
        score += 2.0
        reasons.append("의미 있는 갭 상승 출발이 확인됩니다.")

    bullish_days = _consecutive_bullish_days(recent_rows)
    if bullish_days >= 5:
        score += 4.0
        reasons.append("5거래일 연속 양봉 흐름입니다.")
    elif bullish_days >= 3:
        score += 2.0
        reasons.append("3거래일 연속 양봉 흐름입니다.")

    previous_closes_for_ma = [row.close_price for row in previous_rows]
    if len(previous_closes_for_ma) >= 20:
        ma5_prev = _safe_mean(previous_closes_for_ma[:5])
        ma20_prev = _safe_mean(previous_closes_for_ma[:20])
        if snapshot.low <= ma5_prev * 1.01 and snapshot.close > ma5_prev:
            score += 3.0
            reasons.append("전일 기준 5일선 부근 지지 후 반등했습니다.")
        elif snapshot.low <= ma20_prev * 1.01 and snapshot.close > ma20_prev:
            score += 2.0
            reasons.append("전일 기준 20일선 부근 지지 후 반등했습니다.")

    if snapshot.close_position >= 0.75:
        score += 2.0
        reasons.append("종가가 당일 고가권에서 마감했습니다.")

    return _clamp(score, 0.0, 20.0), reasons


def _tech_score(snapshot: StockSnapshot, rows_desc: list[PriceHistoryRow]) -> tuple[float, list[str]]:
    closes = [row.close_price for row in rows_desc]
    score = 0.0
    reasons: list[str] = []

    if len(closes) >= 60:
        ma5 = _safe_mean(closes[:5])
        ma20 = _safe_mean(closes[:20])
        ma60 = _safe_mean(closes[:60])
        if ma5 > ma20 > ma60:
            score += 4.0
            reasons.append("5/20/60일 이동평균 정배열입니다.")
        elif ma5 > ma20:
            score += 2.0
            reasons.append("5일선이 20일선을 상회하는 단기 정배열입니다.")

    if 3.0 <= snapshot.return_3d_pct <= 18.0:
        score += 4.0
        reasons.append("최근 3거래일 상승률이 급등 초기 추적 구간입니다.")
    elif 18.0 < snapshot.return_3d_pct <= 28.0:
        score += 2.0
        reasons.append("최근 3거래일 상승률이 높아 과열 주의가 필요합니다.")

    if snapshot.close_position >= 0.8 and snapshot.upper_wick_ratio <= 0.2:
        score += 3.0
        reasons.append("윗꼬리가 짧고 종가 고가권 마감입니다.")

    rsi_prev, rsi_today = _rsi_pair(rows_desc)
    if rsi_prev is not None and rsi_today is not None:
        if rsi_prev < 35.0 and rsi_today >= 35.0:
            score += 5.0
            reasons.append(f"RSI 과매도권 이탈 신호가 확인됩니다. ({rsi_today:.1f})")
        elif rsi_prev < 50.0 <= rsi_today:
            score += 3.0
            reasons.append(f"RSI 50선 회복 신호가 확인됩니다. ({rsi_today:.1f})")
        elif 40.0 <= rsi_today <= 70.0:
            score += 1.0

    stoch_k_prev, stoch_k_today, stoch_d_prev, stoch_d_today = _stochastic_pair(rows_desc)
    if (
        stoch_k_prev is not None
        and stoch_k_today is not None
        and stoch_d_prev is not None
        and stoch_d_today is not None
        and stoch_k_prev < stoch_d_prev
        and stoch_k_today >= stoch_d_today
        and stoch_k_today < 50.0
    ):
        score += 2.0
        reasons.append(f"스토캐스틱 골든크로스가 과열 전 구간에서 확인됩니다. ({stoch_k_today:.1f})")

    obv_tail = _obv_values(rows_desc)[-10:]
    recent_closes = [row.close_price for row in rows_desc[:10]]
    if len(obv_tail) == 10 and len(recent_closes) == 10:
        obv_trend = _linear_slope(obv_tail) > 0
        average_close = _safe_mean(recent_closes)
        price_flat = average_close > 0 and ((max(recent_closes) - min(recent_closes)) / average_close) < 0.06
        if obv_trend and price_flat:
            score += 2.0
            reasons.append("OBV 기울기가 상승해 가격 정체 중 매집 신호가 확인됩니다.")

    if snapshot.sector_turnover_ratio >= 1.5:
        score += 2.0
        reasons.append("섹터 거래대금도 함께 증가해 테마 확산 가능성이 있습니다.")
    if snapshot.has_leading_move:
        score += 1.0
        reasons.append("직전 거래일에도 선행 상승 흐름이 있었습니다.")

    return _clamp(score, 0.0, 20.0), reasons


def _supply_proxy_score(snapshot: StockSnapshot) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if snapshot.sector_rising_peers >= 5:
        score += 5.0
        reasons.append("동일 섹터 상승 종목이 많아 수급 확산이 확인됩니다.")
    elif snapshot.sector_rising_peers >= 3:
        score += 3.0
        reasons.append("동일 섹터 동반 상승이 확인됩니다.")

    # 찐 테마 동조화 가중치: 피어가 많으면서도 섹터 거래대금 비중이 높을 때
    if snapshot.sector_rising_peers >= 3 and snapshot.sector_turnover_ratio >= 1.5:
        score += 3.0
        reasons.append("섹터 거래대금 폭증과 동반 상승이 겹쳐 강력한 테마가 형성되었습니다.")

    if snapshot.turnover >= 30_000_000_000:
        score += 3.0
        reasons.append("당일 거래대금 300억원 이상으로 수급 규모가 큽니다.")
    elif snapshot.turnover >= 10_000_000_000:
        score += 2.0
        reasons.append("당일 거래대금 100억원 이상으로 수급 규모가 커졌습니다.")

    if snapshot.market_regime == "strong":
        score += 2.0
        reasons.append("강세장 레짐으로 급등주 후속 수급에 우호적입니다.")

    return _clamp(score, 0.0, 10.0), reasons


def _event_score(snapshot: StockSnapshot) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    for catalyst in snapshot.catalysts:
        if catalyst.kind in NEGATIVE_CATALYST_KINDS:
            continue
        if catalyst.kind in {"earnings", "contract", "approval"}:
            score += 14.0 * catalyst.trust_score
        elif catalyst.kind in {"buyback", "capital_event", "corporate_action", "capex"}:
            score += 10.0 * catalyst.trust_score
        else:
            score += 6.0 * catalyst.trust_score
        reasons.append(f"급등 촉매 확인: {catalyst.title}")
    return _clamp(score, 0.0, 20.0), reasons


def _risk_penalty(snapshot: StockSnapshot, rows_desc: list[PriceHistoryRow]) -> tuple[float, list[str]]:
    penalty = 0.0
    flags: list[str] = []

    if snapshot.warning_level:
        if snapshot.warning_level.lower() in {"warning", "danger"}:
            penalty -= 20.0
        else:
            penalty -= 8.0
        flags.append(f"시장경보 상태: {snapshot.warning_level}")

    body = abs(snapshot.close - snapshot.open_price)
    upper_wick = snapshot.high - max(snapshot.close, snapshot.open_price)
    if body > 0 and upper_wick / body > 2.0:
        penalty -= 10.0
        flags.append("긴 윗꼬리로 추격 매수 위험이 큽니다.")
        
    # VWAP (Volume Weighted Average Price) 이탈 컷
    if snapshot.volume > 0 and snapshot.turnover > 0:
        vwap = snapshot.turnover / snapshot.volume
        if snapshot.close < vwap * 0.98:
            penalty -= 15.0
            flags.append("종가가 당일 평균 체결가(VWAP)를 크게 하회하여 악성 매물이 존재합니다.")

    if snapshot.gap_up_pct >= 10.0:
        penalty -= 8.0
        flags.append("시초 갭 상승이 10% 이상으로 높습니다.")
    if snapshot.day_change_pct >= 25.0:
        penalty -= 8.0
        flags.append("당일 상승률이 25% 이상으로 단기 과열입니다.")
    if snapshot.turnover_ratio_20d >= 15.0:
        penalty -= 5.0
        flags.append("거래대금이 20일 평균 대비 15배 이상 급증했습니다.")
    if snapshot.return_3d_pct >= 30.0:
        penalty -= 8.0
        flags.append("최근 3거래일 상승률이 30% 이상으로 과열입니다.")

    _, rsi_today = _rsi_pair(rows_desc)
    if rsi_today is not None and rsi_today > 70.0:
        penalty -= 5.0
        flags.append(f"RSI가 70을 초과해 단기 과열입니다. ({rsi_today:.1f})")

    if snapshot.market_regime == "bear":
        penalty -= 8.0
        flags.append("하락장 레짐에서는 급등주 실패 확률이 높습니다.")

    negative_catalysts = [item for item in snapshot.catalysts if item.kind in NEGATIVE_CATALYST_KINDS]
    if negative_catalysts:
        penalty -= 12.0
        flags.append("희석/관리/재무 리스크성 공시가 확인됩니다.")

    if snapshot.return_3d_pct >= 15.0 and snapshot.day_change_pct >= 10.0:
        penalty -= 6.0
        flags.append("3거래일 15% 이상 상승 + 당일 10% 이상으로 과열 추격 위험이 큽니다.")

    return max(penalty, -35.0), flags


def _prioritize_reasons(reasons: list[str]) -> list[str]:
    priority = {
        "공시": 1,
        "촉매": 1,
        "계약": 1,
        "거래대금": 2,
        "거래량": 3,
        "박스권": 4,
        "고점": 4,
        "RSI": 5,
        "스토캐스틱": 5,
        "OBV": 5,
        "섹터": 6,
    }

    def reason_rank(reason: str) -> int:
        return next((rank for keyword, rank in priority.items() if keyword in reason), 99)

    return sorted(reasons, key=reason_rank)


def evaluate_surge_snapshot(
    snapshot: StockSnapshot,
    rows_desc: list[PriceHistoryRow],
    generated_at: datetime | None = None,
) -> CandidateEvaluation | None:
    if snapshot.market not in {"KOSPI", "KOSDAQ"}:
        return None
    if not snapshot.is_common_stock or snapshot.is_etf or snapshot.is_etn or snapshot.is_preferred or snapshot.is_spac:
        return None
    if snapshot.is_under_management or snapshot.is_trading_halted or snapshot.listed_days < 60:
        return None
    if snapshot.avg_turnover_20d < 500_000_000:
        return None
    if snapshot.day_change_pct < 3.0 or snapshot.volume_ratio_20d < 3.0:
        return None

    profile_snapshot = replace(snapshot, candidate_profile="surge")
    volume_score, volume_reasons = _volume_score(profile_snapshot, rows_desc)
    price_score, price_reasons = _price_score(profile_snapshot, rows_desc)
    tech_score, tech_reasons = _tech_score(profile_snapshot, rows_desc)
    supply_score, supply_reasons = _supply_proxy_score(profile_snapshot)
    event_score, event_reasons = _event_score(profile_snapshot)
    penalty, risk_flags = _risk_penalty(profile_snapshot, rows_desc)

    breakdown = ScoreBreakdown(
        liquidity_score=volume_score,
        close_strength_score=price_score,
        catalyst_score=event_score,
        sector_score=tech_score,
        continuity_score=supply_score,
        risk_penalty=penalty,
    )
    reasons = _prioritize_reasons([*volume_reasons, *price_reasons, *tech_reasons, *supply_reasons, *event_reasons])
    if not reasons:
        reasons.append("급등형 기본 조건을 충족했습니다.")

    return CandidateEvaluation(
        date=profile_snapshot.date,
        generated_at=generated_at or datetime.now(timezone.utc),
        snapshot=profile_snapshot,
        breakdown=breakdown,
        reasons=reasons,
        risk_flags=risk_flags,
    )
