from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import StudyTask, Subject, User
from app.schemas import StudyTaskCreate, StudyTaskOut, StudyTaskUpdate

router = APIRouter(tags=["study-tasks"])


def validate_subject(db: Session, subject_id: str | None, user_id: str) -> None:
    if subject_id and not db.query(Subject).filter_by(id=subject_id, user_id=user_id).first():
        raise HTTPException(status_code=404, detail="Subject not found")


@router.get("/tasks", response_model=list[StudyTaskOut])
def list_tasks(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[StudyTask]:
    return (
        db.query(StudyTask)
        .filter(StudyTask.user_id == current_user.id)
        .order_by(StudyTask.due_date.asc().nullslast())
        .all()
    )


@router.post("/tasks", response_model=StudyTaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: StudyTaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudyTask:
    validate_subject(db, payload.subject_id, current_user.id)
    task = StudyTask(
        user_id=current_user.id,
        subject_id=payload.subject_id,
        title=payload.title,
        description=payload.description,
        due_date=payload.due_date,
        completed=payload.completed,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/tasks/{task_id}", response_model=StudyTaskOut)
def update_task(
    task_id: str,
    payload: StudyTaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudyTask:
    task = (
        db.query(StudyTask)
        .filter(StudyTask.id == task_id, StudyTask.user_id == current_user.id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Study task not found")
    if "subject_id" in payload.model_fields_set:
        validate_subject(db, payload.subject_id, current_user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    task = (
        db.query(StudyTask)
        .filter(StudyTask.id == task_id, StudyTask.user_id == current_user.id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Study task not found")
    db.delete(task)
    db.commit()
    return {"status": "deleted"}
