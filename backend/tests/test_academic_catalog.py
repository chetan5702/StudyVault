"""Academic cohort navigation is scoped to the authenticated student's profile."""

from app.database import SessionLocal
from app.models import (
    AcademicResource,
    AcademicSubject,
    College,
    Course,
    Department,
    User,
)

P = "/api/v1"


def catalog():
    with SessionLocal() as db:
        college = College(name="Test University")
        other_college = College(name="Other University")
        db.add_all([college, other_college])
        db.flush()
        department = Department(college_id=college.id, code="CSE", name="Computer Science")
        other_department = Department(
            college_id=other_college.id, code="CSE", name="Other Computer Science"
        )
        db.add_all([department, other_department])
        db.flush()
        aiml = Course(
            college_id=college.id, department_id=department.id,
            name="CSE AI and ML", degree="B.Tech",
        )
        ds = Course(
            college_id=college.id, department_id=department.id,
            name="CSE Data Science", degree="B.Tech",
        )
        other = Course(
            college_id=other_college.id, department_id=other_department.id,
            name="Other Branch", degree="B.Tech",
        )
        db.add_all([aiml, ds, other])
        db.flush()
        result = (college.id, department.id, aiml.id, ds.id, other_college.id, other_department.id, other.id)
        db.commit()
    return result


def test_academic_profile_requires_consistent_college_department_branch_year(client, student):
    college, department, aiml, ds, other_college, other_department, other = catalog()
    departments = client.get(P + "/departments", params={"college_id": college}).json()
    assert [(d["code"], d["id"]) for d in departments] == [("CSE", department)]
    branches = client.get(P + "/courses", params={"department_id": department}).json()
    assert {c["id"] for c in branches} == {aiml, ds}

    initial = client.put(
        P + "/profile/me",
        headers=student,
        json={
            "college_id": college,
            "department_id": department,
            "course_id": aiml,
            "year_of_study": 2,
            "semester": 4,
            "academic_year": "2026-27",
        },
    )
    assert initial.status_code == 200, initial.text
    assert initial.json()["year_of_study"] == 2
    assert initial.json()["department_id"] == department

    invalid = (
        {"semester": 5},
        {"year_of_study": 3},
        {"course_id": other},
        {"department_id": other_department},
    )
    for payload in invalid:
        response = client.patch(P + "/profile/me", headers=student, json=payload)
        assert response.status_code == 400, (payload, response.text)

    # Explicitly changing the department clears the mismatched prior branch.
    new_department = Department(college_id=college, code="EE", name="Electrical")
    with SessionLocal() as db:
        db.add(new_department)
        db.commit()
        new_id = new_department.id
    changed = client.patch(
        P + "/profile/me", headers=student, json={"department_id": new_id}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["course_id"] is None


def test_published_materials_filtered_by_course_semester_and_session(client, student):
    college, department, aiml, ds, *_ = catalog()
    with SessionLocal() as db:
        subjects = [
            AcademicSubject(course_id=aiml, semester=4, code="OS", name="Operating Systems"),
            AcademicSubject(course_id=aiml, semester=3, code="DSA", name="Algorithms"),
            AcademicSubject(course_id=ds, semester=4, code="DATA", name="Data Science"),
        ]
        db.add_all(subjects)
        db.flush()
        resources = [
            AcademicResource(
                subject_id=subjects[0].id, title="OS Unit 2", url="https://example.edu/os",
                category="notes", unit_number=2, unit_title="Processes", is_published=True,
            ),
            AcademicResource(
                subject_id=subjects[0].id, title="OS 2026-27", url="https://example.edu/2026",
                category="past-paper", academic_session="2026-27", is_published=True,
            ),
            AcademicResource(
                subject_id=subjects[0].id, title="Old OS 2025-26", url="https://example.edu/2025",
                category="past-paper", academic_session="2025-26", is_published=True,
            ),
            AcademicResource(
                subject_id=subjects[0].id, title="Pending review", url="https://example.edu/hidden",
                category="notes", is_published=False,
            ),
            AcademicResource(
                subject_id=subjects[1].id, title="Other semester", url="https://example.edu/dsa",
                category="notes", is_published=True,
            ),
            AcademicResource(
                subject_id=subjects[2].id, title="Another branch", url="https://example.edu/ds",
                category="notes", is_published=True,
            ),
        ]
        db.add_all(resources)
        db.commit()

    assert client.get(P + "/academic/subjects", headers=student).json() == []
    assert client.get(P + "/academic/resources", headers=student).json() == []

    selected = client.put(
        P + "/profile/me", headers=student,
        json={
            "college_id": college, "department_id": department, "course_id": aiml,
            "year_of_study": 2, "semester": 4, "academic_year": "2026-27",
        },
    )
    assert selected.status_code == 200, selected.text
    subjects_response = client.get(P + "/academic/subjects", headers=student)
    assert subjects_response.status_code == 200
    assert [s["code"] for s in subjects_response.json()] == ["OS"]

    resource_response = client.get(P + "/academic/resources", headers=student)
    assert resource_response.status_code == 200
    assert {r["title"] for r in resource_response.json()} == {"OS Unit 2", "OS 2026-27"}
    assert resource_response.json()[0]["subject_name"] == "Operating Systems"
    assert all("storage_key" not in item for item in resource_response.json())

    switched = client.patch(
        P + "/profile/me", headers=student, json={"course_id": ds}
    )
    assert switched.status_code == 200, switched.text
    assert [s["code"] for s in client.get(P + "/academic/subjects", headers=student).json()] == ["DATA"]
    assert {r["title"] for r in client.get(P + "/academic/resources", headers=student).json()} == {
        "Another branch"
    }


def test_academic_resources_require_authentication(client):
    assert client.get(P + "/academic/subjects").status_code == 401
    assert client.get(P + "/academic/resources").status_code == 401
