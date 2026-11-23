from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import College, Course, Department, Profile, User
from app.schemas import ProfileOut, ProfileUpdate

router = APIRouter(tags=["profile"])


@router.get("/profile/me", response_model=ProfileOut)
def get_profile(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile is None:
        profile = Profile(user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.put("/profile/me", response_model=ProfileOut)
@router.patch("/profile/me", response_model=ProfileOut)
def update_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile is None:
        profile = Profile(user_id=current_user.id)
        db.add(profile)

    changes = payload.model_dump(exclude_unset=True)
    college_id = changes.get("college_id", profile.college_id)
    department_id = changes.get("department_id", profile.department_id)
    course_id = changes.get("course_id", profile.course_id)

    if college_id and not db.get(College, college_id):
        raise HTTPException(400, "College not found")

    # Changing a higher academic scope clears stale lower-level selections.
    if "college_id" in changes:
        if "department_id" not in changes and department_id:
            previous_department = db.get(Department, department_id)
            if not previous_department or previous_department.college_id != college_id:
                changes["department_id"] = None
                department_id = None
        if "course_id" not in changes and course_id:
            previous_course = db.get(Course, course_id)
            if not previous_course or previous_course.college_id != college_id:
                changes["course_id"] = None
                course_id = None

    department = db.get(Department, department_id) if department_id else None
    if department_id and (not department or department.college_id != college_id):
        raise HTTPException(400, "Department must belong to selected college")

    course = db.get(Course, course_id) if course_id else None
    if course_id and (not course or course.college_id != college_id):
        raise HTTPException(400, "Branch must belong to selected college")

    if course and course.department_id:
        if department_id is None and "department_id" not in changes:
            department_id = course.department_id
            changes["department_id"] = department_id
        elif course.department_id != department_id:
            if "course_id" not in changes and "department_id" in changes:
                changes["course_id"] = None
                course_id = None
            else:
                raise HTTPException(400, "Branch must belong to selected department")
    elif course and department_id:
        # Old manually created courses may be unassigned; do not pretend they
        # belong to the new department without an administrator mapping them.
        if "course_id" not in changes and "department_id" in changes:
            changes["course_id"] = None
            course_id = None
        else:
            raise HTTPException(400, "Branch has not been assigned to this department")

    year = changes.get("year_of_study", profile.year_of_study)
    semester = changes.get("semester", profile.semester)
    if year is not None and semester is not None and (semester > 8 or (semester + 1) // 2 != year):
        raise HTTPException(400, "Semester must match the selected B.Tech year")

    for field, value in changes.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
