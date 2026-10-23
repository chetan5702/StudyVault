from tests.test_workflow import P, second, subject


def test_tasks_cannot_reference_another_students_subject(client, student):
    foreign_subject = subject(client, second(client))
    payload = {"title": "Revision", "subject_id": foreign_subject}
    assert client.post(P + "/tasks", headers=student, json=payload).status_code == 404
    assert client.get(P + "/tasks", headers=student).json() == []
    own_subject = subject(client, student)
    response = client.post(
        P + "/tasks", headers=student, json={"title": "Revision", "subject_id": own_subject}
    )
    assert response.status_code == 201
    task_id = response.json()["id"]
    assert client.patch(P + f"/tasks/{task_id}", headers=student, json=payload).status_code == 404
    assert client.get(P + "/tasks", headers=student).json()[0]["subject_id"] == own_subject


def test_tasks_allow_owned_subject_and_no_subject(client, student):
    sid = subject(client, student)
    response = client.post(P + "/tasks", headers=student, json={"title": "Read", "subject_id": sid})
    assert response.status_code == 201
    response = client.patch(
        P + f"/tasks/{response.json()['id']}",
        headers=student,
        json={"title": "Read", "subject_id": None},
    )
    assert response.status_code == 200
    assert response.json()["subject_id"] is None
