from datetime import date
from app.repository import CandidateRepository
from app.batch import MarketRegimeSnapshot, build_market_regime_for_date

def _market_regime_payload_from_snapshot(snapshot) -> dict[str, object]:
    return {
        "regime": snapshot.market_regime,
        "source": snapshot.market_regime_source,
        "indexName": snapshot.market_index_name,
        "indexClose": round(snapshot.market_index_close, 2),
        "indexReturnPct": round(snapshot.market_index_return_pct, 2),
        "indexReturn5dPct": round(snapshot.market_index_return_5d_pct, 2),
        "indexReturn20dPct": round(snapshot.market_index_return_20d_pct, 2),
        "indexReturn60dPct": round(snapshot.market_index_return_60d_pct, 2),
        "indexMa20GapPct": round(snapshot.market_index_ma20_gap_pct, 2),
        "indexMa60GapPct": round(snapshot.market_index_ma60_gap_pct, 2),
        "shortTrend": snapshot.market_short_trend,
        "midTrend": snapshot.market_mid_trend,
        "longTrend": snapshot.market_long_trend,
        "breadthPct": round(snapshot.market_breadth_pct, 2),
        "avgReturnPct": round(snapshot.market_avg_return_pct, 2),
    }

def _market_regime_payload_from_regime(regime: MarketRegimeSnapshot) -> dict[str, object]:
    return {
        "regime": regime.regime,
        "source": regime.source,
        "indexName": regime.index_name,
        "indexClose": round(regime.index_close, 2),
        "indexReturnPct": round(regime.index_return_pct, 2),
        "indexReturn5dPct": round(regime.index_return_5d_pct, 2),
        "indexReturn20dPct": round(regime.index_return_20d_pct, 2),
        "indexReturn60dPct": round(regime.index_return_60d_pct, 2),
        "indexMa20GapPct": round(regime.index_ma20_gap_pct, 2),
        "indexMa60GapPct": round(regime.index_ma60_gap_pct, 2),
        "shortTrend": regime.short_trend,
        "midTrend": regime.mid_trend,
        "longTrend": regime.long_trend,
        "breadthPct": round(regime.breadth_pct, 2),
        "avgReturnPct": round(regime.avg_return_pct, 2),
    }

def market_regime_payload(repo: CandidateRepository, score_date: date, evaluations) -> dict[str, object] | None:
    if evaluations:
        return _market_regime_payload_from_snapshot(evaluations[0].snapshot)
    fetch_price_history = getattr(repo, "fetch_price_history_for_batch", None)
    if not callable(fetch_price_history):
        return None
    price_rows = fetch_price_history(score_date=score_date, history_limit=90)
    if not price_rows:
        return None
    regime = build_market_regime_for_date(score_date=score_date, price_rows=price_rows)
    return _market_regime_payload_from_regime(regime)
