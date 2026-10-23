from tests.test_workflow import P, second, subject, upload


def create_unit(client, headers, subject_id, name="Introduction", order_index=1):
    response = client.post(
        P + f"/subjects/{subject_id}/units",
        headers=headers,
        json={"subject_id": subject_id, "name": name, "order_index": order_index},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_owner_can_update_and_delete_an_empty_unit(client, student):
    subject_id = subject(client, student)
    unit = create_unit(client, student, subject_id)

    updated = client.patch(
        P + f"/subjects/{subject_id}/units/{unit['id']}",
        headers=student,
        json={"name": "Foundations", "order_index": 2},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Foundations"
    assert updated.json()["order_index"] == 2

    deleted = client.delete(P + f"/subjects/{subject_id}/units/{unit['id']}", headers=student)
    assert deleted.status_code == 204, deleted.text
    assert deleted.content == b""
    assert client.get(P + f"/subjects/{subject_id}/units", headers=student).json() == []


def test_unit_mutations_are_owner_scoped(client, student):
    subject_id = subject(client, student)
    unit = create_unit(client, student, subject_id)
    other = second(client)

    assert (
        client.patch(
            P + f"/subjects/{subject_id}/units/{unit['id']}",
            headers=other,
            json={"name": "Taken over"},
        ).status_code
        == 404
    )
    assert (
        client.delete(P + f"/subjects/{subject_id}/units/{unit['id']}", headers=other).status_code
        == 404
    )


def test_unit_with_material_cannot_be_deleted(client, student, pdf):
    subject_id = subject(client, student)
    unit = create_unit(client, student, subject_id)
    material = upload(client, student, subject_id, pdf, unit_id=unit["id"])
    assert material.status_code == 201, material.text

    response = client.delete(P + f"/subjects/{subject_id}/units/{unit['id']}", headers=student)

    assert response.status_code == 409, response.text
    assert "material" in response.json()["detail"].lower()
    assert (
        client.get(P + f"/materials/{material.json()['id']}/download", headers=student).content
        == pdf
    )


def test_material_filters_can_be_combined(client, student, pdf):
    first_subject = subject(client, student)
    second_subject = subject(client, student, "CS102")
    first = upload(
        client,
        student,
        first_subject,
        pdf,
        title="Algorithms guide",
        category="notes",
    )
    second_material = upload(
        client,
        student,
        second_subject,
        pdf,
        title="Algorithms assignment",
        category="assignment",
    )
    assert first.status_code == 201, first.text
    assert second_material.status_code == 201, second_material.text

    response = client.get(
        P + "/materials",
        headers=student,
        params={"subject_id": second_subject, "search": "Algorithms", "category": "assignment"},
    )

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [second_material.json()["id"]]
