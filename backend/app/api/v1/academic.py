"""Read-only academic library scoped to the student's declared academic profile.

No user upload can appear here automatically. Publication requires a separate
trusted curation process; declared branch and semester are not verified enrollment.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import AcademicResource, AcademicSubject, Profile, User
from app.schemas import AcademicResourceOut, AcademicSubjectOut

router = APIRouter(tags=["academic-library"])


def current_scope(db: Session, user: User) -> tuple[str, int] | None:
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile or not profile.course_id or not profile.semester:
        return None
    return profile.course_id, profile.semester


@router.get("/academic/subjects", response_model=list[AcademicSubjectOut])
def list_academic_subjects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AcademicSubject]:
    scope = current_scope(db, current_user)
    if scope is None:
        return []
    course_id, semester = scope
    return (
        db.query(AcademicSubject)
        .filter(AcademicSubject.course_id == course_id, AcademicSubject.semester == semester)
        .order_by(AcademicSubject.name)
        .all()
    )


@router.get("/academic/resources", response_model=list[AcademicResourceOut])
def list_academic_resources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile or not profile.course_id or not profile.semester:
        return []

    # Session-specific content is excluded unless it matches the declared
    # academic session. Global resources (NULL) remain visible.
    scope_filter = AcademicResource.academic_session.is_(None)
    if profile.academic_year:
        scope_filter = or_(
            scope_filter, AcademicResource.academic_session == profile.academic_year
        )

    rows = (
        db.query(AcademicResource, AcademicSubject)
        .join(AcademicSubject, AcademicResource.subject_id == AcademicSubject.id)
        .filter(
            AcademicSubject.course_id == profile.course_id,
            AcademicSubject.semester == profile.semester,
            AcademicResource.is_published.is_(True),
            scope_filter,
        )
        .order_by(AcademicSubject.name, AcademicResource.unit_number, AcademicResource.title)
        .all()
    )
    return [
        {
            "id": resource.id,
            "subject_id": subject.id,
            "subject_code": subject.code,
            "subject_name": subject.name,
            "semester": subject.semester,
            "title": resource.title,
            "url": resource.url,
            "category": resource.category,
            "source_label": resource.source_label,
            "unit_number": resource.unit_number,
            "unit_title": resource.unit_title,
            "academic_session": resource.academic_session,
        }
        for resource, subject in rows
    ]
