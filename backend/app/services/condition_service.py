from __future__ import annotations

from typing import List

from sqlmodel import Session, select

from ..models import Condition
from ..schemas import ConditionCreate


def list_conditions(session: Session) -> List[Condition]:
    return session.exec(select(Condition)).all()


def create_condition(session: Session, condition_in: ConditionCreate) -> Condition:
    existing = session.exec(
        select(Condition).where(Condition.name == condition_in.name)
    ).first()
    if existing:
        return existing

    condition = Condition(name=condition_in.name)
    session.add(condition)
    session.commit()
    session.refresh(condition)
    return condition
