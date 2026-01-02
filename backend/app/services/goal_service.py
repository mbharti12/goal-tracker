from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from ..models import Condition, Goal, GoalCondition, GoalTag, Tag
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


def create_goal(session: Session, goal_in: GoalCreate) -> Goal:
    _validate_tags(session, goal_in.tags)
    _validate_conditions(session, goal_in.conditions)

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

    session.commit()
    return get_goal(session, goal.id)


def update_goal(session: Session, goal_id: int, goal_in: GoalUpdate) -> Optional[Goal]:
    goal = session.get(Goal, goal_id)
    if goal is None:
        return None

    if goal_in.name is not None:
        goal.name = goal_in.name
    if goal_in.description is not None:
        goal.description = goal_in.description
    if goal_in.active is not None:
        goal.active = goal_in.active
    if goal_in.target_window is not None:
        goal.target_window = goal_in.target_window
    if goal_in.target_count is not None:
        goal.target_count = goal_in.target_count
    if goal_in.scoring_mode is not None:
        goal.scoring_mode = goal_in.scoring_mode

    if goal_in.tags is not None:
        _validate_tags(session, goal_in.tags)
        existing_tags = session.exec(
            select(GoalTag).where(GoalTag.goal_id == goal_id)
        ).all()
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
        _validate_conditions(session, goal_in.conditions)
        existing_conditions = session.exec(
            select(GoalCondition).where(GoalCondition.goal_id == goal_id)
        ).all()
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
