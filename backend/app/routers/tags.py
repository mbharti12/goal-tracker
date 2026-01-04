from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..db import get_session
from ..schemas import TagCreate, TagRead, TagUpdate
from ..services import tag_service

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=List[TagRead])
def list_tags(
    include_inactive: bool = False, session: Session = Depends(get_session)
) -> List[TagRead]:
    return tag_service.list_tags(session, include_inactive=include_inactive)


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(tag_in: TagCreate, session: Session = Depends(get_session)) -> TagRead:
    return tag_service.create_tag(session, tag_in)


@router.put("/{tag_id}", response_model=TagRead)
def update_tag(tag_id: int, tag_in: TagUpdate, session: Session = Depends(get_session)) -> TagRead:
    tag = tag_service.update_tag_category(session, tag_id, tag_in)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


@router.put("/{tag_id}/deactivate", response_model=TagRead)
def deactivate_tag(tag_id: int, session: Session = Depends(get_session)) -> TagRead:
    tag = tag_service.set_tag_active(session, tag_id, False)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


@router.put("/{tag_id}/reactivate", response_model=TagRead)
def reactivate_tag(tag_id: int, session: Session = Depends(get_session)) -> TagRead:
    tag = tag_service.set_tag_active(session, tag_id, True)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


@router.delete("/{tag_id}", response_model=TagRead)
def delete_tag(tag_id: int, session: Session = Depends(get_session)) -> TagRead:
    try:
        tag = tag_service.delete_tag_if_unreferenced(session, tag_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag
