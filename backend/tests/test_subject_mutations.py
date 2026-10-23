from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import College, Course, Exam, Notification, Profile, Reminder, Subject, Unit, User

P = "/api/v1"


def create_subject(client, headers, code="CS101"):
    response = client.post(
        P + "/subjects",
        headers=headers,
        json={"code": code, "name": "Computer Science", "semester": 1},
    )
    assert response.status_code == 201, response.text
    return response.json()


def second_student(client):
    response = client.post(
        P + "/auth/register",
        json={
            "full_name": "Student Two",
            "email": "two@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def configure_academic_profile():
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "one@example.com").one()
        college = College(name="Student College")
        other_college = College(name="Other College")
        db.add_all([college, other_college])
        db.flush()
        selected_course = Course(college_id=college.id, name="Selected Course")
        same_college_course = Course(college_id=college.id, name="Other Course")
        other_college_course = Course(college_id=other_college.id, name="External Course")
        db.add_all([selected_course, same_college_course, other_college_course])
        db.flush()
        profile = db.query(Profile).filter(Profile.user_id == user.id).one()
        profile.college_id = college.id
        profile.course_id = selected_course.id
        course_ids = selected_course.id, same_college_course.id, other_college_course.id
        db.commit()
        return course_ids


def test_owner_can_update_subject(client, student):
    created = create_subject(client, student)

    response = client.patch(
        P + f"/subjects/{created['id']}",
        headers=student,
        json={"code": "  CS201  ", "name": "  Data Structures  ", "semester": 2},
    )

    assert response.status_code == 200, response.text
    assert response.json()["code"] == "CS201"
    assert response.json()["name"] == "Data Structures"
    assert response.json()["semester"] == 2
    assert client.get(P + f"/subjects/{created['id']}", headers=student).json() == response.json()


def test_other_student_cannot_update_or_delete_subject(client, student):
    created = create_subject(client, student)
    other = second_student(client)

    assert (
        client.patch(
            P + f"/subjects/{created['id']}",
            headers=other,
            json={"name": "Taken over"},
        ).status_code
        == 404
    )
    assert client.delete(P + f"/subjects/{created['id']}", headers=other).status_code == 404
    assert client.get(P + f"/subjects/{created['id']}", headers=student).status_code == 200


def test_delete_subject_removes_empty_units(client, student):
    created = create_subject(client, student)
    unit = client.post(
        P + f"/subjects/{created['id']}/units",
        headers=student,
        json={"subject_id": created["id"], "name": "Introduction", "order_index": 1},
    )
    assert unit.status_code == 201, unit.text

    response = client.delete(P + f"/subjects/{created['id']}", headers=student)

    assert response.status_code == 204, response.text
    assert response.content == b""
    assert client.get(P + f"/subjects/{created['id']}", headers=student).status_code == 404
    with SessionLocal() as db:
        assert db.query(Unit).filter(Unit.subject_id == created["id"]).count() == 0


def test_delete_subject_preserves_linked_content(client, student, pdf):
    created = create_subject(client, student)
    material = client.post(
        P + "/materials/upload",
        headers=student,
        params={"subject_id": created["id"], "title": "Lecture notes"},
        files={"file": ("notes.pdf", pdf, "application/pdf")},
    )
    assert material.status_code == 201, material.text
    exam = client.post(
        P + "/exams",
        headers=student,
        json={
            "subject_id": created["id"],
            "title": "Midterm",
            "scheduled_for": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        },
    )
    assert exam.status_code == 201, exam.text
    task = client.post(
        P + "/tasks",
        headers=student,
        json={"subject_id": created["id"], "title": "Revise"},
    )
    assert task.status_code == 201, task.text

    response = client.delete(P + f"/subjects/{created['id']}", headers=student)

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == (
        "Delete linked materials, exams, and study tasks before deleting this subject."
    )
    assert client.get(P + f"/subjects/{created['id']}", headers=student).status_code == 200
    download = client.get(P + f"/materials/{material.json()['id']}/download", headers=student)
    assert download.status_code == 200
    assert download.content == pdf


def test_subject_deletion_detaches_archived_exam_and_preserves_reminder_history(client, student):
    created = create_subject(client, student, code="HIST101")
    exam_response = client.post(
        P + "/exams",
        headers=student,
        json={
            "subject_id": created["id"],
            "title": "History final",
            "scheduled_for": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        },
    )
    assert exam_response.status_code == 201, exam_response.text
    exam_id = exam_response.json()["id"]

    # The nullable link is reserved for archived rows. Keep active exam API
    # serialization and ownership protected at the database layer.
    with SessionLocal() as db:
        active_exam = db.get(Exam, exam_id)
        assert active_exam is not None
        active_exam.subject_id = None
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.get(Exam, exam_id).subject_id == created["id"]

    # An active exam must continue to protect its subject relationship.
    blocked = client.delete(P + f"/subjects/{created['id']}", headers=student)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"] == "Delete linked exams before deleting this subject."

    # Simulate a reminder that was already delivered before the exam was archived.
    with SessionLocal() as db:
        exam = db.get(Exam, exam_id)
        reminders = (
            db.query(Reminder)
            .filter(Reminder.exam_id == exam_id)
            .order_by(Reminder.notify_at)
            .all()
        )
        assert exam is not None
        assert reminders
        reminder = reminders[0]
        reminder_ids = {item.id for item in reminders}
        delivered_at = datetime.now(UTC)
        reminder.sent = True
        reminder.delivery_status = "sent"
        reminder.delivered_at = delivered_at
        notification = Notification(
            reminder_id=reminder.id,
            user_id=exam.user_id,
            exam_id=exam.id,
            title="Exam reminder: History final",
            message="History final is approaching.",
            scheduled_for=exam.scheduled_for,
            delivered_at=delivered_at,
        )
        db.add(notification)
        db.commit()
        reminder_id = reminder.id
        notification_id = notification.id

    deleted_exam = client.delete(P + f"/exams/{exam_id}", headers=student)
    assert deleted_exam.status_code == 200, deleted_exam.text
    deleted_subject = client.delete(P + f"/subjects/{created['id']}", headers=student)
    assert deleted_subject.status_code == 204, deleted_subject.text

    with SessionLocal() as db:
        archived_exam = db.get(Exam, exam_id)
        assert archived_exam is not None
        assert archived_exam.deleted_at is not None
        assert archived_exam.subject_id is None
        assert archived_exam.subject_code_snapshot == "HIST101"
        assert archived_exam.subject_name_snapshot == "Computer Science"
        preserved_reminder_ids = {
            item.id for item in db.query(Reminder).filter(Reminder.exam_id == exam_id).all()
        }
        assert preserved_reminder_ids == reminder_ids
        assert db.get(Reminder, reminder_id) is not None
        notification = db.get(Notification, notification_id)
        assert notification is not None
        assert notification.exam_id == exam_id
        assert notification.reminder_id == reminder_id
        assert db.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_subject_update_rejects_invalid_required_values(client, student):
    created = create_subject(client, student)

    assert (
        client.patch(
            P + f"/subjects/{created['id']}", headers=student, json={"name": None}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            P + f"/subjects/{created['id']}", headers=student, json={"code": "   "}
        ).status_code
        == 422
    )
    assert (
        client.patch(P + f"/subjects/{created['id']}", headers=student, json={}).status_code == 422
    )


@pytest.mark.parametrize("semester", [-50, 0, 21])
def test_subject_create_rejects_invalid_semester(client, student, semester):
    response = client.post(
        P + "/subjects",
        headers=student,
        json={"code": "CS101", "name": "Computer Science", "semester": semester},
    )

    assert response.status_code == 422, response.text
    assert client.get(P + "/subjects", headers=student).json() == []


def test_subject_create_and_update_reject_unknown_course(client, student):
    response = client.post(
        P + "/subjects",
        headers=student,
        json={"code": "CS101", "name": "Computer Science", "course_id": "missing"},
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Course not found"

    created = create_subject(client, student)
    response = client.patch(
        P + f"/subjects/{created['id']}",
        headers=student,
        json={"course_id": "missing"},
    )
    assert response.status_code == 404, response.text
    with SessionLocal() as db:
        stored = db.get(Subject, created["id"])
        assert stored is not None
        assert stored.course_id is None


def test_subject_course_must_match_configured_academic_profile(client, student):
    selected_id, same_college_id, other_college_id = configure_academic_profile()
    accepted = client.post(
        P + "/subjects",
        headers=student,
        json={
            "code": "CS101",
            "name": "Computer Science",
            "semester": 1,
            "course_id": selected_id,
        },
    )
    assert accepted.status_code == 201, accepted.text

    for course_id in (same_college_id, other_college_id):
        rejected = client.post(
            P + "/subjects",
            headers=student,
            json={"code": "BAD", "name": "Wrong course", "course_id": course_id},
        )
        assert rejected.status_code == 400, rejected.text
        assert rejected.json()["detail"] == "Course must match your academic profile"

    rejected_update = client.patch(
        P + f"/subjects/{accepted.json()['id']}",
        headers=student,
        json={"course_id": other_college_id},
    )
    assert rejected_update.status_code == 400, rejected_update.text
    persisted = client.get(P + f"/subjects/{accepted.json()['id']}", headers=student)
    assert persisted.status_code == 200
    assert persisted.json()["course_id"] == selected_id


def test_subject_update_rejects_invalid_semester_without_changing_subject(client, student):
    created = create_subject(client, student)

    response = client.patch(
        P + f"/subjects/{created['id']}",
        headers=student,
        json={"semester": -50},
    )

    assert response.status_code == 422, response.text
    persisted = client.get(P + f"/subjects/{created['id']}", headers=student)
    assert persisted.status_code == 200
    assert persisted.json()["semester"] == 1
