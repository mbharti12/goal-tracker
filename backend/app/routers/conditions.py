from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..db import get_session
from ..schemas import ConditionCreate, ConditionRead
from ..services import condition_service

router = APIRouter(prefix="/conditions", tags=["conditions"])


@router.get("", response_model=List[ConditionRead])
def list_conditions(
    include_inactive: bool = False, session: Session = Depends(get_session)
) -> List[ConditionRead]:
    return condition_service.list_conditions(
        session, include_inactive=include_inactive
    )


@router.post("", response_model=ConditionRead, status_code=status.HTTP_201_CREATED)
def create_condition(
    condition_in: ConditionCreate, session: Session = Depends(get_session)
) -> ConditionRead:
    return condition_service.create_condition(session, condition_in)


@router.put("/{condition_id}/deactivate", response_model=ConditionRead)
def deactivate_condition(
    condition_id: int, session: Session = Depends(get_session)
) -> ConditionRead:
    condition = condition_service.set_condition_active(session, condition_id, False)
    if condition is None:
        raise HTTPException(status_code=404, detail="Condition not found")
    return condition


@router.put("/{condition_id}/reactivate", response_model=ConditionRead)
def reactivate_condition(
    condition_id: int, session: Session = Depends(get_session)
) -> ConditionRead:
    condition = condition_service.set_condition_active(session, condition_id, True)
    if condition is None:
        raise HTTPException(status_code=404, detail="Condition not found")
    return condition
