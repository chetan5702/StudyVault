"""Exam and delivery behavior against the real API/database with a controlled clock."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app import reminders
from app.api.v1 import exams, notifications
from app.config import get_settings
from app.database import SessionLocal
from app.email_delivery import ResendProvider
from app.models import Exam, Notification, Reminder, ReminderPreference
from tests.test_workflow import P, second, subject

NOW = datetime(2030, 1, 10, 12, tzinfo=UTC)
OFFSETS = [10080, 4320, 1440, 60]


class TestEmailProvider:
    __test__ = False

    def __init__(self, failures=0, retryable=True):
        self.failures = failures
        self.retryable = retryable
        self.calls = []
        self.deliveries = {}

    def send(self, *, recipient, subject, body, idempotency_key):
        self.calls.append((recipient, subject, body, idempotency_key))
        if len(self.calls) <= self.failures:
            raise reminders.DeliveryError("Test provider unavailable", retryable=self.retryable)
        self.deliveries.setdefault(idempotency_key, (recipient, subject, body))
        return "test-delivery-" + idempotency_key


@pytest.fixture(autouse=True)
def fake_reminder_clock(monkeypatch):
    monkeypatch.setattr(reminders, "utcnow", lambda: NOW)
    monkeypatch.setattr(exams, "utcnow", lambda: NOW)
    monkeypatch.setattr(notifications, "utcnow", lambda: NOW)


def create_exam(client, student, *, scheduled_for=None, subject_id=None, **values):
    response = client.post(
        P + "/exams",
        headers=student,
        json={
            "subject_id": subject_id or subject(client, student),
            "title": "Algorithms final",
            "scheduled_for": (scheduled_for or (NOW + timedelta(days=10))).isoformat(),
            **values,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def preference(client, student, **values):
    response = client.put(
        P + "/notification-preferences",
        headers=student,
        json={
            "in_app_enabled": True,
            "email_enabled": False,
            "reminder_minutes": OFFSETS,
            "timezone": "Asia/Kolkata",
            **values,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def exam_reminders(exam_id):
    with SessionLocal() as db:
        return db.query(Reminder).filter_by(exam_id=exam_id).order_by(Reminder.notify_at).all()


def use_test_email(client, student):
    """Enable email in the DB so fake-provider tests require no network configuration."""
    preference(client, student, in_app_enabled=False, reminder_minutes=[60])
    user_id = client.get(P + "/auth/me", headers=student).json()["id"]
    with SessionLocal() as db:
        row = db.query(ReminderPreference).filter_by(user_id=user_id).one()
        row.email_enabled = True
        db.commit()


def test_create_and_edit_exam_information(client, student):
    exam = create_exam(client, student, location="Room 12", timezone="Asia/Kolkata")
    other_subject = subject(client, student, "CS102")
    response = client.patch(
        P + f"/exams/{exam['id']}",
        headers=student,
        json={
            "title": "Revised final",
            "subject_id": other_subject,
            "exam_type": "final",
            "location": "Room 20",
        },
    )
    assert response.status_code == 200, response.text
    changed = response.json()
    assert changed["title"] == "Revised final"
    assert changed["subject_id"] == other_subject
    assert changed["exam_type"] == "final"
    assert changed["location"] == "Room 20"
    assert changed["timezone"] == "Asia/Kolkata"
    assert datetime.fromisoformat(changed["scheduled_for"]) == NOW + timedelta(days=10)
    assert client.get(P + "/exams", headers=student).json()[0] == changed


def test_create_rejects_legacy_per_exam_reminder_minutes(client, student):
    response = client.post(
        P + "/exams",
        headers=student,
        json={
            "subject_id": subject(client, student),
            "title": "Algorithms final",
            "scheduled_for": (NOW + timedelta(days=10)).isoformat(),
            "reminder_minutes": 120,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "reminder_minutes"
    assert client.get(P + "/exams", headers=student).json() == []


def test_update_rejects_legacy_per_exam_reminder_minutes_without_changing_schedule(client, student):
    preference(client, student)
    exam = create_exam(client, student)
    original = [
        (row.id, row.offset_minutes, row.notify_at, row.delivery_status)
        for row in exam_reminders(exam["id"])
    ]

    response = client.patch(
        P + f"/exams/{exam['id']}", headers=student, json={"reminder_minutes": 120}
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "reminder_minutes"
    assert [
        (row.id, row.offset_minutes, row.notify_at, row.delivery_status)
        for row in exam_reminders(exam["id"])
    ] == original


@pytest.mark.parametrize(
    "local,zone,expected",
    [
        ("2030-01-20T09:30:00+05:30", "Asia/Kolkata", "2030-01-20T04:00:00+00:00"),
        ("2030-07-20T09:30:00-04:00", "America/New_York", "2030-07-20T13:30:00+00:00"),
        ("2030-11-03T01:30:00-04:00", "America/New_York", "2030-11-03T05:30:00+00:00"),
        ("2030-11-03T01:30:00-05:00", "America/New_York", "2030-11-03T06:30:00+00:00"),
    ],
)
def test_timezone_conversion_preserves_instant_and_dst_fold(client, student, local, zone, expected):
    exam = create_exam(client, student, scheduled_for=datetime.fromisoformat(local), timezone=zone)
    assert datetime.fromisoformat(exam["scheduled_for"]) == datetime.fromisoformat(expected)
    assert exam["timezone"] == zone
    with SessionLocal() as db:
        stored = db.get(Exam, exam["id"])
        assert stored.scheduled_for == datetime.fromisoformat(expected)
        assert stored.scheduled_for.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "changes", [{"scheduled_for": "2030-02-01T09:30:00"}, {"timezone": "Invalid/Timezone"}]
)
def test_exam_edit_rejects_invalid_time(client, student, changes):
    exam = create_exam(client, student)
    response = client.patch(P + f"/exams/{exam['id']}", headers=student, json=changes)
    assert response.status_code == 422
    assert (
        client.get(P + "/exams", headers=student).json()[0]["scheduled_for"]
        == exam["scheduled_for"]
    )


def test_reschedule_cancels_old_schedule_and_generates_new_reminders(client, student):
    preference(client, student)
    exam = create_exam(client, student)
    old = exam_reminders(exam["id"])
    assert len(old) == 4
    new_date = NOW + timedelta(days=15, hours=2)
    response = client.patch(
        P + f"/exams/{exam['id']}",
        headers=student,
        json={"scheduled_for": new_date.isoformat()},
    )
    assert response.status_code == 200, response.text
    rows = exam_reminders(exam["id"])
    old_ids = {r.id for r in old}
    assert all(r.delivery_status == "cancelled" for r in rows if r.id in old_ids)
    pending = [r for r in rows if r.delivery_status == "pending"]
    assert len(pending) == 4
    assert {r.notify_at for r in pending} == {
        new_date - timedelta(minutes=offset) for offset in OFFSETS
    }
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(days=3))
    assert client.get(P + "/notifications", headers=student).json()["items"] == []


def test_exam_lists_filter_by_subject_and_completion(client, student):
    today = NOW
    first_subject = subject(client, student)
    next_subject = subject(client, student, "CS102")
    past = create_exam(
        client, student, scheduled_for=today - timedelta(days=2), subject_id=first_subject
    )
    future = create_exam(
        client, student, scheduled_for=today + timedelta(days=2), subject_id=first_subject
    )
    another = create_exam(
        client, student, scheduled_for=today + timedelta(days=3), subject_id=next_subject
    )
    response = client.get(P + "/exams", headers=student, params={"status": "upcoming"})
    assert {r["id"] for r in response.json()} == {future["id"], another["id"]}
    response = client.get(P + "/exams", headers=student, params={"status": "completed"})
    assert [r["id"] for r in response.json()] == [past["id"]]
    response = client.get(
        P + "/exams", headers=student, params={"status": "upcoming", "subject_id": first_subject}
    )
    assert [r["id"] for r in response.json()] == [future["id"]]


def test_exam_edit_delete_and_subject_associations_are_private(client, student):
    exam = create_exam(client, student)
    other = second(client)
    other_subject = subject(client, other)
    assert client.get(P + "/exams", headers=other).json() == []
    assert (
        client.patch(
            P + f"/exams/{exam['id']}", headers=other, json={"title": "Stolen"}
        ).status_code
        == 404
    )
    assert client.delete(P + f"/exams/{exam['id']}", headers=other).status_code == 404
    assert (
        client.patch(
            P + f"/exams/{exam['id']}", headers=student, json={"subject_id": other_subject}
        ).status_code
        == 404
    )
    assert client.get(P + "/exams", headers=student).json()[0]["title"] == "Algorithms final"


def test_generates_preferred_offsets_once_for_correct_recipient(client, student):
    preference(client, student)
    exam = create_exam(client, student)
    user_id = client.get(P + "/auth/me", headers=student).json()["id"]
    with SessionLocal() as db:
        reminders.generate_reminders(db, db.get(Exam, exam["id"]), now=NOW)
        db.commit()
    rows = [r for r in exam_reminders(exam["id"]) if r.delivery_status == "pending"]
    assert len(rows) == 4
    assert {r.offset_minutes for r in rows} == set(OFFSETS)
    assert {r.user_id for r in rows} == {user_id}
    assert {r.channel for r in rows} == {"in_app"}
    assert {r.delivery_status for r in rows} == {"pending"}
    assert {r.notify_at for r in rows} == {
        NOW + timedelta(days=10) - timedelta(minutes=offset) for offset in OFFSETS
    }


def test_late_created_exam_gets_one_immediate_catchup(client, student):
    preference(client, student)
    exam = create_exam(client, student, scheduled_for=NOW + timedelta(minutes=30))
    rows = exam_reminders(exam["id"])
    assert len(rows) == 1
    assert rows[0].notify_at == NOW
    assert rows[0].offset_minutes == 60
    reminders.run_due_reminders(SessionLocal, now=NOW)
    assert len(client.get(P + "/notifications", headers=student).json()["items"]) == 1


def test_due_in_app_reminder_delivered_once_with_unread_count(client, student):
    preference(client, student)
    exam = create_exam(client, student)
    due = NOW + timedelta(days=3)
    reminders.run_due_reminders(SessionLocal, now=due - timedelta(microseconds=1))
    assert client.get(P + "/notifications", headers=student).json()["unread_count"] == 0
    reminders.run_due_reminders(SessionLocal, now=due)
    reminders.run_due_reminders(SessionLocal, now=due)
    result = client.get(P + "/notifications", headers=student).json()
    assert result["unread_count"] == 1
    assert len(result["items"]) == 1
    notification = result["items"][0]
    assert notification["exam_id"] == exam["id"]
    assert "Algorithms final" in notification["title"] + notification["message"]
    assert datetime.fromisoformat(notification["delivered_at"]) == due
    delivered = [r for r in exam_reminders(exam["id"]) if r.delivery_status == "sent"]
    assert len(delivered) == 1
    assert delivered[0].delivery_attempts == 1


def test_two_workers_do_not_duplicate_in_app_delivery(client, student):
    preference(client, student, reminder_minutes=[60])
    exam = create_exam(client, student, scheduled_for=NOW + timedelta(hours=1))
    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = [
            executor.submit(reminders.run_due_reminders, SessionLocal, now=NOW) for _ in range(2)
        ]
        for job in jobs:
            job.result(timeout=15)
    with SessionLocal() as db:
        assert db.query(Notification).filter_by(exam_id=exam["id"]).count() == 1
    assert exam_reminders(exam["id"])[0].delivery_attempts == 1


def test_editing_exam_updates_pending_notification_contents(client, student):
    preference(client, student, reminder_minutes=[60])
    exam = create_exam(client, student, scheduled_for=NOW + timedelta(hours=2))
    initial_ids = {row.id for row in exam_reminders(exam["id"])}
    response = client.patch(
        P + f"/exams/{exam['id']}",
        headers=student,
        json={"title": "Updated exam title", "location": "New lecture hall"},
    )
    assert response.status_code == 200
    assert {row.id for row in exam_reminders(exam["id"])} == initial_ids
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(hours=1))
    notice = client.get(P + "/notifications", headers=student).json()["items"][0]
    assert "Updated exam title" in notice["title"] + notice["message"]
    assert "New lecture hall" in notice["message"]


def test_preferences_toggle_does_not_redeliver_already_sent_reminder(client, student):
    preference(client, student, reminder_minutes=[60])
    exam = create_exam(client, student, scheduled_for=NOW + timedelta(hours=1))
    reminders.run_due_reminders(SessionLocal, now=NOW)
    preference(client, student, in_app_enabled=False, reminder_minutes=[60])
    preference(client, student, in_app_enabled=True, reminder_minutes=[60])
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(minutes=1))
    notices = client.get(P + "/notifications", headers=student).json()["items"]
    assert len(notices) == 1
    assert notices[0]["exam_id"] == exam["id"]


def test_email_delivery_reuses_idempotency_key_after_transient_failure(client, student):
    use_test_email(client, student)
    exam = create_exam(client, student, scheduled_for=NOW + timedelta(hours=1))
    provider = TestEmailProvider(failures=1)
    reminders.run_due_reminders(SessionLocal, now=NOW, provider=provider)
    first = exam_reminders(exam["id"])[0]
    assert first.delivery_attempts == 1
    assert first.next_attempt_at == NOW + timedelta(seconds=60)
    assert first.delivery_status in {"retry", "pending"}
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(seconds=59), provider=provider)
    assert len(provider.calls) == 1
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(seconds=60), provider=provider)
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(seconds=61), provider=provider)
    assert len(provider.calls) == 2
    assert provider.calls[0][0] == "one@example.com"
    assert provider.calls[0][3] == provider.calls[1][3]
    assert len(provider.deliveries) == 1
    assert "Algorithms final" in provider.calls[1][1] + provider.calls[1][2]
    assert exam_reminders(exam["id"])[0].delivery_status == "sent"


def test_worker_recovers_crashed_email_claim_without_duplicate_delivery(client, student):
    use_test_email(client, student)
    exam = create_exam(client, student, scheduled_for=NOW + timedelta(hours=1))

    class WorkerCrash(BaseException):
        pass

    class CrashAfterAcceptance(TestEmailProvider):
        def send(self, **kwargs):
            result = super().send(**kwargs)
            if len(self.calls) == 1:
                raise WorkerCrash("Worker exited after provider accepted email")
            return result

    provider = CrashAfterAcceptance()
    with pytest.raises(WorkerCrash):
        reminders.run_due_reminders(SessionLocal, now=NOW, provider=provider)
    claimed = exam_reminders(exam["id"])[0]
    assert claimed.delivery_status == "processing"
    assert claimed.delivery_attempts == 1
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(seconds=119), provider=provider)
    assert len(provider.calls) == 1
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(minutes=2), provider=provider)
    assert len(provider.calls) == 2
    assert len(provider.deliveries) == 1
    assert provider.calls[0][3] == provider.calls[1][3]
    assert exam_reminders(exam["id"])[0].delivery_status == "sent"


def test_worker_does_not_retry_email_outside_provider_idempotency_window(client, student):
    use_test_email(client, student)
    exam = create_exam(client, student, scheduled_for=NOW + timedelta(hours=1))
    provider = TestEmailProvider()
    with SessionLocal() as db:
        reminder = db.query(Reminder).filter_by(exam_id=exam["id"]).one()
        reminder.first_attempt_at = NOW - timedelta(hours=23)
        reminder.delivery_attempts = 1
        reminder.delivery_status = "retry"
        reminder.next_attempt_at = NOW
        db.commit()
    reminders.run_due_reminders(SessionLocal, now=NOW, provider=provider)
    assert provider.calls == []
    assert exam_reminders(exam["id"])[0].delivery_status == "failed"


def test_configured_development_email_sink_receives_message_once(
    client, student, monkeypatch, tmp_path
):
    settings = get_settings()
    monkeypatch.setattr(settings, "email_provider", "file")
    monkeypatch.setattr(settings, "email_sink_dir", str(tmp_path / "email-sink"))
    saved = preference(
        client, student, email_enabled=True, in_app_enabled=False, reminder_minutes=[60]
    )
    assert saved["email_available"] is True
    exam = create_exam(client, student, scheduled_for=NOW + timedelta(hours=1), location="Room 22")
    reminders.run_due_reminders(SessionLocal, now=NOW)
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(seconds=1))
    files = list((tmp_path / "email-sink").glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["to"] == "one@example.com"
    assert "Algorithms final" in payload["subject"]
    assert "Room 22" in payload["text"]
    assert payload["idempotency_key"] == "studyvault-reminder-" + exam_reminders(exam["id"])[0].id


def test_resend_adapter_passes_idempotency_key_and_bounded_timeout(monkeypatch):
    requests = []

    def post(url, **kwargs):
        requests.append((url, kwargs))
        return httpx.Response(200, json={"id": "provider-message-id"})

    monkeypatch.setattr(httpx, "post", post)
    result = ResendProvider("test-api-key", "StudyVault <study@example.com>").send(
        recipient="one@example.com",
        subject="Exam tomorrow",
        body="Study plan",
        idempotency_key="unique-key",
    )
    assert result == "provider-message-id"
    assert requests[0][0] == "https://api.resend.com/emails"
    assert requests[0][1]["headers"]["Idempotency-Key"] == "unique-key"
    assert requests[0][1]["json"]["to"] == ["one@example.com"]
    assert requests[0][1]["timeout"] <= 10


@pytest.mark.parametrize("status,retryable", [(429, True), (503, True), (400, False), (403, False)])
def test_resend_adapter_distinguishes_retryable_failures(monkeypatch, status, retryable):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(status))
    with pytest.raises(reminders.DeliveryError) as error:
        ResendProvider("test-api-key", "study@example.com").send(
            recipient="one@example.com", subject="Exam", body="Text", idempotency_key="key"
        )
    assert error.value.retryable is retryable


def test_permanent_email_failure_is_not_retried(client, student):
    use_test_email(client, student)
    exam = create_exam(client, student, scheduled_for=NOW + timedelta(hours=1))
    provider = TestEmailProvider(failures=100, retryable=False)
    reminders.run_due_reminders(SessionLocal, now=NOW, provider=provider)
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(minutes=10), provider=provider)
    row = exam_reminders(exam["id"])[0]
    assert row.delivery_status == "failed"
    assert row.delivery_attempts == 1
    assert row.last_error
    assert len(provider.calls) == 1


def test_deletion_cancels_email_retry(client, student):
    use_test_email(client, student)
    exam = create_exam(client, student, scheduled_for=NOW + timedelta(hours=1))
    provider = TestEmailProvider(failures=1)
    reminders.run_due_reminders(SessionLocal, now=NOW, provider=provider)
    assert len(provider.calls) == 1
    assert client.delete(P + f"/exams/{exam['id']}", headers=student).status_code in {200, 204}
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(minutes=5), provider=provider)
    assert len(provider.calls) == 1
    assert exam_reminders(exam["id"])[0].delivery_status == "cancelled"


def test_worker_does_not_deliver_reminders_after_exam_start(client, student):
    preference(client, student, reminder_minutes=[60])
    exam = create_exam(client, student, scheduled_for=NOW + timedelta(hours=1))
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(hours=2))
    assert client.get(P + "/notifications", headers=student).json()["items"] == []
    assert exam_reminders(exam["id"])[0].delivery_status == "cancelled"


def test_transient_failures_stop_after_five_attempts(client, student):
    use_test_email(client, student)
    exam = create_exam(client, student, scheduled_for=NOW + timedelta(hours=1))
    provider = TestEmailProvider(failures=100)
    for seconds in [0, 60, 180, 420, 900, 1800]:
        reminders.run_due_reminders(
            SessionLocal, now=NOW + timedelta(seconds=seconds), provider=provider
        )
    row = exam_reminders(exam["id"])[0]
    assert row.delivery_status == "failed"
    assert row.delivery_attempts == 5
    assert len(provider.calls) == 5
    assert len({call[3] for call in provider.calls}) == 1
    assert provider.deliveries == {}


def test_delete_exam_cancels_pending_reminders(client, student):
    preference(client, student)
    exam = create_exam(client, student)
    response = client.delete(P + f"/exams/{exam['id']}", headers=student)
    assert response.status_code in {200, 204}
    rows = exam_reminders(exam["id"])
    assert len(rows) == 4
    assert all(r.delivery_status == "cancelled" for r in rows)
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(days=9))
    assert client.get(P + "/exams", headers=student).json() == []
    assert client.get(P + "/notifications", headers=student).json()["items"] == []
    assert (
        client.patch(
            P + f"/exams/{exam['id']}", headers=student, json={"title": "Revive"}
        ).status_code
        == 404
    )


def test_notification_privacy_mark_read_and_mark_all(client, student):
    preference(client, student, reminder_minutes=[60])
    create_exam(client, student, scheduled_for=NOW + timedelta(hours=1))
    other = second(client)
    preference(client, other, reminder_minutes=[60])
    create_exam(client, other, scheduled_for=NOW + timedelta(hours=1))
    reminders.run_due_reminders(SessionLocal, now=NOW)
    first = client.get(P + "/notifications", headers=student).json()
    second_notifications = client.get(P + "/notifications", headers=other).json()
    assert first["unread_count"] == second_notifications["unread_count"] == 1
    assert len(first["items"]) == len(second_notifications["items"]) == 1
    notification_id = first["items"][0]["id"]
    assert notification_id != second_notifications["items"][0]["id"]
    assert (
        client.patch(P + f"/notifications/{notification_id}/read", headers=other).status_code == 404
    )
    assert client.get(P + "/notifications", headers=student).json()["unread_count"] == 1
    assert (
        client.patch(P + f"/notifications/{notification_id}/read", headers=student).status_code
        == 200
    )
    read = client.get(P + "/notifications", headers=student).json()
    assert read["unread_count"] == 0
    assert read["items"][0]["read_at"] is not None
    assert client.post(P + "/notifications/read-all", headers=student).status_code == 200
    assert client.get(P + "/notifications", headers=other).json()["unread_count"] == 1
    assert client.post(P + "/notifications/read-all", headers=other).status_code == 200
    assert client.get(P + "/notifications", headers=other).json()["unread_count"] == 0


def test_preferences_persist_and_cancel_disabled_channel(client, student):
    saved = preference(client, student, reminder_minutes=[1440, 60])
    assert saved["timezone"] == "Asia/Kolkata"
    assert set(saved["reminder_minutes"]) == {1440, 60}
    assert client.get(P + "/notification-preferences", headers=student).json() == saved
    exam = create_exam(client, student)
    assert len(exam_reminders(exam["id"])) == 2
    preference(client, student, in_app_enabled=False, reminder_minutes=[1440, 60])
    assert all(r.delivery_status == "cancelled" for r in exam_reminders(exam["id"]))
    reminders.run_due_reminders(SessionLocal, now=NOW + timedelta(days=9))
    assert client.get(P + "/notifications", headers=student).json()["items"] == []


@pytest.mark.parametrize("changes", [{"reminder_minutes": [5]}, {"timezone": "No/Such_Zone"}])
def test_preferences_reject_unsupported_values(client, student, changes):
    response = client.put(
        P + "/notification-preferences",
        headers=student,
        json={
            "in_app_enabled": True,
            "email_enabled": False,
            "reminder_minutes": [60],
            "timezone": "UTC",
            **changes,
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("endpoint", ["/notifications", "/notification-preferences"])
def test_notifications_and_preferences_require_authentication(client, endpoint):
    assert client.get(P + endpoint).status_code == 401
