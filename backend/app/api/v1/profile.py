from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import College, Course, Profile, User
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
    course_id = changes.get("course_id", profile.course_id)

    if college_id and not db.get(College, college_id):
        raise HTTPException(400, "College not found")

    course = db.get(Course, course_id) if course_id else None
    if "college_id" in changes and "course_id" not in changes:
        if course and course.college_id != college_id:
            changes["course_id"] = None
            course_id = None
            course = None
        elif course_id and not course:
            changes["course_id"] = None
            course_id = None

    if course_id and (not course or not college_id or course.college_id != college_id):
        raise HTTPException(400, "Course must belong to selected college")

    for field, value in changes.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
