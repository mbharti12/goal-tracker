from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Tuple

from sqlmodel import Session, select

from ..models import DayCondition, Goal, GoalCondition, GoalTag, TagEvent, TargetWindow


def get_week_bounds(date_str: str) -> Tuple[date, date]:
    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    week_start = day - timedelta(days=day.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


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
) -> Tuple[Dict[Tuple[int, str], int], Dict[int, int]]:
    events_by_tag_and_date: Dict[Tuple[int, str], int] = defaultdict(int)
    events_by_tag_week: Dict[int, int] = defaultdict(int)
    if not tag_ids:
        return events_by_tag_and_date, events_by_tag_week

    rows = session.exec(
        select(TagEvent).where(
            TagEvent.tag_id.in_(tag_ids),
            TagEvent.date >= start_date,
            TagEvent.date <= end_date,
        )
    ).all()
    for row in rows:
        events_by_tag_and_date[(row.tag_id, row.date)] += row.count
        events_by_tag_week[row.tag_id] += row.count
    return events_by_tag_and_date, events_by_tag_week


def compute_goal_statuses_for_date(session: Session, date_str: str) -> List[dict]:
    goals = _load_goals(session)
    if not goals:
        return []

    goal_ids = [goal.id for goal in goals if goal.id is not None]
    goal_tags = _load_goal_tags(session, goal_ids)
    goal_conditions = _load_goal_conditions(session, goal_ids)
    day_conditions = _load_day_conditions(session, date_str)

    week_start, week_end = get_week_bounds(date_str)
    week_start_str = week_start.isoformat()
    week_end_str = week_end.isoformat()

    tag_ids = {tag_id for tags in goal_tags.values() for tag_id in tags.keys()}
    events_by_tag_and_date, events_by_tag_week = _load_tag_events(
        session, tag_ids, week_start_str, week_end_str
    )

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

        progress = 0
        if applicable:
            tag_weights = goal_tags.get(goal.id, {})
            if goal.target_window == TargetWindow.week:
                for tag_id, weight in tag_weights.items():
                    progress += events_by_tag_week.get(tag_id, 0) * weight
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
            progress = 0

        statuses.append(
            {
                "goal_id": goal.id,
                "goal_name": goal.name,
                "applicable": applicable,
                "status": status,
                "progress": progress,
                "target": goal.target_count,
                "target_window": goal.target_window.value,
            }
        )

    return statuses


def compute_day_summary(session: Session, date_str: str) -> dict:
    goal_statuses = compute_goal_statuses_for_date(session, date_str)
    applicable_goals = sum(1 for goal in goal_statuses if goal["applicable"])
    met_goals = sum(1 for goal in goal_statuses if goal["status"] == "met")
    completion_ratio = met_goals / applicable_goals if applicable_goals else 0
    return {
        "date": date_str,
        "applicable_goals": applicable_goals,
        "met_goals": met_goals,
        "completion_ratio": completion_ratio,
    }
