from __future__ import annotations

import psycopg

from app.settings import load_settings


def scalar_count(conn: psycopg.Connection, table_name: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (table_name,))
        if cur.fetchone()[0] is None:
            return 0
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        row = cur.fetchone()
    return int(row[0]) if row else 0


def main() -> None:
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set.")

    with psycopg.connect(settings.database_url) as conn:
        print("Connected to PostgreSQL.")
        for table_name in [
            "stock_master",
            "daily_prices",
            "daily_disclosures",
            "daily_news",
            "daily_market_warnings",
            "daily_candidate_scores",
            "backtest_summaries",
        ]:
            print(f"{table_name}: {scalar_count(conn, table_name)}")


if __name__ == "__main__":
    main()
