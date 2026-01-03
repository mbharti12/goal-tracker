from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models import Notification
from ..schemas import NotificationMarkRead, NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=List[NotificationRead])
def list_notifications(
    unread_only: bool = Query(True),
    session: Session = Depends(get_session),
) -> List[NotificationRead]:
    statement = select(Notification)
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    statement = statement.order_by(Notification.created_at.desc(), Notification.id.desc())
    return session.exec(statement).all()


@router.post("/{notification_id}/read", response_model=NotificationMarkRead)
def mark_notification_read(
    notification_id: int,
    session: Session = Depends(get_session),
) -> NotificationMarkRead:
    notification = session.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        session.add(notification)
        session.commit()
        session.refresh(notification)
    return NotificationMarkRead(id=notification.id, read_at=notification.read_at)
