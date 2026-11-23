"""Release-gate tests for trusted academic enrollment (fictional records only).

These tests deliberately use the disposable test database. There is no API for
students to create or modify trusted enrollment records.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import (
    AcademicResource,
    AcademicSubject,
    College,
    Course,
    Department,
    VerifiedEnrollment,
)

API = "/api/v1"


def register(client, name, email):
    response = client.post(
        API + "/auth/register",
        json={"full_name": name, "email": email, "password": "TestOnlyPassword123!"},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = client.get(API + "/auth/me", headers=headers).json()["id"]
    return user_id, headers


def prepare_fictional_catalog():
    """Different branch, semester, academic session, and publication scopes."""
    with SessionLocal() as db:
        college = College(name="Imaginary Technology University")
        db.add(college)
        db.flush()
        department = Department(
            college_id=college.id, name="Fictional Computer Science", code="FCS"
        )
        db.add(department)
        db.flush()
        ai = Course(college_id=college.id, department_id=department.id, name="Fictional AIML")
        ds = Course(college_id=college.id, department_id=department.id, name="Fictional Data Science")
        db.add_all([ai, ds])
        db.flush()
        aiml_subject = AcademicSubject(
            course_id=ai.id, semester=3, code="AIML301", name="Fictional Machine Learning"
        )
        ds_subject = AcademicSubject(
            course_id=ds.id, semester=3, code="DS301", name="Fictional Data Analytics"
        )
        wrong_semester = AcademicSubject(
            course_id=ai.id, semester=4, code="AIML401", name="Fictional Advanced ML"
        )
        db.add_all([aiml_subject, ds_subject, wrong_semester])
        db.flush()
        db.add_all([
            AcademicResource(
                subject_id=aiml_subject.id, title="AIML shared notes",
                url="https://example.org/aiml-notes", category="notes", is_published=True,
            ),
            AcademicResource(
                subject_id=aiml_subject.id, title="AIML current term",
                url="https://example.org/aiml-current", category="notes",
                academic_session="2026-27", is_published=True,
            ),
            AcademicResource(
                subject_id=aiml_subject.id, title="AIML past term",
                url="https://example.org/aiml-past", category="notes",
                academic_session="2025-26", is_published=True,
            ),
            AcademicResource(
                subject_id=aiml_subject.id, title="AIML draft",
                url="https://example.org/draft", category="notes", is_published=False,
            ),
            AcademicResource(
                subject_id=ds_subject.id, title="DS shared notes",
                url="https://example.org/ds-notes", category="notes", is_published=True,
            ),
            AcademicResource(
                subject_id=wrong_semester.id, title="AIML future semester",
                url="https://example.org/future", category="notes", is_published=True,
            ),
        ])
        result = (ai.id, ds.id, college.id, department.id, aiml_subject.id)
        db.commit()
        return result


def test_multi_student_branch_semester_session_isolation_and_revocation(client):
    aiml_id, ds_id, college_id, department_id, subject_id = prepare_fictional_catalog()
    ai_user, ai_headers = register(client, "Fictional AI Student", "fictional-ai@aiml.suh.edu.in")
    ds_user, ds_headers = register(client, "Fictional DS Student", "fictional-ds@ds.suh.edu.in")

    # Editing student profile never creates trusted access.
    self_report = client.put(API + "/profile/me", headers=ai_headers, json={
        "college_id": college_id, "department_id": department_id,
        "course_id": aiml_id, "year_of_study": 2, "semester": 3,
        "academic_year": "2026-27",
    })
    assert self_report.status_code == 200, self_report.text
    assert client.get(API + "/academic/subjects", headers=ai_headers).json() == []
    assert client.get(API + "/academic/resources", headers=ai_headers).json() == []

    # Test-only direct DB fixtures simulate a future approved university import.
    with SessionLocal() as db:
        db.add_all([
            VerifiedEnrollment(
                user_id=ai_user, course_id=aiml_id, semester=3,
                academic_session="2026-27", verification_source="development",
            ),
            VerifiedEnrollment(
                user_id=ds_user, course_id=ds_id, semester=3,
                academic_session="2026-27", verification_source="development",
            ),
        ])
        db.commit()

    ai_subjects = client.get(API + "/academic/subjects", headers=ai_headers).json()
    ds_subjects = client.get(API + "/academic/subjects", headers=ds_headers).json()
    assert [s["code"] for s in ai_subjects] == ["AIML301"]
    assert [s["code"] for s in ds_subjects] == ["DS301"]
    ai_titles = {r["title"] for r in client.get(API + "/academic/resources", headers=ai_headers).json()}
    ds_titles = {r["title"] for r in client.get(API + "/academic/resources", headers=ds_headers).json()}
    assert ai_titles == {"AIML shared notes", "AIML current term"}
    assert ds_titles == {"DS shared notes"}

    # Forged profile requests cannot switch either student's official scope.
    spoof = client.patch(
        API + "/profile/me", headers=ai_headers, json={"course_id": ds_id}
    )
    assert spoof.status_code == 200, spoof.text
    assert {r["title"] for r in client.get(API + "/academic/resources", headers=ai_headers).json()} == ai_titles

    # A user cannot create/change/delete trusted enrollment via the API.
    for method in (client.post, client.patch, client.delete):
        response = method(
            API + "/academic/enrollment", headers=ai_headers,
            json={"course_id": ds_id, "semester": 3} if method != client.delete else None,
        )
        assert response.status_code == 405, response.text
    assert client.get(API + "/academic/enrollment").status_code == 401

    # Revoking a published resource immediately hides it from the API.
    with SessionLocal() as db:
        resource = db.query(AcademicResource).filter_by(title="AIML current term").one()
        resource.is_published = False
        db.commit()
    assert {r["title"] for r in client.get(API + "/academic/resources", headers=ai_headers).json()} == {"AIML shared notes"}

    # Removing one student's enrollment revokes only that student's access.
    with SessionLocal() as db:
        db.query(VerifiedEnrollment).filter_by(user_id=ai_user).delete()
        db.commit()
    assert client.get(API + "/academic/enrollment", headers=ai_headers).json() is None
    assert client.get(API + "/academic/subjects", headers=ai_headers).json() == []
    assert client.get(API + "/academic/resources", headers=ai_headers).json() == []
    assert {r["title"] for r in client.get(API + "/academic/resources", headers=ds_headers).json()} == ds_titles

    # Metadata doesn't expose private material storage keys.
    assert all("storage_key" not in x for x in client.get(
        API + "/academic/resources", headers=ds_headers
    ).json())


def test_synthetic_enrollment_never_grants_production_access(client):
    aiml_id, _, _, _, _ = prepare_fictional_catalog()
    user_id, headers = register(client, "Fictional Tester", "synthetic@aiml.suh.edu.in")
    with SessionLocal() as db:
        db.add(VerifiedEnrollment(
            user_id=user_id, course_id=aiml_id, semester=3,
            academic_session="2026-27", verification_source="development",
        ))
        db.commit()
    assert client.get(API + "/academic/enrollment", headers=headers).json() is not None

    with patch(
        "app.api.v1.academic.get_settings",
        return_value=SimpleNamespace(environment="production"),
    ):
        assert client.get(API + "/academic/enrollment", headers=headers).json() is None
        assert client.get(API + "/academic/subjects", headers=headers).json() == []
        assert client.get(API + "/academic/resources", headers=headers).json() == []


def test_verified_enrollment_database_constraints(client):
    aiml_id, _, _, _, _ = prepare_fictional_catalog()
    user_id, _ = register(client, "Fictional Constraint Tester", "constraints@aiml.suh.edu.in")
    for source, semester, course_id in (
        ("development", 9, aiml_id),
        ("untrusted", 3, aiml_id),
        ("development", 3, "missing-program-id"),
    ):
        with SessionLocal() as db:
            db.add(VerifiedEnrollment(
                user_id=user_id, course_id=course_id, semester=semester,
                academic_session="2026-27", verification_source=source,
            ))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
