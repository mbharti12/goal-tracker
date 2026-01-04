from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlmodel import Session, select

from ..db import get_session
from ..models import (
    Condition,
    DayCondition,
    DayEntry,
    Goal,
    GoalRating,
    GoalTag,
    GoalVersion,
    GoalVersionTag,
    ScoringMode,
    Tag,
    TagEvent,
    TargetWindow,
)
from ..schemas import (
    CalendarDayRead,
    CalendarMonthRead,
    CalendarSummaryRead,
    CalendarWeekRead,
    DayConditionRead,
    DayConditionsUpdate,
    DayEntryRead,
    DayGoalRatingRead,
    DayGoalRatingsUpdate,
    DayNoteUpdate,
    DayRead,
    TagImpactGoalRead,
    TagImpactRead,
    TagCreate,
    TagEventCreate,
    TagEventDeleteResponse,
    TagEventRead,
)
from ..services import scoring, tag_service

router = APIRouter(tags=["days"])


def _parse_date(date_str: str) -> str:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Expected YYYY-MM-DD.",
        ) from exc
    return date_str


def _load_day_conditions(session: Session, date_str: str) -> List[DayConditionRead]:
    rows = session.exec(
        select(DayCondition, Condition)
        .join(Condition, DayCondition.condition_id == Condition.id)
        .where(DayCondition.date == date_str)
        .order_by(DayCondition.condition_id)
    ).all()
    return [
        DayConditionRead(
            condition_id=day_condition.condition_id,
            name=condition.name,
            value=day_condition.value,
        )
        for day_condition, condition in rows
    ]


def _load_tag_events(session: Session, date_str: str) -> List[TagEventRead]:
    rows = session.exec(
        select(TagEvent, Tag)
        .join(Tag, TagEvent.tag_id == Tag.id)
        .where(TagEvent.date == date_str)
        .order_by(TagEvent.ts, TagEvent.id)
    ).all()
    return [
        TagEventRead(
            id=event.id,
            date=event.date,
            tag_id=event.tag_id,
            tag_name=tag.name,
            ts=event.ts,
            count=event.count,
            note=event.note,
        )
        for event, tag in rows
    ]


def _load_goal_ratings(session: Session, date_str: str) -> List[DayGoalRatingRead]:
    rows = session.exec(
        select(GoalRating)
        .where(GoalRating.date == date_str)
        .order_by(GoalRating.goal_id)
    ).all()
    return [
        DayGoalRatingRead(goal_id=row.goal_id, rating=row.rating, note=row.note)
        for row in rows
    ]


@router.get("/days/{date}", response_model=DayRead)
def get_day(
    date: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    session: Session = Depends(get_session),
) -> DayRead:
    date_str = _parse_date(date)
    day_entry = session.get(DayEntry, date_str)
    conditions = _load_day_conditions(session, date_str)
    tag_events = _load_tag_events(session, date_str)
    goal_ratings = _load_goal_ratings(session, date_str)
    goals = scoring.compute_goal_statuses_for_date(session, date_str)
    return DayRead(
        day_entry=day_entry,
        conditions=conditions,
        tag_events=tag_events,
        goal_ratings=goal_ratings,
        goals=goals,
    )


@router.get("/days/{date}/tag-impacts", response_model=List[TagImpactRead])
def get_tag_impacts(
    date: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    session: Session = Depends(get_session),
) -> List[TagImpactRead]:
    date_str = _parse_date(date)
    goals = session.exec(select(Goal).where(Goal.active == True)).all()  # noqa: E712
    if not goals:
        return []

    goal_ids = [goal.id for goal in goals if goal.id is not None]
    versions_by_goal: dict[int, list[GoalVersion]] = defaultdict(list)
    if goal_ids:
        version_rows = session.exec(
            select(GoalVersion).where(GoalVersion.goal_id.in_(goal_ids))
        ).all()
        for version in version_rows:
            versions_by_goal[version.goal_id].append(version)

    version_ids = [
        version.id
        for versions in versions_by_goal.values()
        for version in versions
        if version.id is not None
    ]
    version_tags_by_version: dict[int, dict[int, int]] = defaultdict(dict)
    if version_ids:
        for row in session.exec(
            select(GoalVersionTag).where(GoalVersionTag.goal_version_id.in_(version_ids))
        ).all():
            version_tags_by_version[row.goal_version_id][row.tag_id] = row.weight

    goal_tags_by_goal: dict[int, dict[int, int]] = defaultdict(dict)
    if goal_ids:
        for row in session.exec(
            select(GoalTag).where(GoalTag.goal_id.in_(goal_ids))
        ).all():
            goal_tags_by_goal[row.goal_id][row.tag_id] = row.weight

    impacts_by_tag: dict[int, list[TagImpactGoalRead]] = defaultdict(list)
    for goal in goals:
        versions = versions_by_goal.get(goal.id, [])
        effective = scoring._select_effective_version(versions, date_str)
        if effective is None and versions:
            earliest = min(versions, key=lambda item: item.start_date)
            latest = max(versions, key=lambda item: item.start_date)
            effective = earliest if date_str < earliest.start_date else latest

        if effective is not None:
            scoring_mode = effective.scoring_mode
            target_window = effective.target_window
            tag_weights = version_tags_by_version.get(effective.id or 0, {})
        else:
            scoring_mode = goal.scoring_mode
            target_window = goal.target_window
            tag_weights = goal_tags_by_goal.get(goal.id, {})

        if scoring_mode == ScoringMode.rating:
            continue

        for tag_id, weight in tag_weights.items():
            impacts_by_tag[tag_id].append(
                TagImpactGoalRead(
                    goal_id=goal.id,
                    goal_name=goal.name,
                    target_window=target_window,
                    scoring_mode=scoring_mode,
                    weight=weight,
                )
            )

    if not impacts_by_tag:
        return []

    tag_ids = list(impacts_by_tag.keys())
    tags = session.exec(select(Tag).where(Tag.id.in_(tag_ids))).all()
    tag_names = {tag.id: tag.name for tag in tags}

    response = [
        TagImpactRead(
            tag_id=tag_id,
            tag_name=tag_names.get(tag_id, "Unknown tag"),
            goals=goals,
        )
        for tag_id, goals in impacts_by_tag.items()
    ]
    response.sort(key=lambda item: item.tag_name.lower())
    return response


@router.get("/calendar", response_model=List[CalendarDayRead])
def get_calendar(
    start: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    session: Session = Depends(get_session),
) -> List[CalendarDayRead]:
    start_str = _parse_date(start)
    end_str = _parse_date(end)

    start_day = datetime.strptime(start_str, "%Y-%m-%d").date()
    end_day = datetime.strptime(end_str, "%Y-%m-%d").date()
    if start_day > end_day:
        raise HTTPException(status_code=400, detail="start must be <= end")

    dates: List[str] = []
    current = start_day
    while current <= end_day:
        dates.append(current.isoformat())
        current += timedelta(days=1)

    condition_rows = session.exec(
        select(DayCondition, Condition)
        .join(Condition, DayCondition.condition_id == Condition.id)
        .where(
            DayCondition.date >= start_str,
            DayCondition.date <= end_str,
            DayCondition.value == True,
        )
        .order_by(DayCondition.date, DayCondition.condition_id)
    ).all()
    conditions_by_date = defaultdict(list)
    for day_condition, condition in condition_rows:
        conditions_by_date[day_condition.date].append(
            {
                "condition_id": day_condition.condition_id,
                "name": condition.name,
                "value": True,
            }
        )

    tag_rows = session.exec(
        select(TagEvent, Tag)
        .join(Tag, TagEvent.tag_id == Tag.id)
        .where(TagEvent.date >= start_str, TagEvent.date <= end_str)
    ).all()
    tag_counts = defaultdict(int)
    tag_names = {}
    for event, tag in tag_rows:
        tag_counts[(event.date, event.tag_id)] += event.count
        tag_names[event.tag_id] = tag.name

    tags_by_date = defaultdict(list)
    for (date_str, tag_id), count in sorted(tag_counts.items()):
        tags_by_date[date_str].append(
            {"tag_id": tag_id, "name": tag_names[tag_id], "count": count}
        )

    calendar: List[CalendarDayRead] = []
    for date_str in dates:
        summary = scoring.compute_day_summary(session, date_str)
        calendar.append(
            CalendarDayRead(
                date=date_str,
                applicable_goals=summary["applicable_goals"],
                met_goals=summary["met_goals"],
                completion_ratio=summary["completion_ratio"],
                conditions=conditions_by_date.get(date_str, []),
                tags=tags_by_date.get(date_str, []),
            )
        )

    return calendar


@router.get("/calendar/summary", response_model=CalendarSummaryRead)
def get_calendar_summary(
    start: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    session: Session = Depends(get_session),
) -> CalendarSummaryRead:
    start_str = _parse_date(start)
    end_str = _parse_date(end)

    start_day = datetime.strptime(start_str, "%Y-%m-%d").date()
    end_day = datetime.strptime(end_str, "%Y-%m-%d").date()
    if start_day > end_day:
        raise HTTPException(status_code=400, detail="start must be <= end")

    dates: List[str] = []
    current = start_day
    while current <= end_day:
        dates.append(current.isoformat())
        current += timedelta(days=1)

    condition_rows = session.exec(
        select(DayCondition, Condition)
        .join(Condition, DayCondition.condition_id == Condition.id)
        .where(
            DayCondition.date >= start_str,
            DayCondition.date <= end_str,
            DayCondition.value == True,
        )
        .order_by(DayCondition.date, DayCondition.condition_id)
    ).all()
    conditions_by_date = defaultdict(list)
    for day_condition, condition in condition_rows:
        conditions_by_date[day_condition.date].append(
            {
                "condition_id": day_condition.condition_id,
                "name": condition.name,
                "value": True,
            }
        )

    tag_rows = session.exec(
        select(TagEvent, Tag)
        .join(Tag, TagEvent.tag_id == Tag.id)
        .where(TagEvent.date >= start_str, TagEvent.date <= end_str)
    ).all()
    tag_counts = defaultdict(int)
    tag_names = {}
    for event, tag in tag_rows:
        tag_counts[(event.date, event.tag_id)] += event.count
        tag_names[event.tag_id] = tag.name

    tags_by_date = defaultdict(list)
    for (date_str, tag_id), count in sorted(tag_counts.items()):
        tags_by_date[date_str].append(
            {"tag_id": tag_id, "name": tag_names[tag_id], "count": count}
        )

    week_bounds = {}
    month_bounds = {}
    days: List[CalendarDayRead] = []
    for date_str in dates:
        summary = scoring.compute_day_summary_for_window(
            session, date_str, TargetWindow.day
        )
        days.append(
            CalendarDayRead(
                date=date_str,
                applicable_goals=summary["applicable_goals"],
                met_goals=summary["met_goals"],
                completion_ratio=summary["completion_ratio"],
                conditions=conditions_by_date.get(date_str, []),
                tags=tags_by_date.get(date_str, []),
            )
        )

        week_start, week_end = scoring.get_week_bounds(date_str)
        week_bounds[week_start] = week_end
        month_start, month_end = scoring.get_month_bounds(date_str)
        month_bounds[month_start] = month_end

    weeks: List[CalendarWeekRead] = []
    for week_start in sorted(week_bounds.keys()):
        week_end = week_bounds[week_start]
        summary = scoring.compute_window_summary(
            session, week_end.isoformat(), TargetWindow.week
        )
        weeks.append(
            CalendarWeekRead(
                start=week_start.isoformat(),
                end=week_end.isoformat(),
                applicable_goals=summary["applicable_goals"],
                met_goals=summary["met_goals"],
                completion_ratio=summary["completion_ratio"],
            )
        )

    months: List[CalendarMonthRead] = []
    for month_start in sorted(month_bounds.keys()):
        month_end = month_bounds[month_start]
        summary = scoring.compute_window_summary(
            session, month_end.isoformat(), TargetWindow.month
        )
        months.append(
            CalendarMonthRead(
                start=month_start.isoformat(),
                end=month_end.isoformat(),
                applicable_goals=summary["applicable_goals"],
                met_goals=summary["met_goals"],
                completion_ratio=summary["completion_ratio"],
            )
        )

    return CalendarSummaryRead(days=days, weeks=weeks, months=months)


@router.put("/days/{date}/note", response_model=DayEntryRead)
def upsert_day_note(
    note_in: DayNoteUpdate,
    date: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    session: Session = Depends(get_session),
) -> DayEntryRead:
    date_str = _parse_date(date)
    day_entry = session.get(DayEntry, date_str)
    if day_entry is None:
        day_entry = DayEntry(date=date_str, note=note_in.note)
        session.add(day_entry)
        session.commit()
        session.refresh(day_entry)
        return day_entry

    if day_entry.note != note_in.note:
        day_entry.note = note_in.note
        day_entry.updated_at = datetime.utcnow()
        session.add(day_entry)
        session.commit()
        session.refresh(day_entry)
    return day_entry


@router.put("/days/{date}/conditions", response_model=List[DayConditionRead])
def upsert_day_conditions(
    payload: DayConditionsUpdate,
    date: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    session: Session = Depends(get_session),
) -> List[DayConditionRead]:
    date_str = _parse_date(date)
    condition_ids = [item.condition_id for item in payload.conditions]
    if not condition_ids:
        return _load_day_conditions(session, date_str)

    if condition_ids:
        existing_ids = set(
            session.exec(
                select(Condition.id).where(Condition.id.in_(condition_ids))
            ).all()
        )
        missing_ids = sorted(set(condition_ids) - existing_ids)
        if missing_ids:
            missing = ", ".join(str(item) for item in missing_ids)
            raise HTTPException(
                status_code=400,
                detail=f"Condition(s) not found: {missing}",
            )

    day_entry = session.get(DayEntry, date_str)
    if day_entry is None:
        session.add(DayEntry(date=date_str))

    for item in payload.conditions:
        existing = session.get(DayCondition, (date_str, item.condition_id))
        if existing is None:
            session.add(
                DayCondition(
                    date=date_str,
                    condition_id=item.condition_id,
                    value=item.value,
                )
            )
        else:
            existing.value = item.value
            session.add(existing)

    session.commit()

    return _load_day_conditions(session, date_str)


@router.put("/days/{date}/ratings", response_model=List[DayGoalRatingRead])
def upsert_day_ratings(
    payload: DayGoalRatingsUpdate,
    date: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    session: Session = Depends(get_session),
) -> List[DayGoalRatingRead]:
    date_str = _parse_date(date)
    ratings = payload.ratings
    if not ratings:
        return _load_goal_ratings(session, date_str)

    goal_ids = [item.goal_id for item in ratings]
    existing_ids = set(
        session.exec(select(Goal.id).where(Goal.id.in_(goal_ids))).all()
    )
    missing_ids = sorted(set(goal_ids) - existing_ids)
    if missing_ids:
        missing = ", ".join(str(item) for item in missing_ids)
        raise HTTPException(
            status_code=400,
            detail=f"Goal(s) not found: {missing}",
        )

    for item in ratings:
        existing = session.get(GoalRating, (date_str, item.goal_id))
        if existing is None:
            session.add(
                GoalRating(
                    date=date_str,
                    goal_id=item.goal_id,
                    rating=item.rating,
                    note=item.note,
                )
            )
        else:
            existing.rating = item.rating
            existing.note = item.note
            session.add(existing)

    session.commit()
    return _load_goal_ratings(session, date_str)


@router.post(
    "/days/{date}/tag-events",
    response_model=TagEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_tag_event(
    payload: TagEventCreate,
    date: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    session: Session = Depends(get_session),
) -> TagEventRead:
    date_str = _parse_date(date)
    tag: Optional[Tag] = None

    if payload.tag_id is not None:
        tag = session.get(Tag, payload.tag_id)
        if tag is None:
            raise HTTPException(status_code=400, detail="Tag not found")
    else:
        tag_name = (payload.tag_name or "").strip()
        if not tag_name:
            raise HTTPException(status_code=400, detail="tag_name is required")
        tag = tag_service.create_tag(session, TagCreate(name=tag_name))

    event = TagEvent(
        date=date_str,
        tag_id=tag.id,
        ts=payload.ts,
        count=payload.count,
        note=payload.note,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return TagEventRead(
        id=event.id,
        date=event.date,
        tag_id=event.tag_id,
        tag_name=tag.name,
        ts=event.ts,
        count=event.count,
        note=event.note,
    )


@router.delete("/tag-events/{event_id}", response_model=TagEventDeleteResponse)
def delete_tag_event(
    event_id: int,
    session: Session = Depends(get_session),
) -> TagEventDeleteResponse:
    event = session.get(TagEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Tag event not found")
    session.delete(event)
    session.commit()
    return TagEventDeleteResponse(deleted=True)
