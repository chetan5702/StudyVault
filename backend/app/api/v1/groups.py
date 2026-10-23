from __future__ import annotations

import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import ClassGroup, ClassMember, User
from app.schemas import GroupCreate, GroupMemberOut, GroupOut

router = APIRouter(tags=["groups"])


@router.get("/groups", response_model=list[GroupOut])
def list_groups(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ClassGroup]:
    membership = (
        db.query(ClassMember.group_id).filter(ClassMember.user_id == current_user.id).subquery()
    )
    return (
        db.query(ClassGroup)
        .filter(ClassGroup.id.in_(membership))
        .order_by(ClassGroup.name.asc())
        .all()
    )


@router.post("/groups", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassGroup:
    invite_code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))
    group = ClassGroup(
        name=payload.name,
        owner_id=current_user.id,
        invite_code=invite_code,
        description=payload.description,
    )
    db.add(group)
    db.flush()
    db.add(ClassMember(group_id=group.id, user_id=current_user.id, role="owner"))
    db.commit()
    db.refresh(group)
    return group


@router.post("/groups/join")
def join_group(
    invite_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    group = db.query(ClassGroup).filter(ClassGroup.invite_code == invite_code.upper()).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    exists = (
        db.query(ClassMember)
        .filter(ClassMember.group_id == group.id, ClassMember.user_id == current_user.id)
        .first()
    )
    if exists:
        return {"status": "already_member", "group_id": group.id}
    group_id = group.id
    db.add(ClassMember(group_id=group_id, user_id=current_user.id, role="member"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Two concurrent joins are idempotent once the DB uniqueness constraint exists.
        if (
            db.query(ClassMember)
            .filter(ClassMember.group_id == group_id, ClassMember.user_id == current_user.id)
            .first()
        ):
            return {"status": "already_member", "group_id": group_id}
        raise
    return {"status": "joined", "group_id": group_id}


@router.get("/groups/{group_id}/members", response_model=list[GroupMemberOut])
def list_group_members(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ClassMember]:
    group = db.query(ClassGroup).filter(ClassGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if (
        not db.query(ClassMember)
        .filter(ClassMember.group_id == group_id, ClassMember.user_id == current_user.id)
        .first()
    ):
        raise HTTPException(status_code=403, detail="Forbidden")
    return db.query(ClassMember).filter(ClassMember.group_id == group_id).all()
