from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import College, Course
from app.schemas import CollegeOut, CourseOut

router = APIRouter(tags=["catalog"])


@router.get("/colleges", response_model=list[CollegeOut])
def list_colleges(db: Session = Depends(get_db)) -> list[College]:
    return db.query(College).order_by(College.name).all()


@router.get("/courses", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db)) -> list[Course]:
    return db.query(Course).order_by(Course.name).all()
