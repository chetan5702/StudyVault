from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.materials import member
from app.database import get_db
from app.datetime_type import utcnow
from app.models import Exam, Reminder, Subject, User
from app.reminders import acquire_reminder_lock, cancel_reminders, generate_reminders
from app.schemas import ExamCreate, ExamOut, ExamUpdate

router = APIRouter(tags=["exams"])


@router.get("/exams", response_model=list[ExamOut])
def list_exams(
    subject_id: str | None = None,
    status: Literal["all", "upcoming", "completed"] = "all",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Exam]:
    query = db.query(Exam).filter(Exam.user_id == current_user.id, Exam.deleted_at.is_(None))
    if subject_id:
        query = query.filter(Exam.subject_id == subject_id)
    if status == "upcoming":
        query = query.filter(Exam.scheduled_for > utcnow())
    elif status == "completed":
        query = query.filter(Exam.scheduled_for <= utcnow())
    return query.order_by(Exam.scheduled_for.asc()).all()


def owned_exam(db: Session, exam_id: str, user_id: str) -> Exam:
    exam = (
        db.query(Exam)
        .filter(Exam.id == exam_id, Exam.user_id == user_id, Exam.deleted_at.is_(None))
        .first()
    )
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


@router.get("/exams/{exam_id}", response_model=ExamOut)
def get_exam(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Exam:
    return owned_exam(db, exam_id, current_user.id)


@router.post("/exams", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Exam:
    acquire_reminder_lock(db)
    subject = (
        db.query(Subject)
        .filter(Subject.id == payload.subject_id, Subject.user_id == current_user.id)
        .first()
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    if payload.group_id and not member(db, current_user.id, payload.group_id):
        raise HTTPException(status_code=403, detail="Group membership required")

    exam = Exam(
        user_id=current_user.id,
        subject_id=payload.subject_id,
        subject_code_snapshot=subject.code,
        subject_name_snapshot=subject.name,
        title=payload.title,
        exam_type=payload.exam_type,
        scheduled_for=payload.scheduled_for,
        location=payload.location,
        group_id=payload.group_id,
        timezone=payload.timezone,
    )
    db.add(exam)
    generate_reminders(db, exam)
    db.commit()
    db.refresh(exam)
    return exam


@router.patch("/exams/{exam_id}", response_model=ExamOut)
def update_exam(
    exam_id: str,
    payload: ExamUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Exam:
    acquire_reminder_lock(db)
    exam = owned_exam(db, exam_id, current_user.id)
    changes = payload.model_dump(exclude_unset=True)
    if "subject_id" in changes:
        subject = (
            db.query(Subject)
            .filter(Subject.id == changes["subject_id"], Subject.user_id == current_user.id)
            .first()
        )
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        changes["subject_code_snapshot"] = subject.code
        changes["subject_name_snapshot"] = subject.name
    if changes.get("group_id") and not member(db, current_user.id, changes["group_id"]):
        raise HTTPException(status_code=403, detail="Group membership required")
    rescheduled = "scheduled_for" in changes and changes["scheduled_for"] != exam.scheduled_for
    for key, value in changes.items():
        setattr(exam, key, value)
    if rescheduled:
        generate_reminders(db, exam)
    else:
        # Preserve identifiers on information-only edits and freeze attempted email
        # payloads so an ambiguous delivery can be retried with the same key.
        db.query(Reminder).filter(
            Reminder.exam_id == exam.id,
            Reminder.delivery_status == "pending",
            Reminder.first_attempt_at.is_(None),
        ).update({"payload": None}, synchronize_session=False)
    db.commit()
    db.refresh(exam)
    return exam


@router.delete("/exams/{exam_id}")
def delete_exam(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    acquire_reminder_lock(db)
    exam = owned_exam(db, exam_id, current_user.id)
    cancel_reminders(db, exam.id)
    exam.deleted_at = utcnow()
    db.commit()
    return {"status": "deleted"}
