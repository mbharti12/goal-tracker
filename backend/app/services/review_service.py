from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import ValidationError
from sqlmodel import Session, select

from ..models import Condition, DayCondition, DayEntry, Goal
from ..schemas import QueryPlan, ReviewContext, ReviewDateRange, ReviewDay, ReviewDaySummary, ReviewFilters
from ..services import scoring
from . import ollama_client

DEFAULT_REVIEW_DAYS = 14
MAX_REVIEW_DAYS = 60
DOW_TO_INT = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def build_review_context(
    session: Session,
    start_date: str,
    end_date: str,
    *,
    days_of_week: Optional[List[str]] = None,
    conditions_all: Optional[List[str]] = None,
    conditions_any: Optional[List[str]] = None,
    goals: Optional[List[str]] = None,
    allow_more: bool = False,
) -> ReviewContext:
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start > end:
        start, end = end, start

    dates = _generate_dates(start, end)
    dates = _filter_by_days_of_week(dates, days_of_week)

    dates = _filter_by_conditions(
        session,
        dates,
        conditions_all=conditions_all,
        conditions_any=conditions_any,
    )

    truncated = False
    if not allow_more and len(dates) > MAX_REVIEW_DAYS:
        dates = dates[-MAX_REVIEW_DAYS:]
        truncated = True

    notes_by_date = _load_notes(session, dates)
    goal_name_filter = _normalize_name_list(goals)
    goal_name_set = {name.lower() for name in goal_name_filter}

    days: List[ReviewDay] = []
    for date_str in dates:
        statuses = scoring.compute_goal_statuses_for_date(session, date_str)
        if goal_name_set:
            statuses = [
                status
                for status in statuses
                if status["goal_name"].lower() in goal_name_set
            ]
        summary = _summary_from_statuses(statuses)
        days.append(
            ReviewDay(
                date=date_str,
                note=_truncate_note(notes_by_date.get(date_str)),
                summary=summary,
                goals=statuses,
            )
        )

    return ReviewContext(
        date_range=ReviewDateRange(start=start.isoformat(), end=end.isoformat()),
        filters=ReviewFilters(
            dow=days_of_week,
            conditions_all=conditions_all,
            conditions_any=conditions_any,
            goals=goals,
        ),
        days=days,
        truncated=truncated,
    )


def build_plan(session: Session, prompt: str) -> QueryPlan:
    conditions = _list_condition_names(session)
    goals = _list_goal_names(session)
    model = ollama_client.DEFAULT_MODEL

    for attempt in range(2):
        messages = _build_planner_messages(
            prompt,
            conditions=conditions,
            goals=goals,
            strict=attempt == 1,
        )
        response_text = ollama_client.chat(model, messages, temperature=0.0)
        try:
            return _parse_plan_response(response_text)
        except (json.JSONDecodeError, ValidationError, ValueError):
            continue

    return QueryPlan(last_n_days=DEFAULT_REVIEW_DAYS, intent="summary")


def resolve_date_range(plan: QueryPlan, today: Optional[date] = None) -> Tuple[str, str]:
    if today is None:
        today = date.today()

    if plan.start_date and plan.end_date:
        start = _parse_date(plan.start_date)
        end = _parse_date(plan.end_date)
    elif plan.start_date:
        start = _parse_date(plan.start_date)
        end = today
    elif plan.end_date:
        end = _parse_date(plan.end_date)
        start = end - timedelta(days=DEFAULT_REVIEW_DAYS - 1)
    elif plan.last_n_days:
        end = today
        start = end - timedelta(days=plan.last_n_days - 1)
    else:
        end = today
        start = end - timedelta(days=DEFAULT_REVIEW_DAYS - 1)

    if start > end:
        start, end = end, start

    return start.isoformat(), end.isoformat()


def prompt_requests_long_range(prompt: str) -> bool:
    if not prompt:
        return False
    lowered = prompt.lower()
    keywords = [
        "all time",
        "all-time",
        "alltime",
        "year",
        "years",
        "month",
        "months",
        "quarter",
        "quarters",
        "entire",
        "since",
        "overall",
    ]
    return any(keyword in lowered for keyword in keywords)


def build_stats_table(days: Sequence[ReviewDay]) -> str:
    if not days:
        return "No days matched the filters."
    lines = ["date | applicable | met | completion_ratio"]
    for day in days:
        ratio = f"{day.summary.completion_ratio:.2f}"
        lines.append(
            f"{day.date} | {day.summary.applicable_goals} | {day.summary.met_goals} | {ratio}"
        )
    return "\n".join(lines)


def build_notes_snippets(days: Sequence[ReviewDay]) -> str:
    snippets = []
    for day in days:
        note = (day.note or "").strip()
        if note:
            snippets.append(f"{day.date}: {note}")
    if not snippets:
        return "No notes available."
    return "\n".join(snippets)


def _build_planner_messages(
    prompt: str, *, conditions: List[str], goals: List[str], strict: bool
) -> List[Dict[str, str]]:
    schema = (
        "{\n"
        '  "start_date": "YYYY-MM-DD" | null,\n'
        '  "end_date": "YYYY-MM-DD" | null,\n'
        '  "last_n_days": int | null,\n'
        '  "days_of_week": ["mon","tue","wed","thu","fri","sat","sun"] | null,\n'
        '  "conditions_any": [string] | null,\n'
        '  "conditions_all": [string] | null,\n'
        '  "goals": [string] | null,\n'
        '  "intent": "summary"|"patterns"|"coach"|"report"\n'
        "}"
    )
    rules = [
        "Return only JSON. No markdown or extra text.",
        "Use null when a field is not specified.",
        "days_of_week must use the short lowercase form (mon..sun).",
        "intent must be one of: summary, patterns, coach, report.",
    ]
    if strict:
        rules.append("Include every key from the schema, even if null.")

    available = [
        f"Available conditions: {conditions if conditions else 'none'}",
        f"Available goals: {goals if goals else 'none'}",
    ]

    system_content = "You convert user prompts into JSON plans.\nSchema:\n"
    system_content += schema
    system_content += "\nRules:\n- " + "\n- ".join(rules)

    user_content = "\n".join(available + [f"User prompt: {prompt}"])

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def _parse_plan_response(text: str) -> QueryPlan:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = json.loads(_extract_json(text))
    return QueryPlan.model_validate(payload)


def _extract_json(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in planner response.")
    return text[start : end + 1]


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _generate_dates(start: date, end: date) -> List[str]:
    dates = []
    current = start
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def _filter_by_days_of_week(
    dates: List[str], days_of_week: Optional[List[str]]
) -> List[str]:
    if not days_of_week:
        return dates
    allowed = {DOW_TO_INT[item] for item in days_of_week}
    filtered = []
    for date_str in dates:
        weekday = datetime.strptime(date_str, "%Y-%m-%d").weekday()
        if weekday in allowed:
            filtered.append(date_str)
    return filtered


def _filter_by_conditions(
    session: Session,
    dates: List[str],
    *,
    conditions_all: Optional[List[str]],
    conditions_any: Optional[List[str]],
) -> List[str]:
    if not dates or not (conditions_all or conditions_any):
        return dates

    all_names = _normalize_name_list(conditions_all)
    any_names = _normalize_name_list(conditions_any)
    resolved_all, missing_all = _resolve_condition_ids(session, all_names)
    resolved_any, missing_any = _resolve_condition_ids(session, any_names)

    if missing_all:
        return []
    if missing_any and not resolved_any:
        return []

    condition_ids = sorted(set(resolved_all + resolved_any))
    if not condition_ids:
        return dates

    rows = session.exec(
        select(DayCondition)
        .where(
            DayCondition.date.in_(dates),
            DayCondition.condition_id.in_(condition_ids),
            DayCondition.value == True,
        )
        .order_by(DayCondition.date)
    ).all()
    conditions_by_date: Dict[str, set] = {}
    for row in rows:
        conditions_by_date.setdefault(row.date, set()).add(row.condition_id)

    filtered = []
    required_all = set(resolved_all)
    required_any = set(resolved_any)
    for date_str in dates:
        day_conditions = conditions_by_date.get(date_str, set())
        if required_all and not required_all.issubset(day_conditions):
            continue
        if required_any and not (required_any & day_conditions):
            continue
        filtered.append(date_str)
    return filtered


def _resolve_condition_ids(
    session: Session, names: Sequence[str]
) -> Tuple[List[int], List[str]]:
    if not names:
        return [], []
    rows = session.exec(select(Condition)).all()
    name_map = {row.name.lower(): row.id for row in rows}
    resolved = []
    missing = []
    for name in names:
        key = name.lower()
        if key in name_map:
            resolved.append(name_map[key])
        else:
            missing.append(name)
    return resolved, missing


def _list_condition_names(session: Session) -> List[str]:
    rows = session.exec(select(Condition).order_by(Condition.name)).all()
    return [row.name for row in rows]


def _list_goal_names(session: Session) -> List[str]:
    rows = session.exec(select(Goal).where(Goal.active == True)).all()
    return [row.name for row in rows]


def _load_notes(session: Session, dates: Iterable[str]) -> Dict[str, Optional[str]]:
    if not dates:
        return {}
    rows = session.exec(select(DayEntry).where(DayEntry.date.in_(dates))).all()
    return {row.date: row.note for row in rows}


def _truncate_note(note: Optional[str]) -> Optional[str]:
    if note is None:
        return None
    return note[:1200]


def _normalize_name_list(values: Optional[Sequence[str]]) -> List[str]:
    if not values:
        return []
    cleaned = []
    for value in values:
        if value is None:
            continue
        stripped = value.strip()
        if stripped:
            cleaned.append(stripped)
    return cleaned


def _summary_from_statuses(statuses: Sequence[Dict]) -> ReviewDaySummary:
    applicable_goals = sum(1 for goal in statuses if goal["applicable"])
    met_goals = sum(1 for goal in statuses if goal["status"] == "met")
    completion_ratio = met_goals / applicable_goals if applicable_goals else 0
    return ReviewDaySummary(
        applicable_goals=applicable_goals,
        met_goals=met_goals,
        completion_ratio=completion_ratio,
    )
