# Production hardening changes (October 23, 2026)

**Status: implementation candidate, not a verified public deployment.** See `docs/PRODUCTION_DEPLOYMENT.md`.

- New migration `0007_public_limits_and_membership` adds per-IP auth abuse counters and a unique `(group_id, user_id)` membership constraint; preexisting duplicate memberships are consolidated.
- Public registration, login, password recovery, and token-confirmation endpoints apply shared DB-backed limits.
- Production rejects disabled rate limiting or placeholder API signing secrets. New `/ready` endpoint checks PostgreSQL/SQLite connectivity and expected schema revision; `/health` remains liveness only. Production disables API docs and OpenAPI schema.
- Docker Compose single-host stack includes PostgreSQL, one-off migration, API, reminder worker, Nginx frontend, and HTTPS Caddy edge; only ports 80/443 are published. Uploads and database persist in Docker volumes.
- Production configuration preflight, database/upload maintenance-window backup, runbook, and targeted test coverage added. GitHub Actions CI and cross-platform browser-test Python detection were also added.
- Verification completed in review environment: source compilation, existing SQLite database migrated to 0007, Alembic autogenerate drift check, SQLite integrity, public API rate-limiting counter behavior, Compose YAML parsing, and shell syntax checks.
- **Not verified:** Docker image build/runtime (Docker unavailable), PostgreSQL integration, email delivery, HTTPS DNS/certificates, complete API test suite (JWT and bcrypt packages unavailable), frontend build/Playwright tests (npm dependencies unavailable). See pre-launch staging checklist.

---

# StudyVault milestone progress

Verified on 14 October 2026 (Asia/Calcutta).

## Delivered

- Replaced the Vite starter with a responsive StudyVault React/TypeScript/Tailwind application: registration, login, verified-account and password-recovery pages, protected routes, onboarding, dashboard, subjects, units, materials, exams, calendar, reminder settings and notifications. The interface now uses a single SVG icon system, distinct verified PDF/image/Word indicators, clearer type and form states, and consistent responsive buttons, hover feedback and loading feedback.
- Every implemented page uses FastAPI endpoints and presents useful empty states. The centralized API client handles authentication failures without allowing a delayed 401 from an earlier request to clear a newer session. Logout clears the browser session.
- Production configuration rejects missing or weak JWT secrets, disabled verified email, incomplete Resend configuration, non-HTTPS public URLs, debug mode and demo seeding. Demo creation is opt-in and development-only. Removed passlib; bcrypt is used directly. JWT expiry is required, and expired tokens and inactive accounts are rejected. Concurrent duplicate registration is handled transactionally. Verification and reset tokens are single-use digests; password reset invalidates prior JWTs. Recovery and resend delivery runs after the generic response so provider latency and failures do not disclose whether an account exists.
- Alembic owns schema initialization. Startup no longer creates tables. Legacy schema adoption is validated, including an empty Alembic version table. Code head `0006_archived_exam_subjects` adds immutable exam subject name/code snapshots and a nullable archived-exam subject link. A database constraint permits a missing subject only after the exam is archived. The main SQLite database was backed up at revision `0005_account_security`, then migrated to `0006`; all 51 existing rows across 19 tables were preserved and zero foreign-key violations remain. SQLite foreign keys are enabled on every connection.
- Subject and profile writes enforce valid course and college relationships, task PATCH accepts true partial updates, and exam create/update rejects the obsolete per-exam `reminder_minutes` field. Sreenidhi University is available through migration `0003`.
- Subjects and units support editing and deletion. Units with linked materials are protected from deletion. Materials, study tasks and active exams block subject deletion. Soft-deleted exams do not: their subject link is cleared while the exam, reminders, notifications and frozen subject name/code remain available as history. The material UI supports owner deletion, search, category and subject filters, and subject-scoped browsing. Successful creation clears previous form values.
- Private upload storage uses random filenames, bounded request reception and streamed writes, parsed file contents, accurate sizes and hidden paths. Image decoding rejects truncated payloads; DOCX package namespaces, content types and macro indicators are validated. Atomic per-owner quotas, unit/subject, task/subject and group membership checks are enforced. Failed uploads clean up files and roll back metadata. Shared downloads require current membership; private downloads require ownership.
- ORM timestamps use UTC-aware datetimes. Legacy naive SQLite values are interpreted as UTC. Exam inputs require an explicit timezone offset; the browser converts local input to UTC, handles daylight-saving gaps and repeated hours, and updates countdown data when an exam begins or the window regains focus.
- Exam editing, rescheduling, soft deletion, monthly calendar views and persisted reminder preferences are available. The independent reminder worker provides in-app delivery, optional email delivery, retries, cancellation and restart catch-up. Automated tests use fake providers or the local file sink and never send external email.
- Database-backed login throttling survives process restarts and returns `Retry-After` while locked. Storage usage is backfilled by revision `0004_security_limits`. Material deletion atomically claims the row before releasing its bytes, so concurrent requests cannot decrement the same owner's quota twice.
- The SQLite backup tool packages the database, uploads and a checksum manifest. The deployment preflight checks production configuration and connected persistent services without performing a deployment.
- README, environment examples and the implementation plan document exact Windows PowerShell setup, migration, startup, worker, backup, preflight and verification commands.

## Checks actually run

| Check | Result |
|---|---|
| Backend full suite | 132 passed in 175.63 seconds |
| Backend Ruff lint and format check | Passed across 57 files |
| Python dependency check | No broken requirements |
| Frontend TypeScript check | Passed |
| Frontend production build | Passed; 324.06 kB JavaScript and 30.70 kB CSS |
| Frontend Oxlint | Passed |
| Headless Microsoft Edge Playwright suite | 17 passed in 1.5 minutes |
| API integration, authentication and authorization | Included in the passing backend suite |
| Fresh migrations, legacy adoption, downgrade/re-upgrade, no-drift and process-restart persistence | Passed using disposable databases |
| Existing SQLite backup | `backend/backups/studyvault-20261014T111451Z.zip`; revision `0005_account_security`, 2 uploads, archive integrity passed |
| Existing SQLite database preservation | All 51 rows across 19 tables preserved while upgrading from `0005_account_security` to `0006_archived_exam_subjects`; 0 foreign-key violations |
| Existing database `alembic check` at revision `0006_archived_exam_subjects` | Clean; no new upgrade operations detected |
| Deployment preflight against the local development environment | Exited 1 as designed: storage, upload writability, migration head, SQLite foreign keys and database connection passed; production mode, public HTTPS CORS and account email configuration failed |

The backend suite uses isolated databases, upload directories and email sinks. It exercises registration races, login throttling, verified email, password reset and JWT invalidation; subject/profile/database integrity; partial task updates; quotas, including simultaneous deletion of one material; private and group material authorization; file parsing, limits and cleanup; exam management, archived subject snapshots and reminder-field validation; timezone handling; migrations; backup and deployment checks; restart persistence; reminder generation, concurrent worker claims, retry/failure paths, cancellation and notification privacy. The restart test persists an academic profile, subject, unit, real PDF bytes and exam across separate application processes, then verifies the dashboard and downloaded file.

The Edge suite registers a new student, saves the academic profile, creates and edits a subject and unit, uploads a real PDF, filters and finds it in the library, verifies downloaded bytes, schedules an exam and checks the stored timestamp and dashboard countdown. It reloads the session, logs out and logs in again, and verifies records remain. A second account sees an empty library and receives 404 for the first account's private download. Further browser cases cover account-security pages, material and unit deletion, exam editing, calendar and notification behavior, the independent worker, daylight-saving edge cases, stale 401 handling, dynamic upload limits, dashboard refresh and accessible mobile navigation. A realistic-content case creates PDF, PNG and DOCX materials, a deliberately long filename and six upcoming exams, then checks desktop and 390-pixel mobile layouts for horizontal overflow and captures screenshots for visual review. Browser tests use a migrated disposable database, upload directory and email sink, leaving application data untouched.

## Boundaries and verification limits

- Browser-control runtime initialization failed; headless Playwright with installed Microsoft Edge tested the major UI workflows instead.
- PostgreSQL, production hosting/TLS, live Resend delivery and non-Edge browser engines have not been exercised. Verification used local SQLite, the file email sink or fake email providers, and Edge. No production deployment is claimed.
- The backup archive passed integrity checks, but a full restoration drill has not been exercised.
- Upstream FastAPI/Starlette deprecation warnings remain under Python 3.14; they do not fail the suite. Backend lint/format/dependency checks and frontend type/build/lint checks pass.
- Existing seeded placeholder material rows never had real files. They remain preserved and correctly return 404 on download. Review or deactivate any pre-existing demo account before deploying an old database.
- Session logout removes the browser bearer token and does not itself revoke a copied token. Password reset increments the account token version and invalidates older JWTs; other sessions otherwise expire according to backend configuration.
- No AI features, chat, material preview/replace UI or advanced collaboration UI is claimed. The material UI uploads private files; existing group APIs are retained and tested for access control.
