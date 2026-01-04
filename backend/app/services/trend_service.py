from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from sqlmodel import Session, select

from ..models import (
    DayCondition,
    Goal,
    GoalRating,
    GoalVersion,
    GoalVersionCondition,
    GoalVersionTag,
    ScoringMode,
    TagEvent,
    TargetWindow,
)
from .scoring import get_month_bounds, get_week_bounds


def build_trend_series(
    session: Session, goal_ids: List[int], start: str, end: str, bucket: str
) -> List[dict]:
    start_date, end_date = _normalize_dates(start, end)
    goals = _load_goals(session, goal_ids)
    points_meta = _build_bucket_points(start_date, end_date, bucket)
    if not goals:
        return []

    range_start = min(
        get_week_bounds(start_date.isoformat())[0],
        get_month_bounds(start_date.isoformat())[0],
    )
    date_list, date_index = _build_date_index(range_start, end_date)

    versions_by_goal = _load_versions(session, goal_ids)
    version_ids = [
        version.id
        for versions in versions_by_goal.values()
        for version in versions
        if version.id is not None
    ]
    version_tags = _load_version_tags(session, version_ids)
    version_conditions = _load_version_conditions(session, version_ids)

    tag_ids = {
        tag_id for tags in version_tags.values() for tag_id in tags.keys()
    }
    tag_prefix = _build_tag_prefix(
        session, tag_ids, range_start, end_date, date_index, len(date_list)
    )

    rating_goal_ids = [
        goal_id
        for goal_id, versions in versions_by_goal.items()
        for version in versions
        if version.scoring_mode == ScoringMode.rating
    ]
    rating_goal_ids = sorted(set(rating_goal_ids))
    rating_values, rating_samples = _build_rating_prefix(
        session,
        rating_goal_ids,
        range_start,
        end_date,
        date_index,
        len(date_list),
    )

    day_conditions = _load_day_conditions(session, start_date, end_date)

    series: List[dict] = []
    for goal in goals:
        versions = versions_by_goal.get(goal.id, [])
        points: List[dict] = []
        for point in points_meta:
            point_date = point["date"]
            version = _select_effective_version(versions, point_date)
            if version is None and versions:
                earliest = min(versions, key=lambda item: item.start_date)
                latest = max(versions, key=lambda item: item.start_date)
                version = earliest if point_date < earliest.start_date else latest

            if version is None:
                target_window = goal.target_window
                target_count = goal.target_count
                scoring_mode = goal.scoring_mode
                goal_version_id = 0
                tag_weights = {}
                conditions = []
            else:
                target_window = version.target_window
                target_count = version.target_count
                scoring_mode = version.scoring_mode
                goal_version_id = version.id or 0
                tag_weights = version_tags.get(goal_version_id, {})
                conditions = version_conditions.get(goal_version_id, [])

            applicable = _is_applicable(day_conditions, point_date, conditions)

            progress = 0.0
            samples = 0
            window_days = 0
            if applicable:
                if scoring_mode == ScoringMode.rating:
                    window_start = _window_start(point_date, target_window)
                    window_days = _window_days(window_start, point_date)
                    sum_ratings = _sum_prefix(
                        rating_values.get(goal.id, []),
                        date_index,
                        window_start,
                        point_date,
                    )
                    samples = _sum_prefix(
                        rating_samples.get(goal.id, []),
                        date_index,
                        window_start,
                        point_date,
                    )
                    progress = sum_ratings / window_days if window_days else 0.0
                    status = "met" if progress >= target_count else "missed"
                else:
                    window_start = _window_start(point_date, target_window)
                    for tag_id, weight in tag_weights.items():
                        total = _sum_prefix(
                            tag_prefix.get(tag_id, []),
                            date_index,
                            window_start,
                            point_date,
                        )
                        progress += total * weight
                    if progress >= target_count:
                        status = "met"
                    elif progress > 0:
                        status = "partial"
                    else:
                        status = "missed"
            else:
                status = "na"

            ratio = progress / target_count if target_count else 0.0

            points.append(
                {
                    "date": point_date,
                    "period_start": point["period_start"],
                    "period_end": point["period_end"],
                    "goal_version_id": goal_version_id,
                    "applicable": applicable,
                    "status": status,
                    "progress": progress,
                    "target": target_count,
                    "ratio": ratio,
                    "samples": samples,
                    "window_days": window_days,
                    "target_window": target_window.value,
                    "scoring_mode": scoring_mode,
                }
            )

        series.append(
            {
                "goal_id": goal.id,
                "goal_name": goal.name,
                "points": points,
            }
        )

    return series


def _normalize_dates(start: str, end: str) -> Tuple[date, date]:
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    return start_date, end_date


def _load_goals(session: Session, goal_ids: Iterable[int]) -> List[Goal]:
    if not goal_ids:
        return []
    return session.exec(select(Goal).where(Goal.id.in_(goal_ids))).all()


def _load_versions(session: Session, goal_ids: Iterable[int]) -> Dict[int, List[GoalVersion]]:
    versions_by_goal: Dict[int, List[GoalVersion]] = defaultdict(list)
    if not goal_ids:
        return versions_by_goal
    rows = session.exec(
        select(GoalVersion).where(GoalVersion.goal_id.in_(goal_ids))
    ).all()
    for row in rows:
        versions_by_goal[row.goal_id].append(row)
    return versions_by_goal


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


def _load_day_conditions(
    session: Session, start_date: date, end_date: date
) -> Dict[str, Dict[int, bool]]:
    rows = session.exec(
        select(DayCondition).where(
            DayCondition.date >= start_date.isoformat(),
            DayCondition.date <= end_date.isoformat(),
        )
    ).all()
    conditions_by_date: Dict[str, Dict[int, bool]] = defaultdict(dict)
    for row in rows:
        conditions_by_date[row.date][row.condition_id] = row.value
    return conditions_by_date


def _build_tag_prefix(
    session: Session,
    tag_ids: Iterable[int],
    start_date: date,
    end_date: date,
    date_index: Dict[str, int],
    total_days: int,
) -> Dict[int, List[int]]:
    prefix_by_tag: Dict[int, List[int]] = {}
    if not tag_ids:
        return prefix_by_tag

    daily_counts: Dict[int, List[int]] = {
        tag_id: [0] * total_days for tag_id in tag_ids
    }
    rows = session.exec(
        select(TagEvent).where(
            TagEvent.tag_id.in_(tag_ids),
            TagEvent.date >= start_date.isoformat(),
            TagEvent.date <= end_date.isoformat(),
        )
    ).all()
    for row in rows:
        idx = date_index.get(row.date)
        if idx is None:
            continue
        daily_counts[row.tag_id][idx] += row.count

    for tag_id, counts in daily_counts.items():
        running = 0
        prefix = []
        for value in counts:
            running += value
            prefix.append(running)
        prefix_by_tag[tag_id] = prefix
    return prefix_by_tag


def _build_rating_prefix(
    session: Session,
    goal_ids: Iterable[int],
    start_date: date,
    end_date: date,
    date_index: Dict[str, int],
    total_days: int,
) -> Tuple[Dict[int, List[int]], Dict[int, List[int]]]:
    values_by_goal: Dict[int, List[int]] = {}
    samples_by_goal: Dict[int, List[int]] = {}
    if not goal_ids:
        return values_by_goal, samples_by_goal

    daily_values: Dict[int, List[int]] = {
        goal_id: [0] * total_days for goal_id in goal_ids
    }
    daily_samples: Dict[int, List[int]] = {
        goal_id: [0] * total_days for goal_id in goal_ids
    }
    rows = session.exec(
        select(GoalRating).where(
            GoalRating.goal_id.in_(goal_ids),
            GoalRating.date >= start_date.isoformat(),
            GoalRating.date <= end_date.isoformat(),
        )
    ).all()
    for row in rows:
        idx = date_index.get(row.date)
        if idx is None:
            continue
        daily_values[row.goal_id][idx] = row.rating
        daily_samples[row.goal_id][idx] = 1

    for goal_id, values in daily_values.items():
        running = 0
        prefix = []
        for value in values:
            running += value
            prefix.append(running)
        values_by_goal[goal_id] = prefix

    for goal_id, samples in daily_samples.items():
        running = 0
        prefix = []
        for value in samples:
            running += value
            prefix.append(running)
        samples_by_goal[goal_id] = prefix

    return values_by_goal, samples_by_goal


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


def _build_bucket_points(
    start_date: date, end_date: date, bucket: str
) -> List[dict]:
    points: List[dict] = []
    if bucket == "day":
        current = start_date
        while current <= end_date:
            date_str = current.isoformat()
            points.append(
                {
                    "date": date_str,
                    "period_start": date_str,
                    "period_end": date_str,
                }
            )
            current += timedelta(days=1)
        return points

    if bucket == "week":
        week_start = start_date - timedelta(days=start_date.weekday())
        while week_start <= end_date:
            week_end = week_start + timedelta(days=6)
            points.append(
                {
                    "date": min(week_end, end_date).isoformat(),
                    "period_start": week_start.isoformat(),
                    "period_end": week_end.isoformat(),
                }
            )
            week_start += timedelta(days=7)
        return points

    month_start = start_date.replace(day=1)
    while month_start <= end_date:
        last_day = monthrange(month_start.year, month_start.month)[1]
        month_end = month_start.replace(day=last_day)
        points.append(
            {
                "date": min(month_end, end_date).isoformat(),
                "period_start": month_start.isoformat(),
                "period_end": month_end.isoformat(),
            }
        )
        if month_start.month == 12:
            month_start = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_start = month_start.replace(month=month_start.month + 1)
    return points


def _build_date_index(
    start_date: date, end_date: date
) -> Tuple[List[str], Dict[str, int]]:
    dates: List[str] = []
    index: Dict[str, int] = {}
    current = start_date
    idx = 0
    while current <= end_date:
        date_str = current.isoformat()
        dates.append(date_str)
        index[date_str] = idx
        idx += 1
        current += timedelta(days=1)
    return dates, index


def _window_start(date_str: str, target_window: TargetWindow) -> str:
    if target_window == TargetWindow.week:
        start, _ = get_week_bounds(date_str)
        return start.isoformat()
    if target_window == TargetWindow.month:
        start, _ = get_month_bounds(date_str)
        return start.isoformat()
    return date_str


def _window_days(window_start: str, date_str: str) -> int:
    start = datetime.strptime(window_start, "%Y-%m-%d").date()
    end = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (end - start).days + 1


def _sum_prefix(
    prefix: List[int],
    date_index: Dict[str, int],
    start_date: str,
    end_date: str,
) -> int:
    if not prefix:
        return 0
    start_idx = date_index.get(start_date)
    end_idx = date_index.get(end_date)
    if start_idx is None or end_idx is None:
        return 0
    if end_idx < start_idx:
        return 0
    if start_idx == 0:
        return prefix[end_idx]
    return prefix[end_idx] - prefix[start_idx - 1]


def _is_applicable(
    day_conditions: Dict[str, Dict[int, bool]],
    date_str: str,
    conditions: List[Tuple[int, bool]],
) -> bool:
    if not conditions:
        return True
    values = day_conditions.get(date_str, {})
    for condition_id, required_value in conditions:
        if values.get(condition_id, False) != required_value:
            return False
    return True
