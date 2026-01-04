from __future__ import annotations

from typing import List, Optional

from sqlmodel import Session, select

from ..models import Condition
from ..schemas import ConditionCreate


def list_conditions(session: Session, include_inactive: bool = False) -> List[Condition]:
    stmt = select(Condition)
    if not include_inactive:
        stmt = stmt.where(Condition.active == True)  # noqa: E712
    return session.exec(stmt).all()


def create_condition(session: Session, condition_in: ConditionCreate) -> Condition:
    existing = session.exec(
        select(Condition).where(Condition.name == condition_in.name)
    ).first()
    if existing:
        if not existing.active:
            existing.active = True
            session.add(existing)
            session.commit()
            session.refresh(existing)
        return existing

    condition = Condition(name=condition_in.name)
    session.add(condition)
    session.commit()
    session.refresh(condition)
    return condition


def set_condition_active(
    session: Session, condition_id: int, active: bool
) -> Optional[Condition]:
    condition = session.get(Condition, condition_id)
    if condition is None:
        return None
    condition.active = active
    session.add(condition)
    session.commit()
    session.refresh(condition)
    return condition
