# StudyVault

> **Production hardening edition:** For the Docker/PostgreSQL/HTTPS deployment candidate, read [Production deployment and operations](docs/PRODUCTION_DEPLOYMENT.md). Run `scripts/check-release.py` before deployment. Local development instructions below are unchanged. A deployment candidate is not proof of a production-tested service.

A React, TypeScript and Tailwind workspace connected to FastAPI: accounts, academic profiles, subjects, units, private materials, exam management, a calendar and scheduled reminders. SQLite is the convenient local default. PostgreSQL is supported through SQLAlchemy and psycopg. No AI, chat or advanced collaboration UI is included.

## Requirements

Windows PowerShell, Python 3.12 or later, Node.js 22.12 or later, and npm. Local development uses the backend, frontend and a separate reminder worker; no external auth, cloud storage, email or PostgreSQL service is required. Browser tests use installed Microsoft Edge.

## Start the backend

Run from the repository root. Installation commands need internet access.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if (-not (Test-Path backend\.env)) {
    Copy-Item .env.example backend\.env
    $studyvaultSecret = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
    (Get-Content backend\.env).Replace('SECRET_KEY=', "SECRET_KEY=$studyvaultSecret") | Set-Content backend\.env
}
Set-Location backend
..\.venv\Scripts\python.exe -m tools.init_db
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The initialization command runs Alembic for a fresh database. For an original database created by `create_all`, it checks the schema against the original revision before stamping it, then applies later migrations. It refuses incompatible schemas. Back up the database and uploads before schema changes. Application startup never creates tables. For subsequent changes run `..\.venv\Scripts\python.exe -m alembic upgrade head` from `backend`. For the local SQLite database, `..\.venv\Scripts\python.exe -m tools.verify_preservation` first verifies the migration on a backup copy, then upgrades the main database and compares every original column and row. It retains `studyvault.pre-reminders.backup`.

## Start the frontend

Open a second PowerShell terminal in the repository root:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Open http://127.0.0.1:5173. Vite proxies `/api` to FastAPI. API documentation is at http://127.0.0.1:8000/docs. Register your own account; no demo account is created by default. Local registration signs you in and opens academic onboarding. Sreenidhi University is available in the college catalog. Create a subject, open it to add units, upload a PDF in Materials, download it, and schedule an exam. Subjects and units can be renamed or deleted; a unit with linked materials returns HTTP 409 until those materials are deleted or reassigned. Subject deletion is also blocked by materials, study tasks and active exams. After an exam is deleted, its archived row no longer blocks subject deletion: the exam keeps immutable subject name/code snapshots, its subject link is cleared, and its reminder and notification history remains intact. Owners can delete materials, search them, filter by category or subject, and open the filtered library from a subject. The dashboard prioritizes up to four upcoming deadlines, recent materials and quick actions, followed by compact persisted totals. The material library shows distinct PDF, image and Word indicators based on the MIME type verified by the backend.

## Exam management and notifications

Exams supports creation, editing, rescheduling and a confirmation dialog before deletion. Switch between the list and monthly calendar, filter by subject, and select Upcoming, Completed or All exams. Completed means the scheduled instant has passed. Countdown cards update while the page is open. Deleted exams disappear from the schedule and dashboard; their database rows, reminders, delivered notifications and frozen subject context are retained for history. Migration `0006_archived_exam_subjects` makes the subject link nullable so deleting the former subject does not break those relationships. A database check constraint permits a missing subject only on an archived exam, so active exams cannot become orphaned.

Downgrading below `0006_archived_exam_subjects` requires restoring deleted subjects or removing archived exams whose subject link has already been cleared.

The form and calendar use the browser's local timezone, displayed beside the controls. API timestamps require an explicit offset and are stored in UTC. Nonexistent local times during a daylight-saving transition are rejected; repeated times require selecting the first or second occurrence. Editing preserves the original instant. Reminder settings separately controls the timezone used in notification messages.

The dashboard header bell opens the private notification center. Its badge counts unread delivered in-app reminders; the center supports individual and bulk read actions and refreshes every 30 seconds while signed in. Reminder settings applies to all upcoming exams and offers 7 days, 3 days, 1 day and 1 hour before an examination. Exam create and update payloads do not accept a separate per-exam `reminder_minutes` value; use reminder settings so the interface and API share one schedule. In-app reminders are enabled by default, email is opt-in. Past thresholds are skipped when scheduling; if every selected threshold has passed but the exam is still upcoming, one immediate reminder is queued. Rescheduling replaces pending deliveries; deletion cancels them. Already delivered history remains available.

## Run the independent reminder worker

Start a third PowerShell terminal, from the repository root:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m app.reminder_worker --interval 30
```

This is a separate process with its own database connections, independent of FastAPI startup and requests. It scans persisted due reminders every 30 seconds, prints delivery/retry/failure/cancellation counts as JSON, and catches up after restarts. A one-shot scheduled-job entry point is also available:

```powershell
..\.venv\Scripts\python.exe -m app.reminder_worker --once
```

For recurring Windows delivery, run the supplied installer from the repository root:

```powershell
powershell.exe -NoProfile -File .\backend\tools\install_reminder_task.ps1
Get-ScheduledTaskInfo -TaskName 'StudyVault Exam Reminders'
```

The installer registers a Task Scheduler job every minute, with the correct Python executable and backend working directory, under the current Windows user. It runs while that user is signed in; keep the computer awake for timely delivery. It refuses to overwrite an existing task. This registration is an explicit local setup step, and is not performed by application startup. To remove it, run `Unregister-ScheduledTask -TaskName 'StudyVault Exam Reminders'`. See Microsoft's [scheduled trigger documentation](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasktrigger?view=windowsserver2025-ps).

On a Linux server, use a process supervisor for the continuous worker or an every-minute cron entry with absolute paths:

```cron
* * * * * cd /srv/studyvault/backend && /srv/studyvault/.venv/bin/python -m app.reminder_worker --once >> /var/log/studyvault-reminders.log 2>&1
```

Web and worker processes must use the same persistent database and configuration. Monitor job exit codes and the JSON counts; `failed` reminder rows retain attempt counts and a sanitized error. A stopped worker cannot deliver reminders. Overdue pending reminders are delivered when it returns if the exam is still upcoming; reminders for an exam that has already started are cancelled.

Delivery uses a database coordination row, persistent claims and a two-minute crash-recovery lease. In-app notification creation and the sent marker commit atomically, with a unique reminder constraint. Retries use the original email idempotency key and frozen content. Transient errors retry after 1, 2, 4 and 8 minutes, up to five total attempts; permanent errors fail immediately. Email retries stop after 23 hours to stay inside [Resend's documented 24-hour idempotency window](https://resend.com/docs/dashboard/emails/idempotency-keys). The coordination lock is held during a bounded provider request to serialize delivery with completed rescheduling/deletion. This favors correctness at StudyVault's present scale; high-volume delivery would need finer-grained coordination.

## Email verification and password recovery

Local development defaults to `REQUIRE_EMAIL_VERIFICATION=false`, so registration returns a session immediately. Production configuration requires verified email delivery. A production registration stores the account as unverified, sends a single-use verification link and directs the browser to the check-email page. Verification links expire after `EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES`; resends are limited by `VERIFICATION_RESEND_COOLDOWN_SECONDS`.

The login page links to password recovery. Reset requests return the same generic response whether or not the address exists, and email delivery runs after that response so provider latency and failures do not disclose account existence. Reset links expire after `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`. Only token digests are stored. Consuming a reset token changes the password, increments the account's token version and invalidates JWTs issued before the reset.

For public use, set these values in `backend/.env` before starting the API or running the deployment check:

```dotenv
ENVIRONMENT=production
SECRET_KEY=a-randomly-generated-secret-of-at-least-32-characters
REQUIRE_EMAIL_VERIFICATION=true
PUBLIC_FRONTEND_URL=https://studyvault.example.com
CORS_ORIGINS=https://studyvault.example.com
EMAIL_PROVIDER=resend
RESEND_API_KEY=your-provider-key
EMAIL_FROM=StudyVault <accounts@your-verified-domain.example>
```

Production also requires a persistent `DATABASE_URL` and private persistent `UPLOAD_DIR`. Replace every example hostname and credential. `STUDYVAULT_DEBUG` and `SEED_DEMO` must remain false. The application rejects production startup when the secret is weak, email verification is disabled, Resend is incomplete, or the public frontend URL is not HTTPS.

## Optional reminder email configuration

The default `EMAIL_PROVIDER=disabled` needs no credentials in local development. The same Resend connection used for account messages can deliver optional exam reminders; restart web and worker processes after changing it:

```dotenv
EMAIL_PROVIDER=resend
RESEND_API_KEY=your-provider-key
EMAIL_FROM=StudyVault <reminders@your-verified-domain.example>
```

Students must also enable Email notifications in Reminder settings; messages go only to their own account email. Provider acceptance is recorded as sent; inbox arrival and bounce tracking are outside this implementation. Never commit a provider key.

For development, configure an inspectable local sink instead:

```dotenv
EMAIL_PROVIDER=file
EMAIL_SINK_DIR=./email-sink
```

The sink writes one atomic JSON file per delivery key, containing recipient, subject and text. It does not contact an email service or mailbox. It is used by automated integration tests to verify generated email content and deduplication. Live Resend delivery is only verified when a configured test account is available; see PROGRESS.md for what was actually exercised.

## Configuration and persistence

Configuration is read from `backend/.env` when started from `backend`, or environment variables. See [.env.example](.env.example). Production requires `ENVIRONMENT=production` and a randomly generated `SECRET_KEY` of at least 32 characters. It rejects weak defaults, demo seeding and debug mode. A missing development key generates an ephemeral random key: data persists, but tokens expire after restart; set a stable generated key to retain sessions. `STUDYVAULT_DEBUG` avoids the host's unrelated `DEBUG` variable.

`DATABASE_URL` and `UPLOAD_DIR` must point to persistent locations. Defaults place SQLite and uploads under `backend`; restarting preserves them. Never serve uploads as static files. Back up the database and files together. Use `postgresql+psycopg://user:password@host/database` for PostgreSQL; provision that service and run Alembic before startup. Production needs TLS, explicit CORS origins, private persistent storage, and a reverse proxy serving the frontend build with SPA fallback and forwarding `/api` to FastAPI. Alternatively set frontend `VITE_API_URL` before building and include the frontend origin in backend CORS. No production deployment is performed.

Login throttling is shared through the database, so it continues across web-process restarts. `LOGIN_MAX_FAILURES` controls failures allowed within `LOGIN_FAILURE_WINDOW_SECONDS`; subsequent attempts receive HTTP 429 and a `Retry-After` header for `LOGIN_LOCKOUT_SECONDS`. A successful login clears its failure record. Records contain only a hash of the normalized login identifier, never submitted passwords or tokens.

The frontend stores its bearer token in `sessionStorage`, validates it on reload and clears it on logout or a 401. It does not cache private records between accounts. Closing the tab ends the session. JWTs expire after `ACCESS_TOKEN_EXPIRE_MINUTES`; logout removes the browser token but does not revoke an already copied token server-side. A successful password reset invalidates previously issued JWTs for that account.

Materials accept parsed PDF, PNG, JPEG and DOCX contents with a default 20 MiB per-file limit. `MAX_USER_STORAGE_BYTES` sets the cumulative persisted-material quota for each owner (1 GiB by default). The authenticated material configuration response reports the per-file limit, quota, usage and remaining bytes. Quota reservations and material metadata commit together; a rejected upload returns HTTP 413 and removes its streamed file. Material deletion atomically claims the database row before releasing its recorded bytes, so simultaneous deletion requests can reduce the owner's usage only once. Migration `0004_security_limits` backfills existing owners from stored material sizes. The upload form reads `MAX_UPLOAD_SIZE_BYTES` from the backend and displays the configured limit. Encrypted/empty PDFs, malformed files, truncated images, unsupported archives and macro-enabled Word documents are rejected. Images are decoded and Word package namespaces/content types are validated. Multipart request reception is limited with an additional 64 KiB overhead allowance. Private files are owner-only; shared files require current group membership. Metadata never returns storage paths. Original in-root storage keys remain supported. Existing seeded placeholder materials never had corresponding files: their downloads return 404. Existing accounts and records are retained; review or deactivate pre-existing demo accounts before deployment. Demo seeding is an explicit development-only option and is not needed for this workflow.

## Backups and deployment checks

Stop the API and reminder worker before taking an operational backup so the database snapshot and copied uploads describe the same point in time. From the repository root, run:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m tools.backup --destination .\backups
```

For file-based SQLite, the command creates a timestamped ZIP containing a SQLite hot backup, private uploads and a manifest with the Alembic revision, sizes and SHA-256 hashes. Store copies outside the application host. The command does not support PostgreSQL; use `pg_dump` and copy `UPLOAD_DIR` during the same maintenance window. A backup is useful only after a documented restore drill. Backup restoration was not exercised in this milestone.

After configuring the target environment and backing it up, apply migrations and run the production preflight:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m tools.deployment_check
..\.venv\Scripts\python.exe -m tools.deployment_check --json
```

The preflight exits with a failure when production configuration, storage limits, public CORS, verified-email delivery, upload writability, database connectivity, migration head or SQLite foreign-key enforcement is incorrect. It validates configured local dependencies; it does not deploy the application or prove public DNS, TLS, reverse-proxy behavior, inbox delivery, restores or hosting health.

## Verification commands

From the repository root:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q --basetemp=.test-tmp-check
..\.venv\Scripts\python.exe -m ruff check app tests tools alembic
..\.venv\Scripts\python.exe -m ruff format --check app tests tools alembic
..\.venv\Scripts\python.exe -m pip check
..\.venv\Scripts\python.exe -m alembic check
Set-Location ..\frontend
npm.cmd run typecheck
npm.cmd run build
npm.cmd run lint
npm.cmd run test:e2e
```

`alembic check` needs an initialized database. The explicit pytest temporary directory avoids access conflicts with other Windows test sessions; use a fresh suffix if necessary. Automated tests use disposable SQLite databases and upload folders, never the main application database. Tests cover the original workflow and security checks, migration preservation, exam management, aware timestamps, concurrent duplicate material deletion, archived exam subject context, reminder generation, delivery, concurrent workers, privacy, retry/failure and cancellation. A fake clock avoids timing-dependent sleeps; fake providers and the local file sink avoid sending external mail.

Playwright starts its own backend on 8011 and Vite on 5174 with disposable data. Its test-only harness launches the real worker executable in a separate process with a controlled timestamp. That control route is absent from the production application; the CLI clock override also requires `ENVIRONMENT=test` and `--once`. Browser tests cover in-app delivery, bell counts, read status, rescheduling/deletion, calendar/mobile layout, DST gaps/repeated hours, long material names, distinct file indicators and crowded exam schedules. Leave the test ports free. If Edge is absent, install it or change the Playwright channel to an installed browser.

See [PROGRESS.md](PROGRESS.md) for actual results and verification limits.
