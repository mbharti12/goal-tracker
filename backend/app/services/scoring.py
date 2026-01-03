from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Tuple

from sqlmodel import Session, select

from ..models import (
    DayCondition,
    Goal,
    GoalCondition,
    GoalRating,
    GoalTag,
    ScoringMode,
    TagEvent,
    TargetWindow,
)


def get_week_bounds(date_str: str) -> Tuple[date, date]:
    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    week_start = day - timedelta(days=day.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def get_month_bounds(date_str: str) -> Tuple[date, date]:
    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    month_start = day.replace(day=1)
    month_end = day.replace(day=monthrange(day.year, day.month)[1])
    return month_start, month_end


def _load_goals(session: Session) -> List[Goal]:
    return session.exec(select(Goal).where(Goal.active == True)).all()


def _load_goal_tags(
    session: Session, goal_ids: Iterable[int]
) -> Dict[int, Dict[int, int]]:
    tags_by_goal: Dict[int, Dict[int, int]] = defaultdict(dict)
    if not goal_ids:
        return tags_by_goal

    rows = session.exec(select(GoalTag).where(GoalTag.goal_id.in_(goal_ids))).all()
    for row in rows:
        tags_by_goal[row.goal_id][row.tag_id] = row.weight
    return tags_by_goal


def _load_goal_conditions(
    session: Session, goal_ids: Iterable[int]
) -> Dict[int, List[Tuple[int, bool]]]:
    conditions_by_goal: Dict[int, List[Tuple[int, bool]]] = defaultdict(list)
    if not goal_ids:
        return conditions_by_goal

    rows = session.exec(
        select(GoalCondition).where(GoalCondition.goal_id.in_(goal_ids))
    ).all()
    for row in rows:
        conditions_by_goal[row.goal_id].append((row.condition_id, row.required_value))
    return conditions_by_goal


def _load_day_conditions(session: Session, date_str: str) -> Dict[int, bool]:
    rows = session.exec(
        select(DayCondition).where(DayCondition.date == date_str)
    ).all()
    return {row.condition_id: row.value for row in rows}


def _load_tag_events(
    session: Session, tag_ids: Iterable[int], start_date: str, end_date: str
) -> Dict[Tuple[int, str], int]:
    events_by_tag_and_date: Dict[Tuple[int, str], int] = defaultdict(int)
    if not tag_ids:
        return events_by_tag_and_date

    rows = session.exec(
        select(TagEvent).where(
            TagEvent.tag_id.in_(tag_ids),
            TagEvent.date >= start_date,
            TagEvent.date <= end_date,
        )
    ).all()
    for row in rows:
        events_by_tag_and_date[(row.tag_id, row.date)] += row.count
    return events_by_tag_and_date


def _sum_events_by_tag(
    events_by_tag_and_date: Dict[Tuple[int, str], int],
    start_date: str,
    end_date: str,
) -> Dict[int, int]:
    totals: Dict[int, int] = defaultdict(int)
    for (tag_id, event_date), count in events_by_tag_and_date.items():
        if start_date <= event_date <= end_date:
            totals[tag_id] += count
    return totals


def _load_goal_ratings(
    session: Session, start_date: str, end_date: str, goal_ids: Iterable[int]
) -> Dict[int, List[GoalRating]]:
    ratings_by_goal: Dict[int, List[GoalRating]] = defaultdict(list)
    if not goal_ids:
        return ratings_by_goal

    rows = session.exec(
        select(GoalRating).where(
            GoalRating.goal_id.in_(goal_ids),
            GoalRating.date >= start_date,
            GoalRating.date <= end_date,
        )
    ).all()
    for row in rows:
        ratings_by_goal[row.goal_id].append(row)
    return ratings_by_goal


def compute_goal_statuses_for_date(session: Session, date_str: str) -> List[dict]:
    goals = _load_goals(session)
    if not goals:
        return []

    goal_ids = [goal.id for goal in goals if goal.id is not None]
    goal_tags = _load_goal_tags(session, goal_ids)
    goal_conditions = _load_goal_conditions(session, goal_ids)
    day_conditions = _load_day_conditions(session, date_str)

    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    week_start, _ = get_week_bounds(date_str)
    week_start_str = week_start.isoformat()
    month_start, _ = get_month_bounds(date_str)
    month_start_str = month_start.isoformat()
    range_start = min(week_start, month_start)
    range_start_str = range_start.isoformat()
    range_end_str = date_str

    tag_ids = {tag_id for tags in goal_tags.values() for tag_id in tags.keys()}
    events_by_tag_and_date = _load_tag_events(
        session, tag_ids, range_start_str, range_end_str
    )
    events_by_tag_week = _sum_events_by_tag(
        events_by_tag_and_date, week_start_str, date_str
    )
    events_by_tag_month = _sum_events_by_tag(
        events_by_tag_and_date, month_start_str, date_str
    )

    rating_goal_ids = [
        goal.id
        for goal in goals
        if goal.id is not None and goal.scoring_mode == ScoringMode.rating
    ]
    if rating_goal_ids:
        rating_window_starts = []
        for goal in goals:
            if goal.scoring_mode != ScoringMode.rating:
                continue
            if goal.target_window == TargetWindow.week:
                rating_window_starts.append(week_start)
            elif goal.target_window == TargetWindow.month:
                rating_window_starts.append(month_start)
            else:
                rating_window_starts.append(day)
        rating_range_start = min(rating_window_starts) if rating_window_starts else day
        ratings_by_goal = _load_goal_ratings(
            session,
            rating_range_start.isoformat(),
            date_str,
            rating_goal_ids,
        )
    else:
        ratings_by_goal = {}

    statuses: List[dict] = []
    for goal in goals:
        conditions = goal_conditions.get(goal.id, [])
        if not conditions:
            applicable = True
        else:
            applicable = True
            for condition_id, required_value in conditions:
                if day_conditions.get(condition_id, False) != required_value:
                    applicable = False
                    break

        progress = 0.0
        samples = 0
        window_days = 0
        target_window_value = goal.target_window.value
        if applicable:
            if goal.scoring_mode == ScoringMode.rating:
                if goal.target_window == TargetWindow.week:
                    window_start = week_start
                elif goal.target_window == TargetWindow.month:
                    window_start = month_start
                else:
                    window_start = day
                window_days = (day - window_start).days + 1
                window_start_str = window_start.isoformat()
                sum_ratings = 0
                for rating in ratings_by_goal.get(goal.id, []):
                    if window_start_str <= rating.date <= date_str:
                        sum_ratings += rating.rating
                        samples += 1
                avg = sum_ratings / window_days if window_days else 0.0
                progress = avg
                status = "met" if avg >= goal.target_count else "missed"
            else:
                tag_weights = goal_tags.get(goal.id, {})
                if goal.target_window == TargetWindow.week:
                    for tag_id, weight in tag_weights.items():
                        progress += events_by_tag_week.get(tag_id, 0) * weight
                elif goal.target_window == TargetWindow.month:
                    for tag_id, weight in tag_weights.items():
                        progress += events_by_tag_month.get(tag_id, 0) * weight
                else:
                    for tag_id, weight in tag_weights.items():
                        progress += (
                            events_by_tag_and_date.get((tag_id, date_str), 0) * weight
                        )

                if progress >= goal.target_count:
                    status = "met"
                elif progress > 0:
                    status = "partial"
                else:
                    status = "missed"
        else:
            status = "na"
            progress = 0.0
            samples = 0
            window_days = 0

        statuses.append(
            {
                "goal_id": goal.id,
                "goal_name": goal.name,
                "applicable": applicable,
                "status": status,
                "progress": progress,
                "target": goal.target_count,
                "samples": samples,
                "window_days": window_days,
                "target_window": target_window_value,
                "scoring_mode": goal.scoring_mode,
            }
        )

    return statuses


def compute_day_summary(session: Session, date_str: str) -> dict:
    goal_statuses = compute_goal_statuses_for_date(session, date_str)
    summary = summarize_goal_statuses(goal_statuses)
    summary["date"] = date_str
    return summary


def summarize_goal_statuses(goal_statuses: Iterable[dict]) -> dict:
    applicable_goals = sum(1 for goal in goal_statuses if goal["applicable"])
    met_goals = sum(1 for goal in goal_statuses if goal["status"] == "met")
    completion_ratio = met_goals / applicable_goals if applicable_goals else 0
    return {
        "applicable_goals": applicable_goals,
        "met_goals": met_goals,
        "completion_ratio": completion_ratio,
    }


def compute_day_summary_for_window(
    session: Session, date_str: str, target_window: TargetWindow
) -> dict:
    goal_statuses = compute_goal_statuses_for_date(session, date_str)
    filtered = [
        goal
        for goal in goal_statuses
        if goal["target_window"] == target_window.value
    ]
    summary = summarize_goal_statuses(filtered)
    summary["date"] = date_str
    return summary


def compute_window_summary(
    session: Session, date_str: str, target_window: TargetWindow
) -> dict:
    goal_statuses = compute_goal_statuses_for_date(session, date_str)
    filtered = [
        goal
        for goal in goal_statuses
        if goal["target_window"] == target_window.value
    ]
    return summarize_goal_statuses(filtered)
