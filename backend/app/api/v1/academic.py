"""Read-only academic resources scoped to trusted enrollment, not editable Profile.

A separate approved provisioning mechanism will populate enrollments. Students
have no route to write or select a trusted academic scope.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import AcademicResource, AcademicSubject, User, VerifiedEnrollment
from app.schemas import AcademicResourceOut, AcademicSubjectOut, VerifiedEnrollmentOut

router = APIRouter(tags=["academic-library"])


def current_enrollment(db: Session, user: User) -> VerifiedEnrollment | None:
    enrollment = db.get(VerifiedEnrollment, user.id)
    if enrollment is None:
        return None
    # Synthetic test enrollment is NEVER an authorized production record.
    if enrollment.verification_source == "development" and get_settings().environment == "production":
        return None
    return enrollment


@router.get("/academic/enrollment", response_model=VerifiedEnrollmentOut | None)
def my_verified_enrollment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerifiedEnrollment | None:
    return current_enrollment(db, current_user)


@router.get("/academic/subjects", response_model=list[AcademicSubjectOut])
def list_academic_subjects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AcademicSubject]:
    enrollment = current_enrollment(db, current_user)
    if enrollment is None:
        return []
    return (
        db.query(AcademicSubject)
        .filter(
            AcademicSubject.course_id == enrollment.course_id,
            AcademicSubject.semester == enrollment.semester,
        )
        .order_by(AcademicSubject.name)
        .all()
    )


@router.get("/academic/resources", response_model=list[AcademicResourceOut])
def list_academic_resources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    enrollment = current_enrollment(db, current_user)
    if enrollment is None:
        return []

    rows = (
        db.query(AcademicResource, AcademicSubject)
        .join(AcademicSubject, AcademicResource.subject_id == AcademicSubject.id)
        .filter(
            AcademicSubject.course_id == enrollment.course_id,
            AcademicSubject.semester == enrollment.semester,
            AcademicResource.is_published.is_(True),
            or_(
                AcademicResource.academic_session.is_(None),
                AcademicResource.academic_session == enrollment.academic_session,
            ),
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
