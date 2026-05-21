from __future__ import annotations

import argparse
from datetime import date, datetime, timezone

from app.batch import evaluate_daily_batch_with_surge
from app.postgres_repository import create_postgres_repository
from app.repository import select_top_candidates
from app.settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate daily candidate scores from stored daily_prices.")
    parser.add_argument("--date", dest="score_date", help="Batch date in YYYY-MM-DD format. Defaults to latest trade date.")
    parser.add_argument("--history-limit", type=int, default=90, help="Number of historical rows per stock to load.")
    parser.add_argument("--min-score", type=float, default=60.0, help="Minimum score for top candidate selection.")
    parser.add_argument("--max-per-sector", type=int, default=3, help="Maximum selected candidates per sector.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of selected candidates to print.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set.")

    repo = create_postgres_repository(settings.database_url)
    score_date = date.fromisoformat(args.score_date) if args.score_date else repo.latest_trade_date()
    if score_date is None:
        raise SystemExit("No daily_prices data found. Load real price data first.")

    price_rows = repo.fetch_price_history_for_batch(score_date=score_date, history_limit=args.history_limit)
    warning_rows = repo.fetch_market_warnings_for_date(score_date)
    disclosure_rows = repo.fetch_disclosures_for_date(score_date)
    fetch_news_rows = getattr(repo, "fetch_news_for_date", None)
    news_rows = fetch_news_rows(score_date) if callable(fetch_news_rows) else []
    generated_at = datetime.now(timezone.utc)

    evaluations = evaluate_daily_batch_with_surge(
        score_date=score_date,
        price_rows=price_rows,
        warning_rows=warning_rows,
        disclosure_rows=disclosure_rows,
        news_rows=news_rows,
        generated_at=generated_at,
    )
    carry_forward_codes: set[str] = set()
    for prior_date in repo.available_trade_dates(limit=20):
        if prior_date >= score_date:
            continue
        for prior in repo.get_daily_scores(prior_date):
            if prior.snapshot.candidate_profile == "trend":
                carry_forward_codes.add(prior.snapshot.code)
        if len(carry_forward_codes) >= 20:
            break

    selected = select_top_candidates(
        evaluations,
        min_score=args.min_score,
        max_per_sector=args.max_per_sector,
        limit=args.limit,
        separate_profiles=True,
        carry_forward_codes=carry_forward_codes,
    )
    persist_scores = getattr(repo, "replace_daily_scores", None)
    if callable(persist_scores):
        persist_scores(score_date, selected)
    else:
        repo.upsert_daily_scores(score_date, selected)
    repo.refresh_daily_top_picks(score_date)

    print(f"Score date: {score_date.isoformat()}")
    print(f"Evaluated stocks: {len(evaluations)}")
    print(f"Selection min score: {args.min_score:.2f}")
    print(f"Persisted candidates: {len(selected)}")
    if selected:
        print("Top candidates:")
        for index, item in enumerate(selected[:10], start=1):
            print(
                f"{index}. {item.snapshot.code} {item.snapshot.name} "
                f"{item.score:.2f} {item.snapshot.sector}"
            )


if __name__ == "__main__":
    main()
