from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Exam, Material, StudyTask, Subject, User

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    total_subjects = db.query(Subject).filter(Subject.user_id == current_user.id).count()
    total_materials = db.query(Material).filter(Material.user_id == current_user.id).count()
    upcoming_query = db.query(Exam).filter(
        Exam.user_id == current_user.id,
        Exam.scheduled_for >= datetime.now(UTC),
        Exam.deleted_at.is_(None),
    )
    upcoming_exams = upcoming_query.order_by(Exam.scheduled_for.asc()).limit(5).all()
    pending_tasks = (
        db.query(StudyTask)
        .filter(StudyTask.user_id == current_user.id, StudyTask.completed.is_(False))
        .order_by(StudyTask.due_date.asc())
        .limit(5)
        .all()
    )
    recent_materials = (
        db.query(Material)
        .filter(Material.user_id == current_user.id)
        .order_by(Material.created_at.desc())
        .limit(5)
        .all()
    )

    next_exam = upcoming_exams[0] if upcoming_exams else None
    return {
        "welcome": f"Welcome back, {current_user.full_name.split()[0] if current_user.full_name.strip() else 'student'}",
        "stats": {
            "subjects": total_subjects,
            "materials": total_materials,
            "upcoming_exams": upcoming_query.count(),
            "pending_tasks": db.query(StudyTask)
            .filter(StudyTask.user_id == current_user.id, StudyTask.completed.is_(False))
            .count(),
        },
        "next_exam": {
            "title": next_exam.title,
            "subject": next_exam.subject.name if next_exam and next_exam.subject else "",
            "scheduled_for": next_exam.scheduled_for.isoformat(),
        }
        if next_exam
        else None,
        "recent_materials": [
            {
                "id": item.id,
                "title": item.title,
                "category": item.category,
                "file_name": item.file_name,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in recent_materials
        ],
        "pending_tasks": [
            {
                "id": item.id,
                "title": item.title,
                "completed": item.completed,
                "due_date": item.due_date.isoformat() if item.due_date else None,
            }
            for item in pending_tasks
        ],
    }
