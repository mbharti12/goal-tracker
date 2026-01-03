from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..db import get_session
from ..services import reminder_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/run-reminders")
def run_reminders(session: Session = Depends(get_session)) -> dict:
    return reminder_service.run_reminders(session, force=True)
