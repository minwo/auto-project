from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from app.collectors.kis_open_api import DailyPriceRecord
from app.collectors.krx_master import StockMasterRecord
from app.domain import CandidateEvaluation, CatalystItem, DisclosureLink, NewsLink, ScoreBreakdown, StockSnapshot
from app.repository import BacktestSummary, CandidateRepository

try:  # pragma: no cover
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None
    Jsonb = None


class PostgresCandidateRepository(CandidateRepository):
    def __init__(self, database_url: str) -> None:
        super().__init__()
        if psycopg is None or dict_row is None:
            raise RuntimeError(
                "psycopg is required for PostgreSQL support. Install dependencies with `pip install -e .`."
            )
        self.database_url = database_url

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def ping(self) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            row = cur.fetchone()
        return bool(row)

    def table_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        table_names = [
            "stock_master",
            "daily_prices",
            "daily_disclosures",
            "daily_market_warnings",
            "daily_candidate_scores",
            "backtest_summaries",
        ]
        with self._connect() as conn, conn.cursor() as cur:
            for table_name in table_names:
                cur.execute(f"SELECT COUNT(*) AS count FROM {table_name}")
                row = cur.fetchone()
                counts[table_name] = int(row["count"]) if row else 0
        return counts

    @staticmethod
    def _ensure_json(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            return json.loads(value)
        return value

    @classmethod
    def _build_snapshot(cls, payload: dict[str, Any]) -> StockSnapshot:
        catalysts = [CatalystItem(**item) for item in payload.get("catalysts", [])]
        news_links = [NewsLink(**item) for item in payload.get("news_links", [])]
        disclosure_links = [DisclosureLink(**item) for item in payload.get("disclosure_links", [])]
        payload = dict(payload)
        payload.pop("close_position", None)
        payload.pop("upper_wick_ratio", None)
        payload.pop("gap_up_pct", None)
        payload.pop("intraday_range_pct", None)
        payload["date"] = date.fromisoformat(payload["date"])
        payload["catalysts"] = catalysts
        payload["news_links"] = news_links
        payload["disclosure_links"] = disclosure_links
        return StockSnapshot(**payload)

    @classmethod
    def _row_to_evaluation(cls, row: dict[str, Any]) -> CandidateEvaluation:
        raw_features = cls._ensure_json(row["raw_features_json"]) or {}
        snapshot = cls._build_snapshot(raw_features)
        return CandidateEvaluation(
            date=row["score_date"],
            generated_at=row["generated_at"],
            snapshot=snapshot,
            breakdown=ScoreBreakdown(
                liquidity_score=float(row["liquidity_score"]),
                close_strength_score=float(row["close_strength_score"]),
                catalyst_score=float(row["catalyst_score"]),
                sector_score=float(row["sector_score"]),
                continuity_score=float(row["continuity_score"]),
                risk_penalty=float(row["risk_penalty"]),
            ),
            reasons=cls._ensure_json(row["reasons_json"]) or [],
            risk_flags=cls._ensure_json(row["risk_flags_json"]) or [],
        )

    @staticmethod
    def _snapshot_json(snapshot: StockSnapshot) -> dict[str, Any]:
        return snapshot.raw_features()

    @staticmethod
    def _price_stats_json(evaluation: CandidateEvaluation) -> dict[str, Any]:
        return evaluation.to_signal_summary_payload()["priceStats"]

    @staticmethod
    def _liquidity_stats_json(evaluation: CandidateEvaluation) -> dict[str, Any]:
        return evaluation.to_signal_summary_payload()["liquidityStats"]

    @staticmethod
    def _sector_stats_json(evaluation: CandidateEvaluation) -> dict[str, Any]:
        return evaluation.to_signal_summary_payload()["sectorStats"]

    @staticmethod
    def _catalyst_summary_json(evaluation: CandidateEvaluation) -> dict[str, Any]:
        return evaluation.to_signal_summary_payload()["catalystSummary"]

    def _upsert_stock_master(self, cur, snapshot: StockSnapshot) -> None:
        sql = """
            INSERT INTO stock_master (
                code,
                name_kr,
                market,
                sector,
                security_type,
                is_common_stock,
                is_preferred,
                is_etf,
                is_etn,
                is_spac,
                updated_at
            )
            VALUES (
                %(code)s,
                %(name_kr)s,
                %(market)s,
                %(sector)s,
                %(security_type)s,
                %(is_common_stock)s,
                %(is_preferred)s,
                %(is_etf)s,
                %(is_etn)s,
                %(is_spac)s,
                NOW()
            )
            ON CONFLICT (code) DO UPDATE
            SET
                name_kr = EXCLUDED.name_kr,
                market = EXCLUDED.market,
                sector = EXCLUDED.sector,
                security_type = EXCLUDED.security_type,
                is_common_stock = EXCLUDED.is_common_stock,
                is_preferred = EXCLUDED.is_preferred,
                is_etf = EXCLUDED.is_etf,
                is_etn = EXCLUDED.is_etn,
                is_spac = EXCLUDED.is_spac,
                updated_at = NOW()
        """
        cur.execute(
            sql,
            {
                "code": snapshot.code,
                "name_kr": snapshot.name,
                "market": snapshot.market,
                "sector": snapshot.sector,
                "security_type": "common_stock" if snapshot.is_common_stock else "other",
                "is_common_stock": snapshot.is_common_stock,
                "is_preferred": snapshot.is_preferred,
                "is_etf": snapshot.is_etf,
                "is_etn": snapshot.is_etn,
                "is_spac": snapshot.is_spac,
            },
        )

    def upsert_stock_master_records(self, records: list[StockMasterRecord]) -> int:
        sql = """
            INSERT INTO stock_master (
                code,
                name_kr,
                market,
                sector,
                isin,
                dart_corp_code,
                security_type,
                is_common_stock,
                is_preferred,
                is_etf,
                is_etn,
                is_spac,
                updated_at
            )
            VALUES (
                %(code)s,
                %(name_kr)s,
                %(market)s,
                %(sector)s,
                %(isin)s,
                %(dart_corp_code)s,
                %(security_type)s,
                %(is_common_stock)s,
                %(is_preferred)s,
                %(is_etf)s,
                %(is_etn)s,
                %(is_spac)s,
                NOW()
            )
            ON CONFLICT (code) DO UPDATE
            SET
                name_kr = EXCLUDED.name_kr,
                market = EXCLUDED.market,
                sector = EXCLUDED.sector,
                isin = EXCLUDED.isin,
                dart_corp_code = EXCLUDED.dart_corp_code,
                security_type = EXCLUDED.security_type,
                is_common_stock = EXCLUDED.is_common_stock,
                is_preferred = EXCLUDED.is_preferred,
                is_etf = EXCLUDED.is_etf,
                is_etn = EXCLUDED.is_etn,
                is_spac = EXCLUDED.is_spac,
                updated_at = NOW()
        """
        if not records:
            return 0
        with self._connect() as conn, conn.cursor() as cur:
            for record in records:
                cur.execute(
                    sql,
                    {
                        "code": record.code,
                        "name_kr": record.name_kr,
                        "market": record.market,
                        "sector": record.sector,
                        "isin": record.isin,
                        "dart_corp_code": record.dart_corp_code,
                        "security_type": record.security_type,
                        "is_common_stock": record.is_common_stock,
                        "is_preferred": record.is_preferred,
                        "is_etf": record.is_etf,
                        "is_etn": record.is_etn,
                        "is_spac": record.is_spac,
                    },
                )
            conn.commit()
        return len(records)

    def _upsert_daily_price(self, cur, snapshot: StockSnapshot) -> None:
        sql = """
            INSERT INTO daily_prices (
                trade_date,
                code,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                turnover,
                source
            )
            VALUES (
                %(trade_date)s,
                %(code)s,
                %(open_price)s,
                %(high_price)s,
                %(low_price)s,
                %(close_price)s,
                %(volume)s,
                %(turnover)s,
                %(source)s
            )
            ON CONFLICT (trade_date, code) DO UPDATE
            SET
                open_price = EXCLUDED.open_price,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price,
                close_price = EXCLUDED.close_price,
                volume = EXCLUDED.volume,
                turnover = EXCLUDED.turnover,
                source = EXCLUDED.source,
                ingested_at = NOW()
        """
        estimated_open = snapshot.prev_close if snapshot.prev_close > 0 else snapshot.low
        cur.execute(
            sql,
            {
                "trade_date": snapshot.date,
                "code": snapshot.code,
                "open_price": estimated_open,
                "high_price": snapshot.high,
                "low_price": snapshot.low,
                "close_price": snapshot.close,
                "volume": snapshot.volume,
                "turnover": snapshot.turnover,
                "source": "score_batch",
            },
        )

    def upsert_daily_price_records(self, records: list[DailyPriceRecord]) -> int:
        stock_sql = """
            INSERT INTO stock_master (
                code,
                name_kr,
                market,
                sector,
                security_type,
                is_common_stock,
                updated_at
            )
            VALUES (
                %(code)s,
                %(name_kr)s,
                %(market)s,
                %(sector)s,
                'unknown',
                TRUE,
                NOW()
            )
            ON CONFLICT (code) DO UPDATE
            SET
                name_kr = COALESCE(NULLIF(EXCLUDED.name_kr, ''), stock_master.name_kr),
                market = CASE
                    WHEN stock_master.market IN ('', 'UNKNOWN') AND EXCLUDED.market NOT IN ('', 'UNKNOWN')
                    THEN EXCLUDED.market
                    ELSE stock_master.market
                END,
                sector = COALESCE(EXCLUDED.sector, stock_master.sector),
                updated_at = NOW()
        """
        price_sql = """
            INSERT INTO daily_prices (
                trade_date,
                code,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                turnover,
                source
            )
            VALUES (
                %(trade_date)s,
                %(code)s,
                %(open_price)s,
                %(high_price)s,
                %(low_price)s,
                %(close_price)s,
                %(volume)s,
                %(turnover)s,
                %(source)s
            )
            ON CONFLICT (trade_date, code) DO UPDATE
            SET
                open_price = EXCLUDED.open_price,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price,
                close_price = EXCLUDED.close_price,
                volume = EXCLUDED.volume,
                turnover = EXCLUDED.turnover,
                source = EXCLUDED.source,
                ingested_at = NOW()
        """
        if not records:
            return 0
        with self._connect() as conn, conn.cursor() as cur:
            for record in records:
                cur.execute(
                    stock_sql,
                    {
                        "code": record.code,
                        "name_kr": record.name_kr or record.code,
                        "market": record.market or "UNKNOWN",
                        "sector": record.sector,
                    },
                )
                cur.execute(
                    price_sql,
                    {
                        "trade_date": record.trade_date,
                        "code": record.code,
                        "open_price": record.open_price,
                        "high_price": record.high_price,
                        "low_price": record.low_price,
                        "close_price": record.close_price,
                        "volume": record.volume,
                        "turnover": record.turnover,
                        "source": record.source,
                    },
                )
            conn.commit()
        return len(records)

    def upsert_daily_scores(self, score_date: date, evaluations: list[CandidateEvaluation]) -> None:
        sql = """
            INSERT INTO daily_candidate_scores (
                score_date,
                code,
                name,
                sector,
                total_score,
                liquidity_score,
                close_strength_score,
                catalyst_score,
                sector_score,
                continuity_score,
                risk_penalty,
                reasons_json,
                risk_flags_json,
                news_links_json,
                disclosure_links_json,
                raw_features_json,
                price_stats_json,
                liquidity_stats_json,
                sector_stats_json,
                catalyst_summary_json,
                generated_at
            )
            VALUES (
                %(score_date)s,
                %(code)s,
                %(name)s,
                %(sector)s,
                %(total_score)s,
                %(liquidity_score)s,
                %(close_strength_score)s,
                %(catalyst_score)s,
                %(sector_score)s,
                %(continuity_score)s,
                %(risk_penalty)s,
                %(reasons_json)s,
                %(risk_flags_json)s,
                %(news_links_json)s,
                %(disclosure_links_json)s,
                %(raw_features_json)s,
                %(price_stats_json)s,
                %(liquidity_stats_json)s,
                %(sector_stats_json)s,
                %(catalyst_summary_json)s,
                %(generated_at)s
            )
            ON CONFLICT (score_date, code) DO UPDATE
            SET
                name = EXCLUDED.name,
                sector = EXCLUDED.sector,
                total_score = EXCLUDED.total_score,
                liquidity_score = EXCLUDED.liquidity_score,
                close_strength_score = EXCLUDED.close_strength_score,
                catalyst_score = EXCLUDED.catalyst_score,
                sector_score = EXCLUDED.sector_score,
                continuity_score = EXCLUDED.continuity_score,
                risk_penalty = EXCLUDED.risk_penalty,
                reasons_json = EXCLUDED.reasons_json,
                risk_flags_json = EXCLUDED.risk_flags_json,
                news_links_json = EXCLUDED.news_links_json,
                disclosure_links_json = EXCLUDED.disclosure_links_json,
                raw_features_json = EXCLUDED.raw_features_json,
                price_stats_json = EXCLUDED.price_stats_json,
                liquidity_stats_json = EXCLUDED.liquidity_stats_json,
                sector_stats_json = EXCLUDED.sector_stats_json,
                catalyst_summary_json = EXCLUDED.catalyst_summary_json,
                generated_at = EXCLUDED.generated_at
        """
        with self._connect() as conn, conn.cursor() as cur:
            for evaluation in evaluations:
                snapshot = evaluation.snapshot
                self._upsert_stock_master(cur, snapshot)
                self._upsert_daily_price(cur, snapshot)
                cur.execute(
                    sql,
                    {
                        "score_date": score_date,
                        "code": snapshot.code,
                        "name": snapshot.name,
                        "sector": snapshot.sector,
                        "total_score": evaluation.score,
                        "liquidity_score": evaluation.breakdown.liquidity_score,
                        "close_strength_score": evaluation.breakdown.close_strength_score,
                        "catalyst_score": evaluation.breakdown.catalyst_score,
                        "sector_score": evaluation.breakdown.sector_score,
                        "continuity_score": evaluation.breakdown.continuity_score,
                        "risk_penalty": evaluation.breakdown.risk_penalty,
                        "reasons_json": Jsonb(evaluation.reasons),
                        "risk_flags_json": Jsonb(evaluation.risk_flags),
                        "news_links_json": Jsonb([{"title": link.title, "url": link.url} for link in snapshot.news_links]),
                        "disclosure_links_json": Jsonb(
                            [{"title": link.title, "url": link.url} for link in snapshot.disclosure_links]
                        ),
                        "raw_features_json": Jsonb(self._snapshot_json(snapshot)),
                        "price_stats_json": Jsonb(self._price_stats_json(evaluation)),
                        "liquidity_stats_json": Jsonb(self._liquidity_stats_json(evaluation)),
                        "sector_stats_json": Jsonb(self._sector_stats_json(evaluation)),
                        "catalyst_summary_json": Jsonb(self._catalyst_summary_json(evaluation)),
                        "generated_at": evaluation.generated_at,
                    },
                )
            conn.commit()

    def upsert_backtest_summary(self, start: date, end: date, summary: BacktestSummary) -> None:
        sql = """
            INSERT INTO backtest_summaries (
                start_date,
                end_date,
                top10_hit_rate,
                median_max_return,
                false_positive_rate,
                sector_concentration,
                warning_hit_rate
            )
            VALUES (
                %(start_date)s,
                %(end_date)s,
                %(top10_hit_rate)s,
                %(median_max_return)s,
                %(false_positive_rate)s,
                %(sector_concentration)s,
                %(warning_hit_rate)s
            )
            ON CONFLICT (start_date, end_date) DO UPDATE
            SET
                top10_hit_rate = EXCLUDED.top10_hit_rate,
                median_max_return = EXCLUDED.median_max_return,
                false_positive_rate = EXCLUDED.false_positive_rate,
                sector_concentration = EXCLUDED.sector_concentration,
                warning_hit_rate = EXCLUDED.warning_hit_rate,
                generated_at = NOW()
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "start_date": start,
                    "end_date": end,
                    "top10_hit_rate": summary.top10_hit_rate,
                    "median_max_return": summary.median_max_return,
                    "false_positive_rate": summary.false_positive_rate,
                    "sector_concentration": summary.sector_concentration,
                    "warning_hit_rate": summary.warning_hit_rate,
                },
            )
            conn.commit()

    def get_daily_scores(self, score_date: date) -> list[CandidateEvaluation]:
        query = """
            SELECT
                score_date,
                code,
                total_score,
                liquidity_score,
                close_strength_score,
                catalyst_score,
                sector_score,
                continuity_score,
                risk_penalty,
                reasons_json,
                risk_flags_json,
                raw_features_json,
                generated_at
            FROM daily_candidate_scores
            WHERE score_date = %(score_date)s
            ORDER BY total_score DESC, code ASC
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(query, {"score_date": score_date})
            rows = cur.fetchall()
        return [self._row_to_evaluation(row) for row in rows]

    def latest_score_date(self) -> date | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT MAX(score_date) AS latest_date FROM daily_candidate_scores")
            row = cur.fetchone()
        if not row:
            return None
        return row["latest_date"]

    def search_daily_scores(self, score_date: date, query: str = "", limit: int = 30) -> list[CandidateEvaluation]:
        normalized = query.strip()
        sql = """
            SELECT
                score_date,
                code,
                total_score,
                liquidity_score,
                close_strength_score,
                catalyst_score,
                sector_score,
                continuity_score,
                risk_penalty,
                reasons_json,
                risk_flags_json,
                raw_features_json,
                generated_at
            FROM daily_candidate_scores
            WHERE score_date = %(score_date)s
              AND (
                %(query)s = ''
                OR code ILIKE %(pattern)s
                OR name ILIKE %(pattern)s
                OR sector ILIKE %(pattern)s
              )
            ORDER BY total_score DESC, code ASC
            LIMIT %(limit)s
        """
        params = {
            "score_date": score_date,
            "query": normalized,
            "pattern": f"%{normalized}%",
            "limit": limit,
        }
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [self._row_to_evaluation(row) for row in rows]

    def get_signal_summary(self, code: str, score_date: date) -> CandidateEvaluation | None:
        sql = """
            SELECT
                score_date,
                code,
                total_score,
                liquidity_score,
                close_strength_score,
                catalyst_score,
                sector_score,
                continuity_score,
                risk_penalty,
                reasons_json,
                risk_flags_json,
                raw_features_json,
                generated_at
            FROM daily_candidate_scores
            WHERE score_date = %(score_date)s AND code = %(code)s
            LIMIT 1
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, {"score_date": score_date, "code": code})
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_evaluation(row)

    def get_backtest_summary(self, start: date, end: date) -> BacktestSummary | None:
        sql = """
            SELECT
                top10_hit_rate,
                median_max_return,
                false_positive_rate,
                sector_concentration,
                warning_hit_rate
            FROM backtest_summaries
            WHERE start_date = %(start_date)s AND end_date = %(end_date)s
            LIMIT 1
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, {"start_date": start, "end_date": end})
            row = cur.fetchone()
        if not row:
            return None
        return BacktestSummary(
            top10_hit_rate=float(row["top10_hit_rate"]),
            median_max_return=float(row["median_max_return"]),
            false_positive_rate=float(row["false_positive_rate"]),
            sector_concentration=float(row["sector_concentration"]),
            warning_hit_rate=float(row["warning_hit_rate"]),
        )


def create_postgres_repository(database_url: str) -> PostgresCandidateRepository:
    repository = PostgresCandidateRepository(database_url=database_url)
    # Connection validation on startup.
    repository.latest_score_date()
    return repository
