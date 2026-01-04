from __future__ import annotations

from typing import List, Optional

from sqlmodel import Session, select

from ..models import GoalTag, Tag, TagEvent
from ..schemas import TagCreate, TagUpdate


def list_tags(session: Session, include_inactive: bool = False) -> List[Tag]:
    stmt = select(Tag)
    if not include_inactive:
        stmt = stmt.where(Tag.active == True)  # noqa: E712
    return session.exec(stmt).all()


def _normalize_category(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def create_tag(session: Session, tag_in: TagCreate) -> Tag:
    existing = session.exec(select(Tag).where(Tag.name == tag_in.name)).first()
    normalized_category = _normalize_category(tag_in.category)
    if existing:
        if not existing.active:
            # Reactivate for a safer UX when a tag already exists.
            existing.active = True
            if normalized_category is not None:
                existing.category = normalized_category
            session.add(existing)
            session.commit()
            session.refresh(existing)
        return existing

    category = normalized_category or "Other"
    tag = Tag(name=tag_in.name, category=category)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def update_tag_category(session: Session, tag_id: int, tag_in: TagUpdate) -> Optional[Tag]:
    tag = session.get(Tag, tag_id)
    if tag is None:
        return None
    normalized_category = _normalize_category(tag_in.category)
    if normalized_category is None:
        return tag
    tag.category = normalized_category
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
