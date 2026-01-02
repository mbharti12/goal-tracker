from __future__ import annotations

from typing import List, Optional

from sqlmodel import Session, select

from ..models import GoalTag, Tag, TagEvent
from ..schemas import TagCreate


def list_tags(session: Session, include_inactive: bool = False) -> List[Tag]:
    stmt = select(Tag)
    if not include_inactive:
        stmt = stmt.where(Tag.active == True)  # noqa: E712
    return session.exec(stmt).all()


def create_tag(session: Session, tag_in: TagCreate) -> Tag:
    existing = session.exec(select(Tag).where(Tag.name == tag_in.name)).first()
    if existing:
        if not existing.active:
            # Reactivate for a safer UX when a tag already exists.
            existing.active = True
            session.add(existing)
            session.commit()
            session.refresh(existing)
        return existing

    tag = Tag(name=tag_in.name)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def set_tag_active(session: Session, tag_id: int, active: bool) -> Optional[Tag]:
    tag = session.get(Tag, tag_id)
    if tag is None:
        return None
    tag.active = active
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def delete_tag_if_unreferenced(session: Session, tag_id: int) -> Optional[Tag]:
    tag = session.get(Tag, tag_id)
    if tag is None:
        return None

    goal_tag = session.exec(select(GoalTag).where(GoalTag.tag_id == tag_id)).first()
    if goal_tag is not None:
        raise ValueError("Tag is still linked to goals.")

    tag_event = session.exec(select(TagEvent).where(TagEvent.tag_id == tag_id)).first()
    if tag_event is not None:
        raise ValueError("Tag is still referenced by tag events.")

    session.delete(tag)
    session.commit()
    return tag
