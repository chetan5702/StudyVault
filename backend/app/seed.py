from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.datetime_type import utcnow
from app.models import (
    ClassGroup,
    ClassMember,
    College,
    Course,
    Exam,
    Material,
    Profile,
    Reminder,
    StudyTask,
    Subject,
    Unit,
    User,
    UserStorageUsage,
)
from app.security import hash_password


def seed_database(db: Session) -> None:
    # A catalog migration can populate colleges without installing the optional
    # development demo. Use the demo account itself as the idempotency marker.
    if db.query(User).filter(User.email == "demo@studyvault.dev").first():
        return

    college = db.query(College).filter(College.name == "National College of Engineering").first()
    if college is None:
        college = College(name="National College of Engineering", city="Bengaluru")
        db.add(college)
        db.flush()

    course = (
        db.query(Course)
        .filter(
            Course.college_id == college.id,
            Course.name == "Computer Science",
            Course.degree == "B.Tech",
        )
        .first()
    )
    if course is None:
        course = Course(college_id=college.id, name="Computer Science", degree="B.Tech")
        db.add(course)
        db.flush()

    user = User(
        email="demo@studyvault.dev",
        password_hash=hash_password("Password123!"),
        full_name="Aisha Patel",
        email_verified_at=utcnow(),
        token_version=0,
    )
    db.add(user)
    db.flush()

    profile = Profile(
        user_id=user.id,
        college_id=college.id,
        course_id=course.id,
        academic_year="2025-26",
        semester=6,
        section="A",
        phone_number="+91 98765 43210",
        bio="Final-year CSE student focused on system design and exam prep.",
    )
    db.add(profile)

    subject_1 = Subject(
        user_id=user.id,
        course_id=course.id,
        code="CS401",
        name="Distributed Systems",
        semester=6,
        color="#4f46e5",
    )
    subject_2 = Subject(
        user_id=user.id,
        course_id=course.id,
        code="CS302",
        name="Operating Systems",
        semester=6,
        color="#14b8a6",
    )
    db.add_all([subject_1, subject_2])
    db.flush()

    unit_1 = Unit(subject_id=subject_1.id, name="Consistency Models", order_index=1)
    unit_2 = Unit(subject_id=subject_2.id, name="Process Scheduling", order_index=1)
    db.add_all([unit_1, unit_2])
    db.flush()

    group = ClassGroup(
        name="Semester 6 CSE Circle",
        owner_id=user.id,
        invite_code="SVCSE2025",
        description="Shared resources for exam prep and assignments.",
    )
    db.add(group)
    db.flush()

    member = ClassMember(group_id=group.id, user_id=user.id, role="owner")
    db.add(member)

    material_1 = Material(
        user_id=user.id,
        subject_id=subject_1.id,
        unit_id=unit_1.id,
        title="Distributed Systems Notes",
        description="Study notes for the final exam overview.",
        file_name="distributed-systems-notes.pdf",
        storage_key="materials/distributed-systems-notes.pdf",
        mime_type="application/pdf",
        size_bytes=123456,
        category="notes",
        visibility="private",
    )
    material_2 = Material(
        user_id=user.id,
        subject_id=subject_2.id,
        unit_id=unit_2.id,
        title="Scheduling Cheat Sheet",
        description="Quick revision sheet with diagrams.",
        file_name="os-scheduling-cheat-sheet.png",
        storage_key="materials/os-scheduling-cheat-sheet.png",
        mime_type="image/png",
        size_bytes=54000,
        category="other",
        visibility="group",
        group_id=group.id,
    )
    db.add_all([material_1, material_2])
    db.flush()
    db.add(
        UserStorageUsage(
            user_id=user.id,
            used_bytes=material_1.size_bytes + material_2.size_bytes,
        )
    )

    exam = Exam(
        user_id=user.id,
        subject_id=subject_1.id,
        subject_code_snapshot=subject_1.code,
        subject_name_snapshot=subject_1.name,
        title="Distributed Systems Midterm",
        exam_type="midterm",
        scheduled_for=utcnow() + timedelta(days=6, hours=12),
        location="Room B-204",
    )
    db.add(exam)
    db.flush()

    db.add(
        Reminder(
            exam_id=exam.id,
            notify_at=utcnow() + timedelta(days=5),
            channel="in_app",
            sent=False,
            delivery_status="pending",
        )
    )
    db.add(
        StudyTask(
            user_id=user.id,
            subject_id=subject_1.id,
            title="Finish revision for consistency models",
            due_date=utcnow() + timedelta(days=2),
            completed=False,
        )
    )
    db.add(
        StudyTask(
            user_id=user.id,
            subject_id=subject_2.id,
            title="Practice scheduling questions",
            due_date=utcnow() + timedelta(days=4),
            completed=True,
        )
    )
    db.commit()
