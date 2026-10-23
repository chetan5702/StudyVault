"""Persistent reminder scheduling and delivery, independent of the web process.

All schedule changes and deliveries acquire the same database row lock. A claim is
committed before contacting an email provider; a crashed worker can safely reclaim
it after two minutes, with its original payload and idempotency key. The lock is
held during the bounded provider call so a completed reschedule/delete cannot race
with a stale delivery. In-app notifications and their sent marker commit together.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.datetime_type import utcnow
from app.email_delivery import DeliveryError, EmailProvider, configured_provider
from app.models import Exam, Notification, Reminder, ReminderLock, ReminderPreference, User

DEFAULT_OFFSETS = [10080, 4320, 1440, 60]
ACTIVE_STATUSES = ("pending", "retry", "processing")
MAX_ATTEMPTS = 5
CLAIM_LEASE = timedelta(minutes=2)
# Resend retains idempotency keys for 24 hours. Stop well before expiration,
# including when the scheduler was offline or a provider response was ambiguous.
EMAIL_RETRY_HORIZON = timedelta(hours=23)


def acquire_reminder_lock(db: Session) -> None:
    dialect = db.get_bind().dialect.name
    insert = sqlite_insert if dialect == "sqlite" else pg_insert
    db.execute(
        insert(ReminderLock).values(id=1, version=0).on_conflict_do_nothing(index_elements=["id"])
    )
    db.execute(
        update(ReminderLock).where(ReminderLock.id == 1).values(version=ReminderLock.version + 1)
    )


def preferences_for(db: Session, user_id: str) -> ReminderPreference:
    preferences = db.get(ReminderPreference, user_id)
    if preferences is None:
        preferences = ReminderPreference(
            user_id=user_id,
            in_app_enabled=True,
            email_enabled=False,
            reminder_minutes=list(DEFAULT_OFFSETS),
            timezone="UTC",
        )
        db.add(preferences)
        db.flush()
    return preferences


def cancel_reminders(db: Session, exam_id: str) -> int:
    return (
        db.query(Reminder)
        .filter(Reminder.exam_id == exam_id, Reminder.delivery_status.in_(ACTIVE_STATUSES))
        .update({"delivery_status": "cancelled", "claim_token": None}, synchronize_session="fetch")
    )


def generate_reminders(db: Session, exam: Exam, *, now: datetime | None = None) -> list[Reminder]:
    """Replace unsent schedules atomically. Caller owns the lock and transaction."""
    now = (now or utcnow()).astimezone(UTC)
    db.flush()
    cancel_reminders(db, exam.id)
    exam.reminder_generation = (exam.reminder_generation or 0) + 1
    if exam.deleted_at is not None or exam.scheduled_for <= now:
        return []
    preferences = preferences_for(db, exam.user_id)
    channels = []
    if preferences.in_app_enabled:
        channels.append("in_app")
    if preferences.email_enabled:
        channels.append("email")
    offsets = preferences.reminder_minutes
    if not channels or not offsets:
        return []
    slots = [(offset, exam.scheduled_for - timedelta(minutes=offset)) for offset in offsets]
    future = [(offset, due) for offset, due in slots if due >= now]
    # Catch up one imminent reminder, rather than emitting all missed thresholds.
    if not future:
        future = [(min(offsets), now)]
    previous = (
        db.query(Reminder)
        .filter(Reminder.exam_id == exam.id, Reminder.exam_scheduled_for == exam.scheduled_for)
        .all()
    )
    prior = {(item.offset_minutes, item.channel): item for item in previous}
    future_by_offset = dict(future)
    result = []
    for channel in channels:
        for offset in offsets:
            old = prior.get((offset, channel))
            if old is not None and (old.sent or old.delivery_status == "failed"):
                continue
            due = future_by_offset.get(offset)
            if old is not None and old.first_attempt_at:
                # Preference toggles must not mint a new key after an ambiguous
                # provider response. Reuse the exact attempted payload and ID.
                old.generation = exam.reminder_generation
                old.delivery_status = "retry"
                old.claim_token = None
                result.append(old)
                continue
            if due is None:
                continue
            if old is not None:
                old.generation = exam.reminder_generation
                old.delivery_status = "pending"
                old.notify_at = due
                old.payload = None
                result.append(old)
                continue
            reminder = Reminder(
                exam_id=exam.id,
                user_id=exam.user_id,
                offset_minutes=offset,
                exam_scheduled_for=exam.scheduled_for,
                generation=exam.reminder_generation,
                notify_at=due,
                channel=channel,
                sent=False,
                delivery_status="pending",
                delivery_attempts=0,
            )
            db.add(reminder)
            result.append(reminder)
    db.flush()
    return result


def _payload(db: Session, reminder: Reminder, exam: Exam) -> dict:
    user = db.get(User, reminder.user_id)
    timezone = preferences_for(db, reminder.user_id).timezone
    local = exam.scheduled_for.astimezone(ZoneInfo(timezone))
    when = local.strftime("%d %b %Y at %H:%M %Z")
    title = f"Exam reminder: {exam.title}"
    message = f"{exam.title} is scheduled for {when} ({timezone})."
    if exam.location:
        message += f" Location: {exam.location}."
    return {
        "recipient": user.email,
        "title": title,
        "message": message,
        "scheduled_for": exam.scheduled_for.isoformat(),
    }


def _eligible(db: Session, reminder: Reminder, now: datetime) -> bool:
    exam = db.get(Exam, reminder.exam_id)
    user = db.get(User, reminder.user_id) if reminder.user_id else None
    if (
        exam is None
        or exam.deleted_at is not None
        or exam.scheduled_for <= now
        or reminder.generation != exam.reminder_generation
        or user is None
        or not user.is_active
    ):
        return False
    preferences = preferences_for(db, user.id)
    return reminder.offset_minutes in preferences.reminder_minutes and (
        (reminder.channel == "in_app" and preferences.in_app_enabled)
        or (reminder.channel == "email" and preferences.email_enabled)
    )


def _claim(session_factory, reminder_id: str, now: datetime) -> tuple[str | None, str | None]:
    with session_factory() as db:
        acquire_reminder_lock(db)
        reminder = db.get(Reminder, reminder_id)
        if (
            reminder is None
            or reminder.sent
            or reminder.delivery_status not in ACTIVE_STATUSES
            or reminder.notify_at > now
            or (reminder.next_attempt_at and reminder.next_attempt_at > now)
        ):
            db.commit()
            return None, None
        if not _eligible(db, reminder, now):
            reminder.delivery_status = "cancelled"
            reminder.claim_token = None
            db.commit()
            return None, "cancelled"
        if reminder.delivery_attempts >= MAX_ATTEMPTS or (
            reminder.channel == "email"
            and reminder.first_attempt_at
            and now - reminder.first_attempt_at >= EMAIL_RETRY_HORIZON
        ):
            reminder.delivery_status = "failed"
            reminder.last_error = "Retry limit or email idempotency safety window exceeded"
            reminder.claim_token = None
            db.commit()
            return None, "failed"
        token = str(uuid.uuid4())
        reminder.delivery_status = "processing"
        reminder.delivery_attempts += 1
        reminder.first_attempt_at = reminder.first_attempt_at or now
        reminder.next_attempt_at = now + CLAIM_LEASE
        reminder.claim_token = token
        reminder.payload = reminder.payload or _payload(
            db, reminder, db.get(Exam, reminder.exam_id)
        )
        db.commit()
        return token, None


def _deliver(session_factory, reminder_id: str, token: str, now: datetime, provider) -> str | None:
    with session_factory() as db:
        acquire_reminder_lock(db)
        reminder = db.get(Reminder, reminder_id)
        if (
            reminder is None
            or reminder.delivery_status != "processing"
            or reminder.claim_token != token
        ):
            db.commit()
            return None
        if not _eligible(db, reminder, now):
            reminder.delivery_status = "cancelled"
            reminder.claim_token = None
            db.commit()
            return "cancelled"
        try:
            payload = reminder.payload
            if reminder.channel == "in_app":
                # UNIQUE(reminder_id) also enforces deduplication at the database layer.
                notification = db.query(Notification).filter_by(reminder_id=reminder.id).first()
                if notification is None:
                    db.add(
                        Notification(
                            reminder_id=reminder.id,
                            user_id=reminder.user_id,
                            exam_id=reminder.exam_id,
                            title=payload["title"],
                            message=payload["message"],
                            scheduled_for=datetime.fromisoformat(payload["scheduled_for"]),
                            delivered_at=now,
                        )
                    )
            else:
                if provider is None:
                    raise DeliveryError("Email provider is not configured")
                provider.send(
                    recipient=payload["recipient"],
                    subject=payload["title"],
                    body=payload["message"],
                    idempotency_key=f"studyvault-reminder-{reminder.id}",
                )
            reminder.sent = True
            reminder.delivery_status = "sent"
            reminder.delivered_at = now
            reminder.next_attempt_at = None
            reminder.last_error = None
            result = "delivered"
        except Exception as exc:
            retryable = not isinstance(exc, DeliveryError) or exc.retryable
            retryable = retryable and reminder.delivery_attempts < MAX_ATTEMPTS
            reminder.delivery_status = "retry" if retryable else "failed"
            reminder.next_attempt_at = (
                now + timedelta(seconds=60 * (2 ** (reminder.delivery_attempts - 1)))
                if retryable
                else None
            )
            reminder.last_error = (
                str(exc)[:500] if isinstance(exc, DeliveryError) else "Delivery adapter failed"
            )
            result = "retried" if retryable else "failed"
        reminder.claim_token = None
        db.commit()
        return result


def run_due_reminders(
    session_factory,
    *,
    now: datetime | None = None,
    provider: EmailProvider | None = None,
    limit: int = 100,
) -> dict[str, int]:
    """One bounded tick; pass an aware fake clock and test provider in tests."""
    injected_clock = now is not None
    now = now or utcnow()
    if now.tzinfo is None:
        raise ValueError("Reminder clock must include a timezone")
    now = now.astimezone(UTC)
    provider = provider if provider is not None else configured_provider()
    counts = {"delivered": 0, "retried": 0, "failed": 0, "cancelled": 0}
    # Adopt exams from the previous milestone without modifying any migration-era data.
    with session_factory() as db:
        acquire_reminder_lock(db)
        legacy = (
            db.query(Exam).filter(Exam.reminder_generation == 0, Exam.deleted_at.is_(None)).all()
        )
        for exam in legacy:
            generate_reminders(db, exam, now=now)
        db.commit()
    with session_factory() as db:
        ids = [
            row[0]
            for row in db.query(Reminder.id)
            .filter(
                Reminder.sent.is_(False),
                Reminder.delivery_status.in_(ACTIVE_STATUSES),
                Reminder.notify_at <= now,
                or_(Reminder.next_attempt_at.is_(None), Reminder.next_attempt_at <= now),
            )
            .order_by(Reminder.notify_at, Reminder.id)
            .limit(limit)
            .all()
        ]
    for reminder_id in ids:
        token, result = _claim(session_factory, reminder_id, now if injected_clock else utcnow())
        if token:
            result = _deliver(
                session_factory, reminder_id, token, now if injected_clock else utcnow(), provider
            )
        if result:
            counts[result] += 1
    return counts
