from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import College, Course, Department
from app.schemas import CollegeOut, CourseOut, DepartmentOut

router = APIRouter(tags=["catalog"])


@router.get("/colleges", response_model=list[CollegeOut])
def list_colleges(db: Session = Depends(get_db)) -> list[College]:
    return db.query(College).order_by(College.name).all()


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    college_id: str | None = None, db: Session = Depends(get_db)
) -> list[Department]:
    query = db.query(Department)
    if college_id:
        query = query.filter(Department.college_id == college_id)
    return query.order_by(Department.name).all()


@router.get("/courses", response_model=list[CourseOut])
def list_courses(
    college_id: str | None = None,
    department_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[Course]:
    query = db.query(Course)
    if college_id:
        query = query.filter(Course.college_id == college_id)
    if department_id:
        query = query.filter(Course.department_id == department_id)
    return query.order_by(Course.name).all()
