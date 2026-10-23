from app.database import SessionLocal
from app.models import College, Course

P = "/api/v1"


def create_catalog() -> tuple[str, str, str, str]:
    with SessionLocal() as db:
        first_college = College(name="First College")
        second_college = College(name="Second College")
        db.add_all([first_college, second_college])
        db.flush()
        first_course = Course(college_id=first_college.id, name="First Course")
        second_course = Course(college_id=second_college.id, name="Second Course")
        db.add_all([first_course, second_course])
        db.flush()
        identifiers = (
            first_college.id,
            first_course.id,
            second_college.id,
            second_course.id,
        )
        db.commit()
        return identifiers


def test_profile_patch_validates_the_resulting_college_and_course(client, student):
    first_college, first_course, second_college, second_course = create_catalog()

    response = client.patch(
        P + "/profile/me",
        headers=student,
        json={"college_id": first_college, "course_id": first_course},
    )
    assert response.status_code == 200, response.text

    response = client.patch(P + "/profile/me", headers=student, json={"course_id": second_course})
    assert response.status_code == 400, response.text
    profile = client.get(P + "/profile/me", headers=student).json()
    assert profile["college_id"] == first_college
    assert profile["course_id"] == first_course

    response = client.patch(P + "/profile/me", headers=student, json={"college_id": second_college})
    assert response.status_code == 200, response.text
    assert response.json()["college_id"] == second_college
    assert response.json()["course_id"] is None

    response = client.patch(P + "/profile/me", headers=student, json={"course_id": second_course})
    assert response.status_code == 200, response.text
    assert response.json()["course_id"] == second_course

    response = client.patch(P + "/profile/me", headers=student, json={"college_id": None})
    assert response.status_code == 200, response.text
    assert response.json()["college_id"] is None
    assert response.json()["course_id"] is None


def test_task_patch_can_update_only_completed(client, student):
    created = client.post(
        P + "/tasks",
        headers=student,
        json={"title": "Review chapter", "description": "Pages 1-10"},
    )
    assert created.status_code == 201, created.text

    response = client.patch(
        P + f"/tasks/{created.json()['id']}",
        headers=student,
        json={"completed": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["completed"] is True
    assert response.json()["title"] == "Review chapter"
    assert response.json()["description"] == "Pages 1-10"


def test_task_patch_rejects_clearing_required_values(client, student):
    created = client.post(P + "/tasks", headers=student, json={"title": "Review"})
    assert created.status_code == 201, created.text

    for payload in ({"title": None}, {"completed": None}):
        response = client.patch(P + f"/tasks/{created.json()['id']}", headers=student, json=payload)
        assert response.status_code == 422, response.text

    task = client.get(P + "/tasks", headers=student).json()[0]
    assert task["title"] == "Review"
    assert task["completed"] is False
