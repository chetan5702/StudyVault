# StudyVault: production deployment and operations (single host)

**Release status: candidate, not a validated live deployment.** The supplied source has not been built inside Docker or exercised against a running PostgreSQL instance in the review environment. Verify all steps below on a disposable staging server before real students use the service.

## Scope and assumptions

This distribution targets **one Linux host** with Docker Engine and the Docker Compose v2 plugin, a real DNS hostname, and inbound TCP **80/443** plus UDP **443**. It provides Caddy TLS termination, an Nginx-served React build, FastAPI, PostgreSQL, and **one** standalone reminder worker. PostgreSQL and upload files live in persistent Docker volumes. Only Caddy publishes host ports. Do not deploy multiple reminder-worker instances or expose the API directly without revisiting locking, proxy trust, and rate limits.

### 1. Set secrets and DNS

1. Create an A/AAAA DNS record pointing `studyvault.yourdomain.com` to the server. Ensure inbound ports 80 and 443 are reachable and outbound HTTPS can reach Resend.
2. Copy `.env.production.example` to `.env.production`. Generate **two separate** cryptographically random values:

   ```bash
   python3 -c 'import secrets; print(secrets.token_urlsafe(48))'  # SECRET_KEY
   python3 -c 'import secrets,string; a=string.ascii_letters+string.digits; print("".join(secrets.choice(a) for _ in range(48)))'  # POSTGRES_PASSWORD
   ```

3. Replace the `SITE_DOMAIN`, `PUBLIC_FRONTEND_URL`, and `CORS_ORIGINS` together. They must agree. Replace `RESEND_API_KEY` and `EMAIL_FROM` with verified working provider credentials. Do **not** share or commit the populated `.env.production`.
4. Set `chmod 600 .env.production` on Linux. Treat losing `SECRET_KEY` as a forced session invalidation; treat losing `POSTGRES_PASSWORD` as a database access/recovery problem.
5. Run `python3 scripts/check-release.py .env.production`. Placeholder credentials and non-production settings deliberately fail.

**Security note:** Production requests must come through Caddy only. Caddy **overwrites** client-controlled `X-Forwarded-For`, and Uvicorn trusts forwarded headers on the unexposed private Docker network. Publishing port 8000 or placing an unconfigured proxy ahead of Caddy can let attackers spoof IP identity and bypass per-IP authentication limits.

### 2. Build, migrate, and run

```bash
bash scripts/deploy-production.sh
# inspect container health and migration outcome
docker compose --env-file .env.production -f compose.prod.yml ps
docker compose --env-file .env.production -f compose.prod.yml logs --tail=100 migrate api worker caddy
# the API container validates schema revision and uploads:
docker compose --env-file .env.production -f compose.prod.yml exec api python -m tools.deployment_check
```

The `migrate` service applies Alembic changes before the API or worker are allowed to start. **Back up a populated database before every subsequent migration.** Container startup does not silently create an empty schema. The public site should be reachable at `https://SITE_DOMAIN`. The `/ready` endpoint is private to the Docker network, and liveness `/health` does not check PostgreSQL or reminder health.

The backend uses one Uvicorn API worker for this initial single-host deployment; evaluate request concurrency, slow uploads, memory, and the global reminder lock before increasing replicas. `docker compose ... up --build` may restart components and is not a zero-downtime migration procedure.

### 3. Mandatory staging smoke tests

- TLS handshake succeeds with a valid certificate; browser navigation and reload on nested frontend routes work; HTTP redirects to HTTPS.
- Only host ports 80/443 are exposed. API `/docs` and `/openapi.json` are disabled in production. API responses include `Cache-Control: no-store`.
- Fresh account registration sends a real verification email; unverified accounts cannot access private data; verification link is single-use.
- Test invalid logins, the `Retry-After` rate-limit header, password reset, old-session invalidation, and email re-send cooldowns.
- With two test accounts, confirm user A cannot download or mutate user B's private materials, subjects, groups, exams, or notifications.
- Upload a valid PDF/image/DOCX; reject malformed files and oversized uploads; verify per-user quotas and storage persistence after container restarts.
- Create and reschedule exams; check the reminder worker actually generates both in-app notifications and opted-in real emails, including after a worker restart.
- Run a fresh PostgreSQL restore rehearsal, **including the upload volume**; confirm file hashes, database migration revision, ownership, and UI access.
- Use the supplied `.github/workflows/ci.yml` to run Ruff, backend tests, frontend build/lint, Microsoft Edge Playwright tests, and Docker image builds in GitHub Actions (it has not run during this offline review). Perform a dependency vulnerability scan and an application-security review before admitting external users.

**Not implemented:** antivirus/antimalware scanning of user uploads, abuse protection against distributed botnets, multi-host HA, load testing, automated daily offsite backups, or cloud object storage. Consider these mandatory enhancements as adoption grows; do not claim them as completed.

### 4. Backups and recovery

During a brief maintenance window (writes stopped), from the repository root:

```bash
bash scripts/backup-production.sh
```

This stops the API and reminder worker, takes a `pg_dump -Fc` dump of the database, archives the `studyvault_uploads` volume, writes SHA-256 checksums, and restarts both services on success or failure. It **does not** automatically send the backups off the server or encrypt them. Configure encrypted, access-controlled **offsite copies** and retention (for example daily backups retained 30 days with periodic archival), and restore-test at least monthly. `backups/` is gitignored and should have restricted access. During backup, the site may return temporary errors.

To restore onto a disposable host or during a planned outage: first stop API and worker, restore the backed-up PostgreSQL dump using `pg_restore --clean --if-exists` into a fresh/appropriate PostgreSQL database, restore the upload archive into the `studyvault_uploads` volume, confirm the migration revision and hashes, then restart the API and worker. **Never perform an untested destructive restore over a live database.** Keep a consistent `SECRET_KEY` from the environment associated with the database to retain existing JWT validity where appropriate.

### 5. Operations and monitoring

- Monitor `docker compose ... ps`, API readiness, TLS certificate renewal, disk space (both volumes), database connections, and worker process uptime.
- Inspect `docker compose ... logs -f api worker caddy` and alert on worker reminder failures; `/ready` alone does **not** prove reminders are being delivered.
- Set an operating alert if the PostgreSQL or upload volumes reach 75–80% capacity; protect the backup encryption keys separately.
- Periodically clear old `public_rate_limits` rows (for example `DELETE FROM public_rate_limits WHERE updated_at < now() - interval '2 days'` once daily). This is safe for hourly-limit windows, but run with an operator-controlled maintenance schedule.
- Do not change `SECRET_KEY` or PostgreSQL credentials casually; rotating these requires a planned runbook.
- Include privacy terms, a support mechanism, data retention/deletion workflows, and incident response before expanding beyond a small invitation-only beta.

### 6. Development still supported

Local development commands in the main `README.md` remain valid. Do not use `.env.production` for local debugging. The new SQLite-compatible Alembic revision `0007_public_limits_and_membership` **removes duplicate class memberships** and creates an additional limiter table. Test it on a backup of an existing database before upgrading; rollback restores the previous schema but cannot recover duplicate membership records removed during de-duplication.
