from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from statistics import median

from psycopg.rows import dict_row

from app.postgres_repository import create_postgres_repository
from app.settings import load_settings


@dataclass(slots=True)
class BacktestTrade:
    score_date: date
    code: str
    name: str
    score: float
    entry_date: date | None
    entry_price: float | None
    max_return_pct: float | None
    min_return_pct: float | None
    close_return_pct: float | None
    skipped_reason: str | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backtest stored daily candidate scores with next-session entries.")
    parser.add_argument("--start", required=True, help="Score start date in YYYY-MM-DD format.")
    parser.add_argument("--end", required=True, help="Score end date in YYYY-MM-DD format.")
    parser.add_argument("--limit", type=int, default=10, help="Top N candidates per score date.")
    parser.add_argument("--horizon", type=int, default=5, help="Forward trading days to evaluate.")
    parser.add_argument("--min-score", type=float, default=30.0, help="Minimum candidate score.")
    parser.add_argument("--max-open-gap-pct", type=float, default=5.0, help="Skip entries above this opening gap.")
    parser.add_argument("--target-pct", type=float, default=5.0, help="Hit threshold for max return.")
    parser.add_argument("--stop-pct", type=float, default=-4.0, help="False-positive threshold for min return.")
    parser.add_argument("--save-summary", action="store_true", help="Upsert summary into backtest_summaries.")
    return parser


def _pct(current: float, base: float) -> float:
    if base <= 0:
        return 0.0
    return ((current - base) / base) * 100.0


def _load_candidates(conn, start: date, end: date, limit: int, min_score: float) -> list[dict]:
    sql = """
        WITH ranked AS (
            SELECT
                score_date,
                code,
                name,
                sector,
                total_score,
                risk_flags_json,
                ROW_NUMBER() OVER (PARTITION BY score_date ORDER BY total_score DESC, code ASC) AS rank
            FROM daily_candidate_scores
            WHERE score_date BETWEEN %(start)s AND %(end)s
              AND total_score >= %(min_score)s
        )
        SELECT *
        FROM ranked
        WHERE rank <= %(limit)s
        ORDER BY score_date ASC, rank ASC
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, {"start": start, "end": end, "limit": limit, "min_score": min_score})
        return list(cur.fetchall())


def _load_forward_prices(conn, code: str, score_date: date, horizon: int) -> list[dict]:
    sql = """
        SELECT trade_date, open_price, high_price, low_price, close_price
        FROM daily_prices
        WHERE code = %(code)s AND trade_date > %(score_date)s
        ORDER BY trade_date ASC
        LIMIT %(horizon)s
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, {"code": code, "score_date": score_date, "horizon": horizon})
        return list(cur.fetchall())


def _backtest_candidate(conn, candidate: dict, horizon: int, max_open_gap_pct: float) -> BacktestTrade:
    prices = _load_forward_prices(conn, candidate["code"], candidate["score_date"], horizon)
    if not prices:
        return BacktestTrade(
            score_date=candidate["score_date"],
            code=candidate["code"],
            name=candidate["name"],
            score=float(candidate["total_score"]),
            entry_date=None,
            entry_price=None,
            max_return_pct=None,
            min_return_pct=None,
            close_return_pct=None,
            skipped_reason="no_forward_prices",
        )

    entry = prices[0]
    prev_close_sql = """
        SELECT close_price
        FROM daily_prices
        WHERE code = %(code)s AND trade_date = %(score_date)s
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(prev_close_sql, {"code": candidate["code"], "score_date": candidate["score_date"]})
        base_row = cur.fetchone()

    prev_close = float(base_row["close_price"]) if base_row else 0.0
    entry_price = float(entry["open_price"])
    open_gap_pct = _pct(entry_price, prev_close)
    if open_gap_pct > max_open_gap_pct:
        return BacktestTrade(
            score_date=candidate["score_date"],
            code=candidate["code"],
            name=candidate["name"],
            score=float(candidate["total_score"]),
            entry_date=entry["trade_date"],
            entry_price=entry_price,
            max_return_pct=None,
            min_return_pct=None,
            close_return_pct=None,
            skipped_reason=f"open_gap_{open_gap_pct:.2f}",
        )

    max_high = max(float(item["high_price"]) for item in prices)
    min_low = min(float(item["low_price"]) for item in prices)
    last_close = float(prices[-1]["close_price"])
    return BacktestTrade(
        score_date=candidate["score_date"],
        code=candidate["code"],
        name=candidate["name"],
        score=float(candidate["total_score"]),
        entry_date=entry["trade_date"],
        entry_price=entry_price,
        max_return_pct=_pct(max_high, entry_price),
        min_return_pct=_pct(min_low, entry_price),
        close_return_pct=_pct(last_close, entry_price),
    )


def _format_pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}%"


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set.")

    repo = create_postgres_repository(settings.database_url)
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    with repo._connect() as conn:
        candidates = _load_candidates(conn, start, end, args.limit, args.min_score)
        trades = [
            _backtest_candidate(conn, candidate, args.horizon, args.max_open_gap_pct)
            for candidate in candidates
        ]

        executed = [trade for trade in trades if trade.skipped_reason is None]
        skipped = [trade for trade in trades if trade.skipped_reason is not None]
        hit_count = sum(1 for trade in executed if (trade.max_return_pct or 0.0) >= args.target_pct)
        false_count = sum(1 for trade in executed if (trade.min_return_pct or 0.0) <= args.stop_pct)
        warning_count = sum(1 for candidate in candidates if candidate.get("risk_flags_json"))
        sector_counts: dict[str, int] = {}
        for candidate in candidates:
            sector = candidate["sector"]
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        top10_hit_rate = hit_count / len(executed) if executed else 0.0
        false_positive_rate = false_count / len(executed) if executed else 0.0
        median_max_return = median([trade.max_return_pct or 0.0 for trade in executed]) if executed else 0.0
        sector_concentration = max(sector_counts.values()) / len(candidates) if candidates else 0.0
        warning_hit_rate = warning_count / len(candidates) if candidates else 0.0

        if args.save_summary:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO backtest_summaries (
                        start_date,
                        end_date,
                        top10_hit_rate,
                        median_max_return,
                        false_positive_rate,
                        sector_concentration,
                        warning_hit_rate
                    )
                    VALUES (%(start)s, %(end)s, %(hit)s, %(median)s, %(false)s, %(sector)s, %(warning)s)
                    ON CONFLICT (start_date, end_date) DO UPDATE SET
                        top10_hit_rate = EXCLUDED.top10_hit_rate,
                        median_max_return = EXCLUDED.median_max_return,
                        false_positive_rate = EXCLUDED.false_positive_rate,
                        sector_concentration = EXCLUDED.sector_concentration,
                        warning_hit_rate = EXCLUDED.warning_hit_rate,
                        generated_at = NOW()
                    """,
                    {
                        "start": start,
                        "end": end,
                        "hit": top10_hit_rate,
                        "median": median_max_return,
                        "false": false_positive_rate,
                        "sector": sector_concentration,
                        "warning": warning_hit_rate,
                    },
                )
            conn.commit()

    print(f"Backtest range: {start.isoformat()} ~ {end.isoformat()}")
    print(f"Candidates: {len(candidates)} / Executed: {len(executed)} / Skipped: {len(skipped)}")
    print(f"Hit rate >= {args.target_pct:.1f}%: {top10_hit_rate:.2%}")
    print(f"Median max return: {median_max_return:.2f}%")
    print(f"False positive <= {args.stop_pct:.1f}%: {false_positive_rate:.2%}")
    print(f"Sector concentration: {sector_concentration:.2%}")
    if trades:
        print("Sample trades:")
        for trade in trades[: min(10, len(trades))]:
            status = trade.skipped_reason or f"max={_format_pct(trade.max_return_pct)} min={_format_pct(trade.min_return_pct)} close={_format_pct(trade.close_return_pct)}"
            print(f"- {trade.score_date} {trade.code} {trade.name} score={trade.score:.2f} {status}")


if __name__ == "__main__":
    main()
