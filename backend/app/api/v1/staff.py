"""Faculty and administrator API for curated official academic materials.

No public role creation. Admins can authorize faculty and assign official
subjects, but the very first admin requires an operator-only bootstrap CLI.
All ordinary university accounts start with no staff privileges.
"""

from __future__ import annotations

import logging
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.datetime_type import utcnow
from app.models import (
    AcademicResource, AcademicSubject, Course, StaffAuditEvent, StaffRole,
    TeachingAssignment, User,
)
from app.object_storage import delete_stored_file, upload_validated_file
from app.storage import save_upload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/staff", tags=["faculty-admin"])


class SubjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    course_id: str = Field(min_length=1)
    semester: int = Field(ge=1, le=8)
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)


class FacultyGrant(BaseModel):
    user_id: str = Field(min_length=1)


class AssignmentCreate(BaseModel):
    faculty_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)


class PublishUpdate(BaseModel):
    is_published: bool


class FacultyResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    subject_id: str
    title: str
    category: str
    unit_number: int | None
    unit_title: str | None
    academic_session: str | None
    is_published: bool
    file_name: str | None
    size_bytes: int | None


def role_of(db: Session, user_id: str) -> str | None:
    role = db.get(StaffRole, user_id)
    return role.role if role is not None else None


def require_staff(db: Session, user: User) -> str:
    role = role_of(db, user.id)
    if role not in {"faculty", "admin"}:
        raise HTTPException(403, "Staff access required")
    if user.email_verified_at is None:
        raise HTTPException(403, "Verified email required for staff access")
    return role


def require_admin(db: Session, user: User) -> None:
    if require_staff(db, user) != "admin":
        raise HTTPException(403, "Administrator access required")


def require_assignment(db: Session, user: User, subject_id: str) -> AcademicSubject:
    role = require_staff(db, user)
    subject = db.get(AcademicSubject, subject_id)
    if subject is None:
        raise HTTPException(404, "Academic subject not found")
    if role != "admin" and db.get(TeachingAssignment, (user.id, subject_id)) is None:
        raise HTTPException(404, "Academic subject not found")
    return subject


def audit(db: Session, user: User, action: str, entity_id: str) -> None:
    db.add(StaffAuditEvent(actor_id=user.id, action=action, entity_id=entity_id))


@router.get("/me")
def staff_me(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> dict:
    role = role_of(db, current_user.id)
    # Students may fetch their role to conditionally render staff navigation.
    return {"role": role if current_user.email_verified_at is not None else None}


@router.get("/subjects")
def staff_subjects(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[dict]:
    role = require_staff(db, current_user)
    query = db.query(AcademicSubject)
    if role != "admin":
        query = query.join(
            TeachingAssignment, TeachingAssignment.subject_id == AcademicSubject.id
        ).filter(TeachingAssignment.faculty_id == current_user.id)
    return [
        {
            "id": s.id, "course_id": s.course_id, "semester": s.semester,
            "code": s.code, "name": s.name,
        }
        for s in query.order_by(AcademicSubject.name).all()
    ]


@router.post("/subjects", status_code=201)
def create_academic_subject(
    payload: SubjectCreate, current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_admin(db, current_user)
    if db.get(Course, payload.course_id) is None:
        raise HTTPException(404, "Program not found")
    subject = AcademicSubject(**payload.model_dump())
    db.add(subject)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Subject code already exists for this program and semester") from exc
    audit(db, current_user, "subject.created", subject.id)
    db.commit()
    return {"id": subject.id, "code": subject.code, "name": subject.name,
            "course_id": subject.course_id, "semester": subject.semester}


@router.post("/faculty", status_code=201)
def grant_faculty(
    payload: FacultyGrant, current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_admin(db, current_user)
    account = db.get(User, payload.user_id)
    if account is None or not account.is_active or account.email_verified_at is None:
        raise HTTPException(400, "Faculty account must exist, be active and have a verified email")
    role = db.get(StaffRole, account.id)
    if role is not None:
        raise HTTPException(409, "Account already has a staff role")
    db.add(StaffRole(user_id=account.id, role="faculty"))
    audit(db, current_user, "faculty.granted", account.id)
    db.commit()
    return {"user_id": account.id, "role": "faculty"}


@router.get("/faculty")
def list_faculty(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[dict]:
    require_admin(db, current_user)
    rows = db.query(User).join(StaffRole, StaffRole.user_id == User.id).filter(
        StaffRole.role == "faculty", User.is_active.is_(True),
    ).order_by(User.full_name).all()
    return [{"id": user.id, "full_name": user.full_name, "email": user.email} for user in rows]


@router.post("/assignments", status_code=201)
def add_assignment(
    payload: AssignmentCreate, current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_admin(db, current_user)
    faculty = db.get(User, payload.faculty_id)
    if faculty is None or not faculty.is_active or faculty.email_verified_at is None:
        raise HTTPException(400, "Verified active faculty account required")
    if role_of(db, faculty.id) != "faculty":
        raise HTTPException(400, "User is not authorized faculty")
    if db.get(AcademicSubject, payload.subject_id) is None:
        raise HTTPException(404, "Academic subject not found")
    if db.get(TeachingAssignment, (payload.faculty_id, payload.subject_id)) is not None:
        raise HTTPException(409, "Teaching assignment already exists")
    db.add(TeachingAssignment(
        faculty_id=payload.faculty_id, subject_id=payload.subject_id,
        assigned_by_id=current_user.id,
    ))
    audit(db, current_user, "assignment.created", payload.subject_id)
    db.commit()
    return payload.model_dump()


@router.get("/assignments")
def list_assignments(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[dict]:
    require_admin(db, current_user)
    return [
        {"faculty_id": row.faculty_id, "subject_id": row.subject_id}
        for row in db.query(TeachingAssignment).all()
    ]


@router.delete("/assignments/{faculty_id}/{subject_id}", status_code=204)
def remove_assignment(
    faculty_id: str, subject_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(db, current_user)
    assignment = db.get(TeachingAssignment, (faculty_id, subject_id))
    if assignment is None:
        raise HTTPException(404, "Teaching assignment not found")
    db.delete(assignment)
    audit(db, current_user, "assignment.revoked", subject_id)
    db.commit()


def assigned_resource(db: Session, user: User, resource_id: str) -> AcademicResource:
    resource = db.get(AcademicResource, resource_id)
    if resource is None:
        raise HTTPException(404, "Resource not found")
    require_assignment(db, user, resource.subject_id)
    # Admins may moderate; faculty cannot modify another teacher's uploads.
    if role_of(db, user.id) != "admin" and resource.uploaded_by_id != user.id:
        raise HTTPException(404, "Resource not found")
    return resource


@router.get("/resources", response_model=list[FacultyResourceOut])
def list_staff_resources(
    subject_id: str, current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AcademicResource]:
    require_assignment(db, current_user, subject_id)
    query = db.query(AcademicResource).filter(AcademicResource.subject_id == subject_id)
    if role_of(db, current_user.id) != "admin":
        query = query.filter(AcademicResource.uploaded_by_id == current_user.id)
    return query.order_by(AcademicResource.created_at.desc()).all()


@router.post("/resources/upload", response_model=FacultyResourceOut, status_code=201)
def upload_faculty_resource(
    subject_id: str, title: str, category: str = "notes",
    unit_number: int | None = None, unit_title: str | None = None,
    academic_session: str | None = None, file: UploadFile = File(...),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    require_assignment(db, current_user, subject_id)
    title = title.strip()
    category = category.strip()
    if not 1 <= len(title) <= 200 or not 1 <= len(category) <= 40:
        raise HTTPException(422, "Invalid resource title or category")
    if unit_number is not None and unit_number < 1:
        raise HTTPException(422, "Unit number must be positive")
    if unit_title is not None and len(unit_title) > 200:
        raise HTTPException(422, "Unit title too long")
    if academic_session is not None and not 1 <= len(academic_session.strip()) <= 20:
        raise HTTPException(422, "Invalid academic session")

    # Use the same content validation as personal uploads (PDF, images, DOCX).
    from app.api.v1.materials import reserve_storage
    from pathlib import Path

    path, key, mime, size = save_upload(file)
    filename = PurePosixPath((file.filename or key).replace("\\", "/")).name
    filename = "".join(c for c in filename if ord(c) >= 32)[:200] or key
    remote = get_settings().storage_backend == "s3"
    persisted = None
    committed = False
    try:
        reserve_storage(db, current_user.id, size)
        persisted = (
            upload_validated_file(path, f"academic/{current_user.id}/{key}", mime)
            if remote else key
        )
        resource = AcademicResource(
            subject_id=subject_id,
            title=title,
            category=category,
            unit_number=unit_number,
            unit_title=unit_title.strip() if unit_title else None,
            academic_session=academic_session.strip() if academic_session else None,
            storage_key=persisted,
            file_name=filename,
            mime_type=mime,
            size_bytes=size,
            uploaded_by_id=current_user.id,
            is_published=False,
        )
        db.add(resource)
        db.flush()
        audit(db, current_user, "resource.uploaded", resource.id)
        db.commit()
        committed = True
    except BaseException:
        db.rollback()
        if persisted is not None and persisted.startswith("s3:") and not committed:
            try:
                delete_stored_file(persisted)
            except Exception:
                logger.exception("Unable to clean up uncommitted faculty upload")
        raise
    finally:
        if remote or not committed:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Unable to remove faculty upload temp file")
    return resource


@router.patch("/resources/{resource_id}/publish", response_model=FacultyResourceOut)
def publish_faculty_resource(
    resource_id: str, payload: PublishUpdate,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> AcademicResource:
    resource = assigned_resource(db, current_user, resource_id)
    if not resource.storage_key:
        raise HTTPException(400, "This milestone only publishes stored official documents")
    resource.is_published = payload.is_published
    audit(db, current_user,
          "resource.published" if payload.is_published else "resource.unpublished",
          resource.id)
    db.commit()
    db.refresh(resource)
    return resource


@router.delete("/resources/{resource_id}", status_code=204)
def delete_faculty_resource(
    resource_id: str, current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resource = assigned_resource(db, current_user, resource_id)
    if resource.storage_key is None:
        raise HTTPException(400, "This milestone manages stored faculty files only")
    storage_key = resource.storage_key
    owner_id = resource.uploaded_by_id
    size = resource.size_bytes or 0
    db.delete(resource)
    audit(db, current_user, "resource.deleted", resource.id)
    db.flush()
    if owner_id:
        from app.api.v1.materials import release_storage
        release_storage(db, owner_id, size)
    db.commit()
    delete_stored_file(storage_key)
