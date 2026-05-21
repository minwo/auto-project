from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from app.batch import DisclosureRow, NewsRow, PriceHistoryRow, WarningRow
from app.collectors.dart_open_api import DartCorpCodeRecord, DartDisclosureRecord
from app.collectors.kiwoom_open_api import DailyPriceRecord
from app.collectors.krx_master import StockMasterRecord
from app.collectors.market_warnings import MarketWarningRecord
from app.collectors.naver_news import NaverNewsRecord
from app.domain import CandidateEvaluation, CatalystItem, DisclosureLink, NewsLink, ScoreBreakdown, StockSnapshot
from app.price_validation import validate_ohlc
from app.repository import BacktestSummary, CandidateRepository, DailyTopPick, PriceChartPoint

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
        self._ensure_daily_news_table()
        counts: dict[str, int] = {}
        table_names = [
            "stock_master",
            "daily_prices",
            "daily_disclosures",
            "daily_news",
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

    def _ensure_daily_top_pick_table(self) -> None:
        sql = """
            CREATE TABLE IF NOT EXISTS daily_top_score_picks (
                pick_date DATE PRIMARY KEY,
                code VARCHAR(12) NOT NULL REFERENCES stock_master(code),
                name VARCHAR(120) NOT NULL,
                sector VARCHAR(120) NOT NULL,
                total_score NUMERIC(5, 2) NOT NULL,
                base_close NUMERIC(18, 4) NOT NULL,
                reasons_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                risk_flags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()

    def _ensure_daily_news_table(self) -> None:
        sql = """
            CREATE TABLE IF NOT EXISTS daily_news (
                trade_date DATE NOT NULL,
                code VARCHAR(12) NOT NULL REFERENCES stock_master(code),
                news_id VARCHAR(64) NOT NULL,
                title VARCHAR(500) NOT NULL,
                url TEXT NOT NULL,
                source VARCHAR(64) NOT NULL,
                published_at TIMESTAMPTZ,
                summary TEXT,
                news_type VARCHAR(64),
                trust_score NUMERIC(4, 2) NOT NULL DEFAULT 0.50,
                ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (trade_date, code, news_id)
            )
        """
        index_sql = """
            CREATE INDEX IF NOT EXISTS idx_daily_news_code_date
            ON daily_news (code, trade_date DESC)
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(index_sql)
            conn.commit()

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
        payload.pop("is_bullish", None)
        payload.pop("body_ratio", None)
        payload.pop("lower_wick_ratio", None)
        payload["date"] = date.fromisoformat(payload["date"])
        payload["catalysts"] = catalysts
        payload["news_links"] = news_links
        payload["disclosure_links"] = disclosure_links
        if "open_price" not in payload:
            payload["open_price"] = payload.get("prev_close", payload.get("close", 0.0))
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
    def _json_ready(value: Any) -> Any:
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, list):
            return [PostgresCandidateRepository._json_ready(item) for item in value]
        if isinstance(value, dict):
            return {key: PostgresCandidateRepository._json_ready(item) for key, item in value.items()}
        return value

    @staticmethod
    def _snapshot_json(snapshot: StockSnapshot) -> dict[str, Any]:
        return PostgresCandidateRepository._json_ready(snapshot.raw_features())

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
        open_price = snapshot.open_price if snapshot.open_price > 0 else snapshot.prev_close
        validate_ohlc(
            open_price=open_price,
            high_price=snapshot.high,
            low_price=snapshot.low,
            close_price=snapshot.close,
            context=f"score_batch {snapshot.code} {snapshot.date.isoformat()}",
        )
        cur.execute(
            sql,
            {
                "trade_date": snapshot.date,
                "code": snapshot.code,
                "open_price": open_price,
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
                %(security_type)s,
                %(is_common_stock)s,
                NOW()
            )
            ON CONFLICT (code) DO UPDATE
            SET
                name_kr = CASE
                    WHEN EXCLUDED.name_kr IS NULL OR EXCLUDED.name_kr = '' OR EXCLUDED.name_kr = EXCLUDED.code
                    THEN stock_master.name_kr
                    ELSE EXCLUDED.name_kr
                END,
                market = CASE
                    WHEN stock_master.market IN ('', 'UNKNOWN') AND EXCLUDED.market NOT IN ('', 'UNKNOWN')
                    THEN EXCLUDED.market
                    ELSE stock_master.market
                END,
                sector = COALESCE(EXCLUDED.sector, stock_master.sector),
                security_type = EXCLUDED.security_type,
                is_common_stock = EXCLUDED.is_common_stock,
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
                validate_ohlc(
                    open_price=record.open_price,
                    high_price=record.high_price,
                    low_price=record.low_price,
                    close_price=record.close_price,
                    context=f"{record.source} {record.code} {record.trade_date.isoformat()}",
                )
                cur.execute(
                    stock_sql,
                    {
                        "code": record.code,
                        "name_kr": record.name_kr or record.code,
                        "market": record.market or "KOSPI",
                        "sector": record.sector or "Unclassified",
                        "security_type": "index" if record.market == "INDEX" else "unknown",
                        "is_common_stock": record.market != "INDEX",
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

    def fetch_stock_codes_for_price_load(
        self,
        *,
        markets: list[str] | None = None,
        limit: int | None = None,
    ) -> list[str]:
        filters = [
            "is_common_stock = TRUE",
            "is_preferred = FALSE",
            "is_etf = FALSE",
            "is_etn = FALSE",
            "is_spac = FALSE",
            "delisted_at IS NULL",
        ]
        params: dict[str, Any] = {}
        if markets:
            filters.append("market = ANY(%(markets)s)")
            params["markets"] = markets

        limit_sql = ""
        if limit is not None:
            limit_sql = " LIMIT %(limit)s"
            params["limit"] = limit

        sql = f"""
            SELECT code
            FROM stock_master
            WHERE {" AND ".join(filters)}
            ORDER BY code ASC
            {limit_sql}
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [row["code"] for row in rows]

    def fetch_stock_news_targets(
        self,
        *,
        codes: list[str] | None = None,
        markets: list[str] | None = None,
        limit: int | None = None,
    ) -> list[tuple[str, str]]:
        filters = [
            "is_common_stock = TRUE",
            "is_preferred = FALSE",
            "is_etf = FALSE",
            "is_etn = FALSE",
            "is_spac = FALSE",
            "delisted_at IS NULL",
        ]
        params: dict[str, Any] = {}
        if codes:
            filters.append("code = ANY(%(codes)s)")
            params["codes"] = codes
        if markets:
            filters.append("market = ANY(%(markets)s)")
            params["markets"] = markets

        limit_sql = ""
        if limit is not None:
            limit_sql = " LIMIT %(limit)s"
            params["limit"] = limit

        sql = f"""
            SELECT code, name_kr
            FROM stock_master
            WHERE {" AND ".join(filters)}
            ORDER BY code ASC
            {limit_sql}
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [(row["code"], row["name_kr"]) for row in rows]

    def update_stock_display_names(self, records: list[tuple[str, str]]) -> int:
        sql = """
            UPDATE stock_master
            SET
                name_kr = %(name_kr)s,
                updated_at = NOW()
            WHERE code = %(code)s
        """
        if not records:
            return 0
        updated = 0
        with self._connect() as conn, conn.cursor() as cur:
            for code, name_kr in records:
                cur.execute(sql, {"code": code, "name_kr": name_kr})
                updated += cur.rowcount
            conn.commit()
        return updated

    def upsert_manual_stock_records(self, records: list[tuple[str, str]]) -> int:
        sql = """
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
                'KOSDAQ',
                'Unclassified',
                'manual_alias',
                TRUE,
                NOW()
            )
            ON CONFLICT (code) DO UPDATE
            SET
                name_kr = CASE
                    WHEN stock_master.name_kr = stock_master.code OR stock_master.name_kr = ''
                    THEN EXCLUDED.name_kr
                    ELSE stock_master.name_kr
                END,
                market = CASE
                    WHEN stock_master.market IN ('', 'UNKNOWN')
                    THEN EXCLUDED.market
                    ELSE stock_master.market
                END,
                sector = COALESCE(stock_master.sector, EXCLUDED.sector),
                updated_at = NOW()
        """
        if not records:
            return 0
        with self._connect() as conn, conn.cursor() as cur:
            for code, name_kr in records:
                cur.execute(sql, {"code": code, "name_kr": name_kr})
            conn.commit()
        return len(records)

    def resolve_stock_codes(self, query: str, limit: int = 5) -> list[str]:
        normalized = query.strip()
        if not normalized:
            return []
        sql = """
            SELECT code
            FROM stock_master
            WHERE code ILIKE %(pattern)s OR name_kr ILIKE %(pattern)s
            ORDER BY
                CASE
                    WHEN code = %(query)s THEN 0
                    WHEN name_kr = %(query)s THEN 1
                    WHEN code ILIKE %(prefix)s THEN 2
                    WHEN name_kr ILIKE %(prefix)s THEN 3
                    ELSE 4
                END,
                code ASC
            LIMIT %(limit)s
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "query": normalized,
                    "pattern": f"%{normalized}%",
                    "prefix": f"{normalized}%",
                    "limit": limit,
                },
            )
            rows = cur.fetchall()
        return [row["code"] for row in rows]

    def update_dart_corp_codes(self, records: list[DartCorpCodeRecord]) -> int:
        sql = """
            UPDATE stock_master
            SET
                dart_corp_code = %(dart_corp_code)s,
                updated_at = NOW()
            WHERE code = %(code)s
        """
        matched = 0
        with self._connect() as conn, conn.cursor() as cur:
            for record in records:
                if not record.stock_code:
                    continue
                cur.execute(sql, {"code": record.stock_code, "dart_corp_code": record.corp_code})
                matched += cur.rowcount
            conn.commit()
        return matched

    def upsert_daily_disclosure_records(self, records: list[DartDisclosureRecord]) -> int:
        sql = """
            INSERT INTO daily_disclosures (
                trade_date,
                code,
                receipt_no,
                report_name,
                report_type,
                disclosed_at,
                url,
                is_material,
                material_tag
            )
            VALUES (
                %(trade_date)s,
                %(code)s,
                %(receipt_no)s,
                %(report_name)s,
                %(report_type)s,
                %(disclosed_at)s,
                %(url)s,
                %(is_material)s,
                %(material_tag)s
            )
            ON CONFLICT (trade_date, code, receipt_no) DO UPDATE
            SET
                report_name = EXCLUDED.report_name,
                report_type = EXCLUDED.report_type,
                disclosed_at = EXCLUDED.disclosed_at,
                url = EXCLUDED.url,
                is_material = EXCLUDED.is_material,
                material_tag = EXCLUDED.material_tag,
                ingested_at = NOW()
        """
        if not records:
            return 0
        inserted = 0
        with self._connect() as conn, conn.cursor() as cur:
            for record in records:
                cur.execute(
                    "SELECT 1 FROM stock_master WHERE code = %(code)s",
                    {"code": record.code},
                )
                if cur.fetchone() is None:
                    continue
                cur.execute(
                    sql,
                    {
                        "trade_date": record.trade_date,
                        "code": record.code,
                        "receipt_no": record.receipt_no,
                        "report_name": record.report_name,
                        "report_type": record.report_type,
                        "disclosed_at": record.disclosed_at,
                        "url": record.url,
                        "is_material": record.is_material,
                        "material_tag": record.material_tag,
                    },
                )
                inserted += 1
            conn.commit()
        return inserted

    def upsert_daily_news_records(self, records: list[NaverNewsRecord]) -> int:
        self._ensure_daily_news_table()
        sql = """
            INSERT INTO daily_news (
                trade_date,
                code,
                news_id,
                title,
                url,
                source,
                published_at,
                summary,
                news_type,
                trust_score
            )
            VALUES (
                %(trade_date)s,
                %(code)s,
                %(news_id)s,
                %(title)s,
                %(url)s,
                %(source)s,
                %(published_at)s,
                %(summary)s,
                %(news_type)s,
                %(trust_score)s
            )
            ON CONFLICT (trade_date, code, news_id) DO UPDATE
            SET
                title = EXCLUDED.title,
                url = EXCLUDED.url,
                source = EXCLUDED.source,
                published_at = EXCLUDED.published_at,
                summary = EXCLUDED.summary,
                news_type = EXCLUDED.news_type,
                trust_score = EXCLUDED.trust_score,
                ingested_at = NOW()
        """
        if not records:
            return 0
        inserted = 0
        with self._connect() as conn, conn.cursor() as cur:
            for record in records:
                cur.execute(
                    "SELECT 1 FROM stock_master WHERE code = %(code)s",
                    {"code": record.code},
                )
                if cur.fetchone() is None:
                    continue
                cur.execute(
                    sql,
                    {
                        "trade_date": record.trade_date,
                        "code": record.code,
                        "news_id": record.news_id,
                        "title": record.title,
                        "url": record.url,
                        "source": record.source,
                        "published_at": record.published_at,
                        "summary": record.summary,
                        "news_type": record.news_type,
                        "trust_score": record.trust_score,
                    },
                )
                inserted += 1
            conn.commit()
        return inserted

    def upsert_daily_market_warning_records(self, records: list[MarketWarningRecord]) -> int:
        sql = """
            INSERT INTO daily_market_warnings (
                trade_date,
                code,
                warning_type,
                warning_level,
                is_halted,
                is_under_management,
                source_url
            )
            VALUES (
                %(trade_date)s,
                %(code)s,
                %(warning_type)s,
                %(warning_level)s,
                %(is_halted)s,
                %(is_under_management)s,
                %(source_url)s
            )
            ON CONFLICT (trade_date, code) DO UPDATE
            SET
                warning_type = EXCLUDED.warning_type,
                warning_level = EXCLUDED.warning_level,
                is_halted = EXCLUDED.is_halted,
                is_under_management = EXCLUDED.is_under_management,
                source_url = EXCLUDED.source_url,
                ingested_at = NOW()
        """
        if not records:
            return 0
        inserted = 0
        with self._connect() as conn, conn.cursor() as cur:
            for record in records:
                cur.execute(
                    "SELECT 1 FROM stock_master WHERE code = %(code)s",
                    {"code": record.code},
                )
                if cur.fetchone() is None:
                    continue
                cur.execute(
                    sql,
                    {
                        "trade_date": record.trade_date,
                        "code": record.code,
                        "warning_type": record.warning_type,
                        "warning_level": record.warning_level,
                        "is_halted": record.is_halted,
                        "is_under_management": record.is_under_management,
                        "source_url": record.source_url,
                    },
                )
                inserted += 1
            conn.commit()
        return inserted

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

    def replace_daily_scores(self, score_date: date, evaluations: list[CandidateEvaluation]) -> None:
        self._ensure_daily_top_pick_table()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM daily_candidate_scores WHERE score_date = %(score_date)s",
                {"score_date": score_date},
            )
            cur.execute(
                "DELETE FROM daily_top_score_picks WHERE pick_date = %(score_date)s",
                {"score_date": score_date},
            )
            conn.commit()
        self.upsert_daily_scores(score_date, evaluations)

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

    def latest_trade_date(self) -> date | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT MAX(trade_date) AS latest_date FROM daily_prices")
            row = cur.fetchone()
        if not row:
            return None
        return row["latest_date"]

    def available_trade_dates(self, limit: int = 260) -> list[date]:
        sql = """
            SELECT score_date
            FROM daily_candidate_scores
            GROUP BY score_date
            HAVING COUNT(*) > 0
            ORDER BY score_date DESC
            LIMIT %(limit)s
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, {"limit": limit})
            rows = cur.fetchall()
        return [row["score_date"] for row in rows]

    def fetch_price_history_for_batch(self, score_date: date, history_limit: int = 25) -> list[PriceHistoryRow]:
        sql = """
            WITH ranked_prices AS (
                SELECT
                    dp.trade_date,
                    dp.code,
                    dp.open_price,
                    dp.high_price,
                    dp.low_price,
                    dp.close_price,
                    dp.volume,
                    dp.turnover,
                    sm.name_kr,
                    sm.market,
                    COALESCE(sm.sector, 'Unclassified') AS sector,
                    sm.listed_at,
                    sm.is_common_stock,
                    sm.is_preferred,
                    sm.is_etf,
                    sm.is_etn,
                    sm.is_spac,
                    ROW_NUMBER() OVER (PARTITION BY dp.code ORDER BY dp.trade_date DESC) AS rn
                FROM daily_prices dp
                JOIN stock_master sm ON sm.code = dp.code
                WHERE dp.trade_date <= %(score_date)s
            )
            SELECT *
            FROM ranked_prices
            WHERE rn <= %(history_limit)s
            ORDER BY code ASC, trade_date DESC
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, {"score_date": score_date, "history_limit": history_limit})
            rows = cur.fetchall()
        return [
            PriceHistoryRow(
                code=row["code"],
                name=row["name_kr"],
                market=row["market"],
                sector=row["sector"],
                listed_at=row["listed_at"],
                is_common_stock=bool(row["is_common_stock"]),
                is_preferred=bool(row["is_preferred"]),
                is_etf=bool(row["is_etf"]),
                is_etn=bool(row["is_etn"]),
                is_spac=bool(row["is_spac"]),
                trade_date=row["trade_date"],
                open_price=float(row["open_price"]),
                high_price=float(row["high_price"]),
                low_price=float(row["low_price"]),
                close_price=float(row["close_price"]),
                volume=float(row["volume"]),
                turnover=float(row["turnover"]),
            )
            for row in rows
        ]

    def fetch_market_warnings_for_date(self, score_date: date) -> list[WarningRow]:
        sql = """
            SELECT code, warning_level, is_halted, is_under_management
            FROM daily_market_warnings
            WHERE trade_date = %(score_date)s
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, {"score_date": score_date})
            rows = cur.fetchall()
        return [
            WarningRow(
                code=row["code"],
                warning_level=row["warning_level"],
                is_halted=bool(row["is_halted"]),
                is_under_management=bool(row["is_under_management"]),
            )
            for row in rows
        ]

    def fetch_disclosures_for_date(self, score_date: date) -> list[DisclosureRow]:
        sql = """
            SELECT code, report_name, report_type, material_tag, url, is_material
            FROM daily_disclosures
            WHERE trade_date = %(score_date)s
            ORDER BY code ASC, disclosed_at DESC NULLS LAST, receipt_no DESC
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, {"score_date": score_date})
            rows = cur.fetchall()
        return [
            DisclosureRow(
                code=row["code"],
                report_name=row["report_name"],
                report_type=row["report_type"],
                material_tag=row["material_tag"],
                url=row["url"],
                is_material=bool(row["is_material"]),
            )
            for row in rows
        ]

    def fetch_news_for_date(self, score_date: date) -> list[NewsRow]:
        self._ensure_daily_news_table()
        sql = """
            SELECT code, title, url, source, published_at, summary, news_type, trust_score
            FROM daily_news
            WHERE trade_date = %(score_date)s
            ORDER BY code ASC, published_at DESC NULLS LAST, title ASC
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, {"score_date": score_date})
            rows = cur.fetchall()
        return [
            NewsRow(
                code=row["code"],
                title=row["title"],
                url=row["url"],
                source=row["source"],
                published_at=row["published_at"],
                summary=row["summary"],
                news_type=row["news_type"],
                trust_score=float(row["trust_score"]),
            )
            for row in rows
        ]

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

    def get_price_chart(self, code: str, to_date: date, limit: int = 60) -> list[PriceChartPoint]:
        sql = """
            SELECT trade_date, open_price, high_price, low_price, close_price, volume
            FROM daily_prices
            WHERE code = %(code)s
              AND trade_date <= %(to_date)s
            ORDER BY trade_date DESC
            LIMIT %(limit)s
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, {"code": code, "to_date": to_date, "limit": limit})
            rows = cur.fetchall()
        return [
            PriceChartPoint(
                trade_date=row["trade_date"],
                open_price=float(row["open_price"]),
                high_price=float(row["high_price"]),
                low_price=float(row["low_price"]),
                close_price=float(row["close_price"]),
                volume=float(row["volume"]),
            )
            for row in reversed(rows)
        ]

    def refresh_daily_top_picks(self, as_of: date, retention_days: int = 92) -> list[DailyTopPick]:
        self._ensure_daily_top_pick_table()
        cutoff = as_of - timedelta(days=retention_days)
        select_sql = """
            SELECT
                score_date,
                code,
                name,
                sector,
                total_score,
                raw_features_json,
                reasons_json,
                risk_flags_json
            FROM daily_candidate_scores
            WHERE score_date >= %(cutoff)s
              AND score_date <= %(as_of)s
            ORDER BY score_date ASC, total_score DESC, code ASC
        """
        insert_sql = """
            INSERT INTO daily_top_score_picks (
                pick_date,
                code,
                name,
                sector,
                total_score,
                base_close,
                reasons_json,
                risk_flags_json,
                updated_at
            )
            VALUES (
                %(pick_date)s,
                %(code)s,
                %(name)s,
                %(sector)s,
                %(total_score)s,
                %(base_close)s,
                %(reasons_json)s,
                %(risk_flags_json)s,
                NOW()
            )
            ON CONFLICT (pick_date) DO UPDATE
            SET
                code = EXCLUDED.code,
                name = EXCLUDED.name,
                sector = EXCLUDED.sector,
                total_score = EXCLUDED.total_score,
                base_close = EXCLUDED.base_close,
                reasons_json = EXCLUDED.reasons_json,
                risk_flags_json = EXCLUDED.risk_flags_json,
                updated_at = NOW()
        """
        delete_window_sql = """
            DELETE FROM daily_top_score_picks
            WHERE pick_date >= %(cutoff)s AND pick_date <= %(as_of)s
        """
        delete_old_sql = "DELETE FROM daily_top_score_picks WHERE pick_date < %(cutoff)s"

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(select_sql, {"cutoff": cutoff, "as_of": as_of})
            rows = cur.fetchall()

            picks_by_date: dict[date, dict[str, Any]] = {}
            active_codes: set[str] = set()

            for row in rows:
                score_date = row["score_date"]
                code = row["code"]
                if code in active_codes:
                    continue
                if score_date in picks_by_date:
                    continue

                raw_features = self._ensure_json(row["raw_features_json"]) or {}
                picks_by_date[score_date] = {
                    "pick_date": score_date,
                    "code": code,
                    "name": row["name"],
                    "sector": row["sector"],
                    "total_score": row["total_score"],
                    "base_close": float(raw_features.get("close", 0.0) or 0.0),
                    "reasons_json": Jsonb(self._ensure_json(row["reasons_json"]) or []),
                    "risk_flags_json": Jsonb(self._ensure_json(row["risk_flags_json"]) or []),
                }
                active_codes.add(code)

            cur.execute(delete_window_sql, {"cutoff": cutoff, "as_of": as_of})
            for pick in picks_by_date.values():
                cur.execute(insert_sql, pick)
            cur.execute(delete_old_sql, {"cutoff": cutoff})
            conn.commit()
        return self.get_daily_top_picks(as_of=as_of, retention_days=retention_days)

    def get_daily_top_picks(self, as_of: date, retention_days: int = 92) -> list[DailyTopPick]:
        self._ensure_daily_top_pick_table()
        cutoff = as_of - timedelta(days=retention_days)
        sql = """
            SELECT
                pick.pick_date,
                pick.code,
                pick.name,
                pick.sector,
                pick.total_score,
                pick.base_close,
                pick.reasons_json,
                pick.risk_flags_json,
                score.raw_features_json,
                COALESCE(latest_recommendation.score_date, pick.pick_date) AS recommendation_end_date,
                COALESCE(latest_price.trade_date, pick.pick_date) AS latest_date,
                COALESCE(latest_price.close_price, pick.base_close) AS latest_close
            FROM daily_top_score_picks pick
            LEFT JOIN daily_candidate_scores score
              ON score.score_date = pick.pick_date
             AND score.code = pick.code
            LEFT JOIN LATERAL (
                SELECT score_date
                FROM daily_candidate_scores recommendation
                WHERE recommendation.code = pick.code
                  AND recommendation.score_date >= pick.pick_date
                  AND recommendation.score_date <= %(as_of)s
                ORDER BY recommendation.score_date DESC
                LIMIT 1
            ) latest_recommendation ON TRUE
            LEFT JOIN LATERAL (
                SELECT trade_date, close_price
                FROM daily_prices price
                WHERE price.code = pick.code
                  AND price.trade_date >= pick.pick_date
                  AND price.trade_date <= %(as_of)s
                ORDER BY price.trade_date DESC
                LIMIT 1
            ) latest_price ON TRUE
            WHERE pick.pick_date >= %(cutoff)s
              AND pick.pick_date <= %(as_of)s
            ORDER BY pick.pick_date DESC
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, {"cutoff": cutoff, "as_of": as_of})
            rows = cur.fetchall()
        picks: list[DailyTopPick] = []
        for row in rows:
            base_close = float(row["base_close"])
            latest_close = float(row["latest_close"])
            change_pct = 0.0 if base_close <= 0 else ((latest_close - base_close) / base_close) * 100.0
            raw_features = self._ensure_json(row["raw_features_json"]) or {}
            picks.append(
                DailyTopPick(
                    pick_date=row["pick_date"],
                    recommendation_end_date=row["recommendation_end_date"],
                    code=row["code"],
                    name=row["name"],
                    sector=row["sector"],
                    score=float(row["total_score"]),
                    base_close=base_close,
                    latest_date=row["latest_date"],
                    latest_close=latest_close,
                    change_pct=change_pct,
                    reasons=self._ensure_json(row["reasons_json"]) or [],
                    risk_flags=self._ensure_json(row["risk_flags_json"]) or [],
                    market_regime=raw_features.get("market_regime", "neutral"),
                    market_regime_source=raw_features.get("market_regime_source", "breadth"),
                    market_index_name=raw_features.get("market_index_name"),
                    market_index_close=float(raw_features.get("market_index_close", 0.0) or 0.0),
                    market_index_return_pct=float(raw_features.get("market_index_return_pct", 0.0) or 0.0),
                    market_index_return_5d_pct=float(raw_features.get("market_index_return_5d_pct", 0.0) or 0.0),
                    market_index_return_20d_pct=float(raw_features.get("market_index_return_20d_pct", 0.0) or 0.0),
                    market_index_return_60d_pct=float(raw_features.get("market_index_return_60d_pct", 0.0) or 0.0),
                    market_short_trend=raw_features.get("market_short_trend", "neutral"),
                    market_mid_trend=raw_features.get("market_mid_trend", "neutral"),
                    market_long_trend=raw_features.get("market_long_trend", "neutral"),
                )
            )
        return picks


def create_postgres_repository(database_url: str) -> PostgresCandidateRepository:
    repository = PostgresCandidateRepository(database_url=database_url)
    # Connection validation on startup.
    repository.latest_score_date()
    return repository
