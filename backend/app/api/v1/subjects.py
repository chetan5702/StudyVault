from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Course, Exam, Material, Profile, StudyTask, Subject, Unit, User
from app.schemas import SubjectCreate, SubjectOut, SubjectUpdate, UnitCreate, UnitOut, UnitUpdate

router = APIRouter(tags=["subjects"])


def owned_subject(db: Session, subject_id: str, user_id: str) -> Subject:
    subject = db.query(Subject).filter(Subject.id == subject_id, Subject.user_id == user_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


def owned_unit(db: Session, subject_id: str, unit_id: str, user_id: str) -> Unit:
    subject = owned_subject(db, subject_id, user_id)
    unit = db.query(Unit).filter(Unit.id == unit_id, Unit.subject_id == subject.id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit


def valid_subject_course(db: Session, course_id: str, user_id: str) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if profile is not None:
        mismatched_course = profile.course_id is not None and profile.course_id != course.id
        mismatched_college = (
            profile.college_id is not None and profile.college_id != course.college_id
        )
        if mismatched_course or mismatched_college:
            raise HTTPException(
                status_code=400,
                detail="Course must match your academic profile",
            )
    return course


@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Subject]:
    return (
        db.query(Subject)
        .filter(Subject.user_id == current_user.id)
        .order_by(Subject.name.asc())
        .all()
    )


@router.post("/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Subject:
    if payload.course_id is not None:
        valid_subject_course(db, payload.course_id, current_user.id)
    subject = Subject(
        user_id=current_user.id,
        course_id=payload.course_id,
        code=payload.code,
        name=payload.name,
        semester=payload.semester,
        color=payload.color or "#4f46e5",
    )
    db.add(subject)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Subject references invalid academic data",
        ) from exc
    db.refresh(subject)
    return subject


@router.get("/subjects/{subject_id}", response_model=SubjectOut)
def get_subject(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Subject:
    return owned_subject(db, subject_id, current_user.id)


@router.patch("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject(
    subject_id: str,
    payload: SubjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Subject:
    subject = owned_subject(db, subject_id, current_user.id)
    changes = payload.model_dump(exclude_unset=True)
    if "course_id" in changes and changes["course_id"] is not None:
        valid_subject_course(db, changes["course_id"], current_user.id)
    for field, value in changes.items():
        setattr(subject, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Subject references invalid academic data",
        ) from exc
    db.refresh(subject)
    return subject


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    subject = owned_subject(db, subject_id, current_user.id)
    linked_content = []
    if db.query(Material.id).filter(Material.subject_id == subject.id).first():
        linked_content.append("materials")
    if db.query(Exam.id).filter(Exam.subject_id == subject.id, Exam.deleted_at.is_(None)).first():
        linked_content.append("exams")
    if db.query(StudyTask.id).filter(StudyTask.subject_id == subject.id).first():
        linked_content.append("study tasks")
    if linked_content:
        if len(linked_content) == 1:
            content_names = linked_content[0]
        else:
            content_names = ", ".join(linked_content[:-1]) + f", and {linked_content[-1]}"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Delete linked {content_names} before deleting this subject.",
        )

    # Deleted exams remain as audit history with all reminder and notification rows.
    # Detach only those archived exams; their subject code/name snapshots preserve
    # the historical context. Active exams were rejected above.
    try:
        db.query(Exam).filter(
            Exam.subject_id == subject.id,
            Exam.deleted_at.is_not(None),
        ).update({Exam.subject_id: None}, synchronize_session=False)
        # Units are organizational children, so empty units can be removed with
        # the subject. Material links were checked first, so this cannot remove
        # an uploaded file.
        db.query(Unit).filter(Unit.subject_id == subject.id).delete(synchronize_session=False)
        db.delete(subject)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The subject is still in use and cannot be deleted.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/subjects/{subject_id}/units",
    response_model=UnitOut,
    status_code=status.HTTP_201_CREATED,
)
def create_unit(
    subject_id: str,
    payload: UnitCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Unit:
    subject = owned_subject(db, subject_id, current_user.id)

    unit = Unit(subject_id=subject.id, name=payload.name, order_index=payload.order_index)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


@router.get("/subjects/{subject_id}/units", response_model=list[UnitOut])
def list_units(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Unit]:
    subject = owned_subject(db, subject_id, current_user.id)
    return (
        db.query(Unit).filter(Unit.subject_id == subject.id).order_by(Unit.order_index.asc()).all()
    )


@router.patch("/subjects/{subject_id}/units/{unit_id}", response_model=UnitOut)
def update_unit(
    subject_id: str,
    unit_id: str,
    payload: UnitUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Unit:
    unit = owned_unit(db, subject_id, unit_id, current_user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(unit, field, value)
    db.commit()
    db.refresh(unit)
    return unit


@router.delete(
    "/subjects/{subject_id}/units/{unit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_unit(
    subject_id: str,
    unit_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    unit = owned_unit(db, subject_id, unit_id, current_user.id)
    if db.query(Material.id).filter(Material.unit_id == unit.id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delete linked materials before deleting this unit.",
        )
    try:
        db.delete(unit)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The unit is still in use and cannot be deleted.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
