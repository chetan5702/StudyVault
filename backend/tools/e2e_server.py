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
