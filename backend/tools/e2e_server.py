"""Disposable backend for browser tests; never opens studyvault.db."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.chdir(root)
sys.path.insert(0, str(root))
with tempfile.TemporaryDirectory(prefix="studyvault-browser-", ignore_cleanup_errors=True) as temp:
    os.environ.update(
        ENVIRONMENT="test",
        SEED_DEMO="false",
        # All browser specs originate from one disposable localhost IP. Give
        # the test harness ample headroom without weakening production limits.
        REGISTER_PER_HOUR="1000",
        LOGIN_PER_HOUR="1000",
        RECOVERY_PER_HOUR="1000",
        STUDYVAULT_DEBUG="false",
        DATABASE_URL="sqlite:///" + (Path(temp) / "browser.db").as_posix(),
        UPLOAD_DIR=str(Path(temp) / "uploads"),
        SECRET_KEY="isolated-browser-test-secret-not-for-deployment",
        CORS_ORIGINS="http://127.0.0.1:5174",
        EMAIL_PROVIDER="file",
        EMAIL_FROM="StudyVault <reminders@example.test>",
        EMAIL_SINK_DIR=str(Path(temp) / "email-outbox"),
    )
    from alembic.config import Config

    from alembic import command

    command.upgrade(Config("alembic.ini"), "head")
    import uvicorn
    from fastapi import HTTPException
    from pydantic import AwareDatetime, BaseModel

    from app.main import app

    class WorkerRequest(BaseModel):
        now: AwareDatetime

    # Test-only privileged setup routes exist ONLY in this disposable browser
    # harness, never in app.main or in a real StudyVault deployment. All
    # accounts and enrollments provisioned here are synthetic.
    from typing import Literal
    from fastapi import status
    from app.database import SessionLocal
    from app.models import Course, StaffRole, User, VerifiedEnrollment

    class FictionalRole(BaseModel):
        user_id: str
        role: Literal["admin", "faculty"]

    class FictionalEnrollment(BaseModel):
        user_id: str
        course_id: str
        semester: int
        academic_session: str

    @app.post("/__test__/fixtures/staff-role", status_code=status.HTTP_204_NO_CONTENT)
    def grant_fictional_staff_role(payload: FictionalRole):
        with SessionLocal() as db:
            user = db.get(User, payload.user_id)
            if user is None or user.email_verified_at is None:
                raise HTTPException(404, "Fictional user not available")
            if db.get(StaffRole, user.id) is not None:
                raise HTTPException(409, "Fictional role exists")
            db.add(StaffRole(user_id=user.id, role=payload.role))
            db.commit()

    @app.post("/__test__/fixtures/enrollment", status_code=status.HTTP_204_NO_CONTENT)
    def provision_fictional_enrollment(payload: FictionalEnrollment):
        with SessionLocal() as db:
            if db.get(User, payload.user_id) is None or db.get(Course, payload.course_id) is None:
                raise HTTPException(404, "Fictional student or program missing")
            if db.get(VerifiedEnrollment, payload.user_id) is not None:
                raise HTTPException(409, "Fictional enrollment exists")
            db.add(VerifiedEnrollment(
                user_id=payload.user_id, course_id=payload.course_id,
                semester=payload.semester, academic_session=payload.academic_session,
                verification_source="development",
            ))
            db.commit()

    # This test-only route is registered solely by this disposable harness.
    # It launches the actual worker executable; production app has no clock override route.
    @app.post("/__test__/reminders/run")
    def run_worker(payload: WorkerRequest):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.reminder_worker",
                "--once",
                "--now",
                payload.now.isoformat(),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode:
            raise HTTPException(status_code=500, detail=result.stderr + result.stdout)
        return {"worker_output": result.stdout}

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8011))

    @app.post("/__test__/shutdown")
    def shutdown_server():
        # The browser harness calls this after the suite so Windows can release
        # SQLite and upload handles without relying on process-tree termination.
        server.should_exit = True
        return {"status": "stopping"}

    server.run()
    from app.database import engine

    engine.dispose()
