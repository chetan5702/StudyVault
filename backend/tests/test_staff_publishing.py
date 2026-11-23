"""Isolated end-to-end faculty/admin permissions with fictional identities."""

from app.database import SessionLocal
from app.models import (
    AcademicResource, College, Course, Department, StaffAuditEvent, StaffRole,
    VerifiedEnrollment,
)

API = "/api/v1"


def account(client, name: str, email: str):
    response = client.post(API + "/auth/register", json={
        "full_name": name, "email": email, "password": "FictionalPassword123!",
    })
    assert response.status_code == 201, response.text
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    user_id = client.get(API + "/auth/me", headers=headers).json()["id"]
    return user_id, headers


def academic_programs():
    with SessionLocal() as db:
        college = College(name="Fictional University")
        db.add(college)
        db.flush()
        dept = Department(college_id=college.id, code="FCS", name="Fictional Computing")
        db.add(dept)
        db.flush()
        aiml = Course(
            college_id=college.id, department_id=dept.id, name="Fictional AIML",
            degree="B.Tech",
        )
        ds = Course(
            college_id=college.id, department_id=dept.id, name="Fictional DS",
            degree="B.Tech",
        )
        db.add_all([aiml, ds])
        db.flush()
        ids = aiml.id, ds.id
        db.commit()
    return ids


def admin_credential(client):
    # Test fixture only: the real system has an operator-only bootstrap tool.
    user_id, headers = account(client, "Fictional Admin", "fake-admin@suh.edu.in")
    with SessionLocal() as db:
        db.add(StaffRole(user_id=user_id, role="admin"))
        db.commit()
    return user_id, headers


def upload(client, headers, subject_id, pdf, *, title="Unit 1 verified notes",
           category="notes", session="2026-27"):
    return client.post(
        API + "/staff/resources/upload",
        headers=headers,
        params={
            "subject_id": subject_id, "title": title, "category": category,
            "unit_number": 1, "unit_title": "Introduction",
            "academic_session": session,
        },
        files={"file": ("faculty.pdf", pdf, "application/pdf")},
    )


def test_complete_faculty_admin_student_flow(client, pdf):
    ai_course, ds_course = academic_programs()
    admin_id, admin = admin_credential(client)
    faculty_id, faculty = account(client, "Fictional Faculty", "fake-faculty@suh.edu.in")
    outsider_id, outsider = account(client, "Unassigned Faculty", "fake-outside@suh.edu.in")
    student_id, student = account(client, "Fictional Student", "fake-student@aiml.suh.edu.in")
    ds_id, other_student = account(client, "Fictional DS Student", "fake-ds@ds.suh.edu.in")

    assert client.get(API + "/staff/me", headers=student).json()["role"] is None
    assert client.get(API + "/staff/subjects", headers=student).status_code == 403
    assert client.post(API + "/staff/subjects", headers=faculty, json={
        "course_id": ai_course, "semester": 3, "code": "FORBIDDEN", "name": "Fake",
    }).status_code == 403

    created = client.post(API + "/staff/subjects", headers=admin, json={
        "course_id": ai_course, "semester": 3, "code": "AIML301", "name": "ML Foundations",
    })
    assert created.status_code == 201, created.text
    subject_id = created.json()["id"]
    other_created = client.post(API + "/staff/subjects", headers=admin, json={
        "course_id": ds_course, "semester": 3, "code": "DS301", "name": "Data Analytics",
    })
    assert other_created.status_code == 201, other_created.text
    other_subject_id = other_created.json()["id"]
    duplicate = client.post(API + "/staff/subjects", headers=admin, json={
        "course_id": ai_course, "semester": 3, "code": "AIML301", "name": "Duplicate",
    })
    assert duplicate.status_code == 409

    assert client.post(API + "/staff/faculty", headers=student, json={
        "user_id": student_id,
    }).status_code == 403
    assert client.post(API + "/staff/faculty", headers=admin, json={
        "user_id": faculty_id,
    }).status_code == 201
    assert client.post(API + "/staff/faculty", headers=admin, json={
        "user_id": outsider_id,
    }).status_code == 201
    assert client.get(API + "/staff/me", headers=faculty).json()["role"] == "faculty"
    assert client.post(API + "/staff/assignments", headers=faculty, json={
        "faculty_id": faculty_id, "subject_id": subject_id,
    }).status_code == 403
    assert client.post(API + "/staff/assignments", headers=admin, json={
        "faculty_id": faculty_id, "subject_id": subject_id,
    }).status_code == 201
    assert client.post(API + "/staff/assignments", headers=admin, json={
        "faculty_id": faculty_id, "subject_id": subject_id,
    }).status_code == 409
    assert [row["id"] for row in client.get(API + "/staff/subjects", headers=faculty).json()] == [subject_id]
    assert client.get(
        API + "/staff/resources", headers=outsider, params={"subject_id": subject_id}
    ).status_code == 404
    assert client.get(API + "/staff/subjects", headers=outsider).json() == []
    assert upload(client, outsider, subject_id, pdf).status_code == 404
    assert upload(client, student, subject_id, pdf).status_code == 403

    with SessionLocal() as db:
        db.add_all([
            VerifiedEnrollment(
                user_id=student_id, course_id=ai_course, semester=3,
                academic_session="2026-27", verification_source="development",
            ),
            VerifiedEnrollment(
                user_id=ds_id, course_id=ds_course, semester=3,
                academic_session="2026-27", verification_source="development",
            ),
        ])
        db.commit()

    draft = upload(client, faculty, subject_id, pdf)
    assert draft.status_code == 201, draft.text
    resource_id = draft.json()["id"]
    assert draft.json()["is_published"] is False
    assert client.get(API + "/academic/resources", headers=student).json() == []
    assert client.get(
        API + f"/academic/resources/{resource_id}/download", headers=student
    ).status_code == 404
    assert client.patch(
        API + f"/staff/resources/{resource_id}/publish", headers=outsider,
        json={"is_published": True},
    ).status_code == 404
    assert client.patch(
        API + f"/staff/resources/{resource_id}/publish", headers=student,
        json={"is_published": True},
    ).status_code == 403

    published = client.patch(
        API + f"/staff/resources/{resource_id}/publish", headers=faculty,
        json={"is_published": True},
    )
    assert published.status_code == 200, published.text
    listed = client.get(API + "/academic/resources", headers=student).json()
    assert len(listed) == 1
    assert listed[0]["title"] == "Unit 1 verified notes"
    assert listed[0]["url"] is None
    assert listed[0]["file_name"] == "faculty.pdf"
    assert listed[0]["download_url"] == f"/academic/resources/{resource_id}/download"
    assert "storage_key" not in listed[0]
    assert client.get(
        API + f"/academic/resources/{resource_id}/download", headers=student
    ).content == pdf
    assert client.get(
        API + f"/academic/resources/{resource_id}/download", headers=other_student
    ).status_code == 404
    assert client.get(
        API + f"/academic/resources/{resource_id}/download", headers=outsider
    ).status_code == 404
    assert client.get(
        API + f"/academic/resources/{resource_id}/download"
    ).status_code == 401

    assert client.patch(
        API + f"/staff/resources/{resource_id}/publish", headers=faculty,
        json={"is_published": False},
    ).status_code == 200
    assert client.get(
        API + f"/academic/resources/{resource_id}/download", headers=student
    ).status_code == 404

    # Revoking assignment prevents further faculty publishing.
    assert client.delete(
        API + f"/staff/assignments/{faculty_id}/{subject_id}", headers=admin
    ).status_code == 204
    assert client.patch(
        API + f"/staff/resources/{resource_id}/publish", headers=faculty,
        json={"is_published": True},
    ).status_code == 404
    assert client.delete(
        API + f"/staff/resources/{resource_id}", headers=admin
    ).status_code == 204
    with SessionLocal() as db:
        assert db.get(AcademicResource, resource_id) is None
        assert db.query(StaffAuditEvent).filter_by(actor_id=admin_id).count() >= 5
        assert db.query(StaffAuditEvent).filter_by(actor_id=faculty_id).count() >= 3


def test_faculty_rejects_invalid_upload_and_out_of_scope_term(client, pdf):
    ai_course, _ = academic_programs()
    _, admin = admin_credential(client)
    teacher_id, faculty = account(client, "Fictional Faculty", "upload-teacher@suh.edu.in")
    student_id, student = account(client, "Fictional Student", "upload-student@aiml.suh.edu.in")
    subject = client.post(API + "/staff/subjects", headers=admin, json={
        "course_id": ai_course, "semester": 4, "code": "AI401", "name": "AI Semester Four",
    }).json()
    subject_id = subject["id"]
    assert client.post(API + "/staff/faculty", headers=admin, json={
        "user_id": teacher_id,
    }).status_code == 201
    assert client.post(API + "/staff/assignments", headers=admin, json={
        "faculty_id": teacher_id, "subject_id": subject_id,
    }).status_code == 201
    bad = client.post(API + "/staff/resources/upload", headers=faculty,
        params={"subject_id": subject_id, "title": "Fake PDF"},
        files={"file": ("fake.pdf", b"not really a PDF", "application/pdf")})
    assert bad.status_code == 400
    assert client.get(
        API + "/staff/resources", headers=faculty, params={"subject_id": subject_id}
    ).json() == []
    with SessionLocal() as db:
        db.add(VerifiedEnrollment(
            user_id=student_id, course_id=ai_course, semester=4,
            academic_session="2026-27", verification_source="development",
        ))
        db.commit()
    resource = upload(client, faculty, subject_id, pdf, session="2025-26")
    assert resource.status_code == 201, resource.text
    resource_id = resource.json()["id"]
    assert client.patch(
        API + f"/staff/resources/{resource_id}/publish", headers=faculty,
        json={"is_published": True},
    ).status_code == 200
    assert client.get(API + "/academic/resources", headers=student).json() == []
    assert client.get(
        API + f"/academic/resources/{resource_id}/download", headers=student
    ).status_code == 404
