from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from sqlmodel import Session, select

from ..models import (
    DayCondition,
    Goal,
    GoalCondition,
    GoalRating,
    GoalTag,
    GoalVersion,
    GoalVersionCondition,
    GoalVersionTag,
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


def _load_goal_versions(
    session: Session, goal_ids: Iterable[int]
) -> Dict[int, List[GoalVersion]]:
    versions_by_goal: Dict[int, List[GoalVersion]] = defaultdict(list)
    if not goal_ids:
        return versions_by_goal

    rows = session.exec(
        select(GoalVersion).where(GoalVersion.goal_id.in_(goal_ids))
    ).all()
    for row in rows:
        versions_by_goal[row.goal_id].append(row)
    return versions_by_goal


def _select_effective_version(
    versions: Iterable[GoalVersion], date_str: str
) -> Optional[GoalVersion]:
    effective: Optional[GoalVersion] = None
    for version in versions:
        if version.start_date > date_str:
            continue
        if version.end_date is not None and version.end_date < date_str:
            continue
        if effective is None or version.start_date > effective.start_date:
            effective = version
    return effective


def _load_version_tags(
    session: Session, version_ids: Iterable[int]
) -> Dict[int, Dict[int, int]]:
    tags_by_version: Dict[int, Dict[int, int]] = defaultdict(dict)
    if not version_ids:
        return tags_by_version

    rows = session.exec(
        select(GoalVersionTag).where(GoalVersionTag.goal_version_id.in_(version_ids))
    ).all()
    for row in rows:
        tags_by_version[row.goal_version_id][row.tag_id] = row.weight
    return tags_by_version


def _load_version_conditions(
    session: Session, version_ids: Iterable[int]
) -> Dict[int, List[Tuple[int, bool]]]:
    conditions_by_version: Dict[int, List[Tuple[int, bool]]] = defaultdict(list)
    if not version_ids:
        return conditions_by_version

    rows = session.exec(
        select(GoalVersionCondition).where(
            GoalVersionCondition.goal_version_id.in_(version_ids)
        )
    ).all()
    for row in rows:
        conditions_by_version[row.goal_version_id].append(
            (row.condition_id, row.required_value)
        )
    return conditions_by_version


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
    versions_by_goal = _load_goal_versions(session, goal_ids)
    version_ids = [
        version.id
        for versions in versions_by_goal.values()
        for version in versions
        if version.id is not None
    ]
    version_tags = _load_version_tags(session, version_ids)
    version_conditions = _load_version_conditions(session, version_ids)
    day_conditions = _load_day_conditions(session, date_str)

    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    week_start, _ = get_week_bounds(date_str)
    week_start_str = week_start.isoformat()
    month_start, _ = get_month_bounds(date_str)
    month_start_str = month_start.isoformat()
    range_start = min(week_start, month_start)
    range_start_str = range_start.isoformat()
    range_end_str = date_str

    version_selection: Dict[int, Tuple[Optional[GoalVersion], bool]] = {}
    for goal in goals:
        versions = versions_by_goal.get(goal.id, [])
        effective = _select_effective_version(versions, date_str)
        if effective is not None:
            version_selection[goal.id] = (effective, True)
        elif versions:
            earliest = min(versions, key=lambda version: version.start_date)
            latest = max(versions, key=lambda version: version.start_date)
            fallback = earliest if date_str < earliest.start_date else latest
            version_selection[goal.id] = (fallback, True)
        else:
            version_selection[goal.id] = (None, True)

    tag_ids = set()
    for goal in goals:
        version, _ = version_selection.get(goal.id, (None, True))
        if version is not None and version.id is not None:
            tag_ids.update(version_tags.get(version.id, {}).keys())
        else:
            tag_ids.update(goal_tags.get(goal.id, {}).keys())
    events_by_tag_and_date = _load_tag_events(
        session, tag_ids, range_start_str, range_end_str
    )
    events_by_tag_week = _sum_events_by_tag(
        events_by_tag_and_date, week_start_str, date_str
    )
    events_by_tag_month = _sum_events_by_tag(
        events_by_tag_and_date, month_start_str, date_str
    )

    rating_goal_ids = []
    rating_window_starts = []
    for goal in goals:
        version, _ = version_selection.get(goal.id, (None, True))
        scoring_mode = version.scoring_mode if version is not None else goal.scoring_mode
        target_window = (
            version.target_window if version is not None else goal.target_window
        )
        if scoring_mode != ScoringMode.rating:
            continue
        rating_goal_ids.append(goal.id)
        if target_window == TargetWindow.week:
            rating_window_starts.append(week_start)
        elif target_window == TargetWindow.month:
            rating_window_starts.append(month_start)
        else:
            rating_window_starts.append(day)
    if rating_goal_ids:
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
        version, _ = version_selection.get(goal.id, (None, True))
        if version is not None:
            conditions = version_conditions.get(version.id, [])
            tag_weights = version_tags.get(version.id, {})
            target_window = version.target_window
            target_count = version.target_count
            scoring_mode = version.scoring_mode
            goal_version_id = version.id or 0
        else:
            conditions = goal_conditions.get(goal.id, [])
            tag_weights = goal_tags.get(goal.id, {})
            target_window = goal.target_window
            target_count = goal.target_count
            scoring_mode = goal.scoring_mode
            goal_version_id = 0

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
        target_window_value = target_window.value
        if applicable:
            if scoring_mode == ScoringMode.rating:
                if target_window == TargetWindow.week:
                    window_start = week_start
                elif target_window == TargetWindow.month:
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
                status = "met" if avg >= target_count else "missed"
            else:
                if target_window == TargetWindow.week:
                    for tag_id, weight in tag_weights.items():
                        progress += events_by_tag_week.get(tag_id, 0) * weight
                elif target_window == TargetWindow.month:
                    for tag_id, weight in tag_weights.items():
                        progress += events_by_tag_month.get(tag_id, 0) * weight
                else:
                    for tag_id, weight in tag_weights.items():
                        progress += (
                            events_by_tag_and_date.get((tag_id, date_str), 0) * weight
                        )

                if progress >= target_count:
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
                "goal_version_id": goal_version_id,
                "goal_name": goal.name,
                "applicable": applicable,
                "status": status,
                "progress": progress,
                "target": target_count,
                "samples": samples,
                "window_days": window_days,
                "target_window": target_window_value,
                "scoring_mode": scoring_mode,
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
