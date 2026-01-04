from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional, Sequence, Tuple

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from ..models import (
    Condition,
    Goal,
    GoalCondition,
    GoalTag,
    GoalVersion,
    GoalVersionCondition,
    GoalVersionTag,
    ScoringMode,
    Tag,
)
from ..schemas import GoalCreate, GoalUpdate


def _goal_with_relations_stmt(goal_id: Optional[int] = None):
    stmt = select(Goal).options(
        selectinload(Goal.goal_tags).selectinload(GoalTag.tag),
        selectinload(Goal.goal_conditions).selectinload(GoalCondition.condition),
    )
    if goal_id is not None:
        stmt = stmt.where(Goal.id == goal_id)
    return stmt


def list_goals(session: Session) -> List[Goal]:
    return session.exec(_goal_with_relations_stmt()).all()


def get_goal(session: Session, goal_id: int) -> Optional[Goal]:
    return session.exec(_goal_with_relations_stmt(goal_id)).first()


def _validate_tags(session: Session, tags) -> None:
    for tag_item in tags:
        if session.get(Tag, tag_item.tag_id) is None:
            raise ValueError(f"Tag {tag_item.tag_id} does not exist")


def _validate_conditions(session: Session, conditions) -> None:
    for condition_item in conditions:
        if session.get(Condition, condition_item.condition_id) is None:
            raise ValueError(f"Condition {condition_item.condition_id} does not exist")


def _validate_target_count(scoring_mode: ScoringMode, target_count: int) -> None:
    if scoring_mode == ScoringMode.rating and not (1 <= target_count <= 100):
        raise ValueError("rating goals require target_count between 1 and 100")


def _normalize_tag_pairs(items: Sequence) -> List[Tuple[int, int]]:
    return sorted((item.tag_id, item.weight) for item in items)


def _normalize_condition_pairs(items: Sequence) -> List[Tuple[int, bool]]:
    return sorted((item.condition_id, item.required_value) for item in items)


def _select_effective_version(
    versions: Sequence[GoalVersion], date_str: str
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


def _today_str() -> str:
    return date.today().isoformat()


def create_goal(session: Session, goal_in: GoalCreate) -> Goal:
    _validate_tags(session, goal_in.tags)
    _validate_conditions(session, goal_in.conditions)
    _validate_target_count(goal_in.scoring_mode, goal_in.target_count)

    today_str = _today_str()
    goal = Goal(
        name=goal_in.name,
        description=goal_in.description,
        active=goal_in.active,
        target_window=goal_in.target_window,
        target_count=goal_in.target_count,
        scoring_mode=goal_in.scoring_mode,
    )
    session.add(goal)
    session.flush()

    for tag_item in goal_in.tags:
        session.add(
            GoalTag(
                goal_id=goal.id,
                tag_id=tag_item.tag_id,
                weight=tag_item.weight,
            )
        )

    for condition_item in goal_in.conditions:
        session.add(
            GoalCondition(
                goal_id=goal.id,
                condition_id=condition_item.condition_id,
                required_value=condition_item.required_value,
            )
        )

    version = GoalVersion(
        goal_id=goal.id,
        start_date=today_str,
        end_date=None,
        target_window=goal_in.target_window,
        target_count=goal_in.target_count,
        scoring_mode=goal_in.scoring_mode,
    )
    session.add(version)
    session.flush()

    for tag_item in goal_in.tags:
        session.add(
            GoalVersionTag(
                goal_version_id=version.id,
                tag_id=tag_item.tag_id,
                weight=tag_item.weight,
            )
        )

    for condition_item in goal_in.conditions:
        session.add(
            GoalVersionCondition(
                goal_version_id=version.id,
                condition_id=condition_item.condition_id,
                required_value=condition_item.required_value,
            )
        )

    session.commit()
    return get_goal(session, goal.id)


def update_goal(session: Session, goal_id: int, goal_in: GoalUpdate) -> Optional[Goal]:
    goal = session.get(Goal, goal_id)
    if goal is None:
        return None

    existing_tags = session.exec(
        select(GoalTag).where(GoalTag.goal_id == goal_id)
    ).all()
    existing_conditions = session.exec(
        select(GoalCondition).where(GoalCondition.goal_id == goal_id)
    ).all()

    scoring_mode = (
        goal_in.scoring_mode if goal_in.scoring_mode is not None else goal.scoring_mode
    )
    target_count = (
        goal_in.target_count
        if goal_in.target_count is not None
        else goal.target_count
    )
    _validate_target_count(scoring_mode, target_count)
    target_window = (
        goal_in.target_window
        if goal_in.target_window is not None
        else goal.target_window
    )

    tags_changed = False
    if goal_in.tags is not None:
        _validate_tags(session, goal_in.tags)
        tags_changed = _normalize_tag_pairs(existing_tags) != _normalize_tag_pairs(
            goal_in.tags
        )
    new_tag_items = goal_in.tags if goal_in.tags is not None else existing_tags

    conditions_changed = False
    if goal_in.conditions is not None:
        _validate_conditions(session, goal_in.conditions)
        conditions_changed = _normalize_condition_pairs(
            existing_conditions
        ) != _normalize_condition_pairs(goal_in.conditions)
    new_condition_items = (
        goal_in.conditions if goal_in.conditions is not None else existing_conditions
    )

    scoring_fields_changed = (
        (goal_in.target_window is not None and goal_in.target_window != goal.target_window)
        or (
            goal_in.target_count is not None
            and goal_in.target_count != goal.target_count
        )
        or (
            goal_in.scoring_mode is not None
            and goal_in.scoring_mode != goal.scoring_mode
        )
    )
    scoring_config_changed = (
        scoring_fields_changed or tags_changed or conditions_changed
    )

    if goal_in.name is not None:
        goal.name = goal_in.name
    if goal_in.description is not None:
        goal.description = goal_in.description
    if goal_in.active is not None:
        goal.active = goal_in.active
    goal.target_window = target_window
    if goal_in.target_count is not None:
        goal.target_count = goal_in.target_count
    if goal_in.scoring_mode is not None:
        goal.scoring_mode = goal_in.scoring_mode

    if goal_in.tags is not None:
        for tag_item in existing_tags:
            session.delete(tag_item)
        for tag_item in goal_in.tags:
            session.add(
                GoalTag(
                    goal_id=goal_id,
                    tag_id=tag_item.tag_id,
                    weight=tag_item.weight,
                )
            )

    if goal_in.conditions is not None:
        for condition_item in existing_conditions:
            session.delete(condition_item)
        for condition_item in goal_in.conditions:
            session.add(
                GoalCondition(
                    goal_id=goal_id,
                    condition_id=condition_item.condition_id,
                    required_value=condition_item.required_value,
                )
            )

    if scoring_config_changed:
        effective_date = goal_in.effective_date or _today_str()
        effective_date_value = datetime.strptime(effective_date, "%Y-%m-%d").date()

        versions = session.exec(
            select(GoalVersion).where(GoalVersion.goal_id == goal_id)
        ).all()
        effective_version = _select_effective_version(versions, effective_date)

        version_id: Optional[int] = None
        if effective_version is None:
            if versions:
                next_start = min(
                    (version.start_date for version in versions if version.start_date > effective_date),
                    default=None,
                )
                end_date = None
                if next_start is not None:
                    end_date = (
                        datetime.strptime(next_start, "%Y-%m-%d").date()
                        - timedelta(days=1)
                    ).isoformat()
                new_version = GoalVersion(
                    goal_id=goal_id,
                    start_date=effective_date,
                    end_date=end_date,
                    target_window=target_window,
                    target_count=target_count,
                    scoring_mode=scoring_mode,
                )
                session.add(new_version)
                session.flush()
                version_id = new_version.id
            else:
                new_version = GoalVersion(
                    goal_id=goal_id,
                    start_date=effective_date,
                    end_date=None,
                    target_window=target_window,
                    target_count=target_count,
                    scoring_mode=scoring_mode,
                )
                session.add(new_version)
                session.flush()
                version_id = new_version.id
        elif effective_version.start_date == effective_date:
            effective_version.target_window = target_window
            effective_version.target_count = target_count
            effective_version.scoring_mode = scoring_mode
            session.add(effective_version)
            version_id = effective_version.id
        else:
            effective_version.end_date = (
                effective_date_value - timedelta(days=1)
            ).isoformat()
            session.add(effective_version)
            new_version = GoalVersion(
                goal_id=goal_id,
                start_date=effective_date,
                end_date=None,
                target_window=target_window,
                target_count=target_count,
                scoring_mode=scoring_mode,
            )
            session.add(new_version)
            session.flush()
            version_id = new_version.id

        if version_id is not None:
            existing_version_tags = session.exec(
                select(GoalVersionTag).where(
                    GoalVersionTag.goal_version_id == version_id
                )
            ).all()
            for tag_item in existing_version_tags:
                session.delete(tag_item)
            for tag_item in new_tag_items:
                session.add(
                    GoalVersionTag(
                        goal_version_id=version_id,
                        tag_id=tag_item.tag_id,
                        weight=tag_item.weight,
                    )
                )

            existing_version_conditions = session.exec(
                select(GoalVersionCondition).where(
                    GoalVersionCondition.goal_version_id == version_id
                )
            ).all()
            for condition_item in existing_version_conditions:
                session.delete(condition_item)
            for condition_item in new_condition_items:
                session.add(
                    GoalVersionCondition(
                        goal_version_id=version_id,
                        condition_id=condition_item.condition_id,
                        required_value=condition_item.required_value,
                    )
                )

    session.add(goal)
    session.commit()
    return get_goal(session, goal_id)


def soft_delete_goal(session: Session, goal_id: int) -> Optional[Goal]:
    goal = session.get(Goal, goal_id)
    if goal is None:
        return None
    goal.active = False
    session.add(goal)
    session.commit()
    return get_goal(session, goal_id)
