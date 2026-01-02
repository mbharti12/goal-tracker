from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..db import get_session
from ..schemas import GoalCreate, GoalRead, GoalUpdate
from ..services import goal_service

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=List[GoalRead])
def list_goals(session: Session = Depends(get_session)) -> List[GoalRead]:
    return goal_service.list_goals(session)


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
def create_goal(
    goal_in: GoalCreate, session: Session = Depends(get_session)
) -> GoalRead:
    try:
        goal = goal_service.create_goal(session, goal_in)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return goal


@router.put("/{goal_id}", response_model=GoalRead)
def update_goal(
    goal_id: int, goal_in: GoalUpdate, session: Session = Depends(get_session)
) -> GoalRead:
    try:
        goal = goal_service.update_goal(session, goal_id, goal_in)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.delete("/{goal_id}", response_model=GoalRead)
def delete_goal(
    goal_id: int, session: Session = Depends(get_session)
) -> GoalRead:
    goal = goal_service.soft_delete_goal(session, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal
