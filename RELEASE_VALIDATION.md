# StudyVault release verification — October 23, 2026

## Checked here (passed)

- Full Python `compileall` on source, tests, tools, and Alembic migrations.
- Alembic upgrade 0006 → 0007 on a backed-up SQLite source database.
- Alembic autogenerate drift check: no new migration operations detected.
- SQLite integrity and membership uniqueness constraint after migration.
- Existing duplicate memberships consolidated with the owner role preserved.
- API limiter's database-persisted per-IP counting: third request with limit 2 is HTTP 429 with `Retry-After`.
- Parsed production Docker Compose and GitHub Actions YAML.
- Shell scripts passed bash syntax checks.
- Configuration preflight correctly rejected unmodified placeholder settings.

## Not executed here (requires staging and dependencies)

- Production Docker image builds and actual Compose startup (Docker executable unavailable).
- PostgreSQL migration and concurrency tests.
- Full FastAPI test suite (python-jose and bcrypt are absent from this offline environment).
- React/TypeScript build, frontend lint, and Playwright browser tests (node_modules not installed; offline dependency installation unavailable).
- Real Resend verification/reset email, reminder delivery, DNS, HTTPS certificate issuance and renewal.
- Cloud backup/restore drills, security scanning, multi-user load testing and penetration testing.

**Do not announce a general-availability launch until the staging checklist in `docs/PRODUCTION_DEPLOYMENT.md` has been completed and a real backup restored successfully.**
