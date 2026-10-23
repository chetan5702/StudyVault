from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.datetime_type import utcnow
from app.models import Exam, Notification, User
from app.reminders import acquire_reminder_lock, generate_reminders, preferences_for
from app.schemas import (
    NotificationList,
    NotificationOut,
    ReminderPreferencesOut,
    ReminderPreferencesUpdate,
)

router = APIRouter(tags=["notifications"])


@router.get("/notification-preferences", response_model=ReminderPreferencesOut)
def get_preferences(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReminderPreferencesOut:
    acquire_reminder_lock(db)
    preferences = preferences_for(db, current_user.id)
    result = ReminderPreferencesOut.model_validate(preferences)
    result.email_available = get_settings().email_available
    db.commit()
    return result


@router.put("/notification-preferences", response_model=ReminderPreferencesOut)
def update_preferences(
    payload: ReminderPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReminderPreferencesOut:
    if payload.email_enabled and not get_settings().email_available:
        raise HTTPException(
            status_code=422, detail="Email notifications require a configured provider"
        )
    acquire_reminder_lock(db)
    preferences = preferences_for(db, current_user.id)
    changes = payload.model_dump()
    changed = any(getattr(preferences, key) != value for key, value in changes.items())
    for key, value in changes.items():
        setattr(preferences, key, value)
    if changed:
        now = utcnow()
        for exam in (
            db.query(Exam)
            .filter(
                Exam.user_id == current_user.id, Exam.deleted_at.is_(None), Exam.scheduled_for > now
            )
            .all()
        ):
            generate_reminders(db, exam, now=now)
    db.commit()
    result = ReminderPreferencesOut.model_validate(preferences)
    result.email_available = get_settings().email_available
    return result


@router.get("/notifications", response_model=NotificationList)
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    unread = query.filter(Notification.read_at.is_(None)).count()
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    return {
        "items": query.order_by(Notification.delivered_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
        .all(),
        "unread_count": unread,
    }


@router.post("/notifications/read-all")
def read_all(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, str]:
    db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.read_at.is_(None)
    ).update({"read_at": utcnow()}, synchronize_session=False)
    db.commit()
    return {"status": "read"}


@router.patch("/notifications/{notification_id}/read", response_model=NotificationOut)
def read_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Notification:
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.read_at = notification.read_at or utcnow()
    db.commit()
    db.refresh(notification)
    return notification
