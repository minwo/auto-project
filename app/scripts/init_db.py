from __future__ import annotations

from pathlib import Path

import psycopg

from app.settings import load_settings


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def ensure_database_exists(admin_url: str, database_name: str) -> None:
    query = f"SELECT 1 FROM pg_database WHERE datname = %s"
    with psycopg.connect(admin_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(query, (database_name,))
        exists = cur.fetchone()
        if exists:
            print(f"Database already exists: {database_name}")
            return
        cur.execute(f"CREATE DATABASE {_quote_identifier(database_name)}")
        print(f"Database created: {database_name}")


def apply_schema(database_url: str) -> None:
    schema_path = Path("sql/schema.sql")
    sql = schema_path.read_text(encoding="utf-8")
    with psycopg.connect(database_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(sql)
    print(f"Schema applied from {schema_path}")


def main() -> None:
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set. Create a .env file or export DATABASE_URL first.")

    if settings.postgres_admin_url and settings.database_name:
        ensure_database_exists(settings.postgres_admin_url, settings.database_name)
    elif settings.database_name:
        print("POSTGRES_ADMIN_URL is not set. Skipping CREATE DATABASE step and applying schema only.")

    apply_schema(settings.database_url)
    print("Database initialization complete.")


if __name__ == "__main__":
    main()
