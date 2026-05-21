from __future__ import annotations

from app.scripts.run_daily_batch import build_parser


def test_run_daily_batch_parser_accepts_selection_options() -> None:
    args = build_parser().parse_args(
        [
            "--date",
            "2026-04-29",
            "--min-score",
            "30",
            "--max-per-sector",
            "2",
            "--limit",
            "5",
        ]
    )

    assert args.score_date == "2026-04-29"
    assert args.min_score == 30.0
    assert args.max_per_sector == 2
    assert args.limit == 5
