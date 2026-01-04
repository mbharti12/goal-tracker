from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlmodel import Session, select

from .. import db
from ..models import AppState, Notification, ScoringMode
from ..settings import settings
from . import scoring, trend_service

logger = logging.getLogger("goal-tracker")

STATE_KEY = "reminders.last_run_at"


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _get_last_run_at(session: Session) -> Optional[datetime]:
    state = session.get(AppState, STATE_KEY)
    if state is None:
        return None
    return _parse_datetime(state.value)


def _upsert_last_run_at(session: Session, timestamp: datetime) -> AppState:
    state = session.get(AppState, STATE_KEY)
    iso_timestamp = timestamp.isoformat()
    if state is None:
        state = AppState(key=STATE_KEY, value=iso_timestamp, updated_at=timestamp)
    else:
        state.value = iso_timestamp
        state.updated_at = timestamp
    session.add(state)
    return state


def _build_notification(
    goal_statuses: List[dict], date_str: str
) -> Optional[Notification]:
    incomplete = [
        status
        for status in goal_statuses
        if status["applicable"] and status["status"] != "met"
    ]
    if not incomplete:
        return None

    sorted_statuses = sorted(incomplete, key=lambda status: status["goal_name"].lower())
    names = []
    for status in sorted_statuses:
        name = status["goal_name"]
        if status.get("scoring_mode") == ScoringMode.rating:
            avg = float(status.get("progress") or 0.0)
            target = status.get("target", 0)
            samples = status.get("samples", 0)
            window_days = status.get("window_days", 0)
            comparison = "<" if avg < target else ">="
            names.append(
                f"{name} (avg {avg:.1f} {comparison} {target}, {samples}/{window_days} rated)"
            )
        else:
            names.append(name)
    title = "Goal check-in"
    body = "Incomplete goals today: " + ", ".join(names) + "."
    return Notification(
        type="reminder",
        title=title,
        body=body,
        dedupe_key=f"reminder:{date_str}",
    )


def _build_trend_notifications(
    session: Session, goal_statuses: List[dict], date_str: str
) -> List[Notification]:
    if not goal_statuses:
        return []

    today = datetime.strptime(date_str, "%Y-%m-%d").date()
    statuses_by_goal = {status["goal_id"]: status for status in goal_statuses}
    daily_goal_ids = [
        status["goal_id"]
        for status in goal_statuses
        if status["target_window"] == "day"
    ]

    notifications: List[Notification] = []

    if daily_goal_ids:
        start_str = (today - timedelta(days=13)).isoformat()
        daily_series = trend_service.build_trend_series(
            session, daily_goal_ids, start_str, date_str, "day"
        )
        series_by_goal = {entry["goal_id"]: entry for entry in daily_series}
        for goal_id in daily_goal_ids:
            series = series_by_goal.get(goal_id, {})
            points = series.get("points", [])
            if len(points) < 14:
                continue
            prior_points = points[:7]
            recent_points = points[7:14]
            applicable_points = [
                point
                for point in points
                if point["applicable"] and point["status"] != "na"
            ]
            if len(applicable_points) < 10:
                continue
            prior_avg = _average_ratio(prior_points)
            recent_avg = _average_ratio(recent_points)
            if prior_avg - recent_avg >= 0.2:
                status = statuses_by_goal.get(goal_id)
                if status is None:
                    continue
                title = f"Trend dip: {status['goal_name']}"
                body = (
                    "Last 7 days average dropped "
                    f"from {_format_ratio(prior_avg)} to {_format_ratio(recent_avg)}."
                )
                notifications.append(
                    Notification(
                        type="trend",
                        title=title,
                        body=body,
                        dedupe_key=f"trend:avg_drop:{goal_id}:{date_str}",
                    )
                )

    for status in goal_statuses:
        target_window = status["target_window"]
        if target_window not in {"week", "month"}:
            continue
        if not status["applicable"] or status["status"] == "na":
            continue
        target = status.get("target", 0) or 0
        actual_ratio = (status.get("progress", 0.0) or 0.0) / target if target else 0.0
        if target_window == "week":
            week_start, week_end = scoring.get_week_bounds(date_str)
            elapsed = (today - week_start).days + 1
            total_days = (week_end - week_start).days + 1
            expected_ratio = elapsed / total_days if total_days else 0.0
            if actual_ratio < expected_ratio - 0.2:
                title = f"Weekly pace: {status['goal_name']}"
                body = (
                    f"You're at {_format_ratio(actual_ratio)} vs "
                    f"expected {_format_ratio(expected_ratio)} for this week."
                )
                notifications.append(
                    Notification(
                        type="trend",
                        title=title,
                        body=body,
                        dedupe_key=f"trend:weekly_pace:{status['goal_id']}:{date_str}",
                    )
                )
        elif target_window == "month":
            month_start, month_end = scoring.get_month_bounds(date_str)
            elapsed = (today - month_start).days + 1
            total_days = (month_end - month_start).days + 1
            expected_ratio = elapsed / total_days if total_days else 0.0
            if actual_ratio < expected_ratio - 0.2:
                title = f"Monthly pace: {status['goal_name']}"
                body = (
                    f"You're at {_format_ratio(actual_ratio)} vs "
                    f"expected {_format_ratio(expected_ratio)} this month."
                )
                notifications.append(
                    Notification(
                        type="trend",
                        title=title,
                        body=body,
                        dedupe_key=f"trend:monthly_pace:{status['goal_id']}:{date_str}",
                    )
                )

    return notifications


def _average_ratio(points: List[dict]) -> float:
    applicable = [
        point["ratio"]
        for point in points
        if point["applicable"] and point["status"] != "na"
    ]
    if not applicable:
        return 0.0
    return sum(applicable) / len(applicable)


def _format_ratio(value: float) -> str:
    return f"{value * 100:.0f}%"


def run_reminders(
    session: Session, *, now: Optional[datetime] = None, force: bool = False
) -> dict:
    if now is None:
        now = datetime.utcnow()

    if not force and not settings.reminders_enabled:
        return {
            "ran": False,
            "created": False,
            "notification_id": None,
            "reason": "disabled",
        }

    last_run_at = _get_last_run_at(session)
    cadence_minutes = settings.reminders_cadence_minutes
    due = (
        last_run_at is None
        or now - last_run_at >= timedelta(minutes=cadence_minutes)
    )
    if not force and not due:
        return {
            "ran": False,
            "created": False,
            "notification_id": None,
            "reason": "not_due",
        }

    date_str = now.date().isoformat()
    statuses = scoring.compute_goal_statuses_for_date(session, date_str)
    notification = _build_notification(statuses, date_str)
    trend_notifications = _build_trend_notifications(session, statuses, date_str)

    created = False
    notification_id = None
    reason: Optional[str] = None

    if notification is None:
        reason = "no_incomplete_goals"
    else:
        existing = session.exec(
            select(Notification).where(
                Notification.dedupe_key == notification.dedupe_key
            )
        ).first()
        if existing is None:
            session.add(notification)
            created = True
        else:
            notification_id = existing.id
            reason = "deduped"

    for trend_notification in trend_notifications:
        existing_trend = session.exec(
            select(Notification).where(
                Notification.dedupe_key == trend_notification.dedupe_key
            )
        ).first()
        if existing_trend is None:
            session.add(trend_notification)

    _upsert_last_run_at(session, now)
    session.commit()

    if notification is not None and created:
        session.refresh(notification)
        notification_id = notification.id

    return {
        "ran": True,
        "created": created,
        "notification_id": notification_id,
        "reason": reason,
    }


async def _sleep_with_stop(stop_event: asyncio.Event, seconds: int) -> None:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        return


async def reminder_loop(stop_event: asyncio.Event) -> None:
    cadence_seconds = max(settings.reminders_cadence_minutes, 1) * 60
    while not stop_event.is_set():
        try:
            with Session(db.engine) as session:
                run_reminders(session)
        except Exception:
            logger.exception("Reminder run failed")
        await _sleep_with_stop(stop_event, cadence_seconds)
