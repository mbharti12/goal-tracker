from datetime import date, timedelta

from app.schemas import ReviewDay, ReviewDaySummary
from app.services.review_service import (
    MAX_LLM_NOTES_SNIPPETS_CHARS,
    MAX_LLM_NOTE_CHARS_PER_DAY,
    build_notes_snippets,
)


def test_build_notes_snippets_truncates_and_keeps_recent():
    days = []
    start = date(2024, 1, 1)
    for offset in range(49):
        day_date = start + timedelta(days=offset)
        days.append(
            ReviewDay(
                date=day_date.isoformat(),
                note=("a" * (MAX_LLM_NOTE_CHARS_PER_DAY + 50)) + "TAIL",
                summary=ReviewDaySummary(
                    applicable_goals=0,
                    met_goals=0,
                    completion_ratio=0.0,
                ),
            )
        )

    snippets = build_notes_snippets(days)

    assert "... (older notes omitted)" in snippets
    assert (start + timedelta(days=48)).isoformat() + ":" in snippets
    assert "2024-01-01:" not in snippets
    assert "TAIL" not in snippets
    assert len(snippets) <= MAX_LLM_NOTES_SNIPPETS_CHARS + 100
