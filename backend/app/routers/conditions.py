from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from ..db import get_session
from ..schemas import ConditionCreate, ConditionRead
from ..services import condition_service

router = APIRouter(prefix="/conditions", tags=["conditions"])


@router.get("", response_model=List[ConditionRead])
def list_conditions(session: Session = Depends(get_session)) -> List[ConditionRead]:
    return condition_service.list_conditions(session)


@router.post("", response_model=ConditionRead, status_code=status.HTTP_201_CREATED)
def create_condition(
    condition_in: ConditionCreate, session: Session = Depends(get_session)
) -> ConditionRead:
    return condition_service.create_condition(session, condition_in)
