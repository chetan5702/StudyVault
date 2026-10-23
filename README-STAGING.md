# StudyVault — local Docker integration smoke test

This setup is for **local-only testing** on Windows with Docker Desktop (Linux containers). It deliberately runs in `development` mode, without public TLS or live email. It is **not** a production deployment configuration.

It runs separate, isolated PostgreSQL and upload volumes, and uses the existing `studyvault-backend:staging` and `studyvault-frontend:staging` Docker images. It does not use or change the standalone `studyvault-pg-staging` container or the existing SQLite database.

## Files to add

Extract this ZIP into the ROOT of the existing `StudyVault-Production-Hardened-2026-10-23` folder, preserving the `deploy/` directory. This adds `compose.staging.yml`, `deploy/Caddyfile.staging`, and this document. It should not replace any of the project's original files.

## Start in PowerShell

```powershell
cd C:\Users\CHETHAN\Downloads\StudyVault-Production-Hardened-2026-10-23
$secret = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
$pw = .\.venv\Scripts\python.exe -c "import secrets,string; a=string.ascii_letters+string.digits; print(''.join(secrets.choice(a) for _ in range(40)))"
"STAGING_SECRET_KEY=$secret`nSTAGING_DB_PASSWORD=$pw" | Set-Content .env.staging -Encoding ascii
Add-Content .gitignore "`n.env.staging"
docker compose --env-file .env.staging -f compose.staging.yml config --quiet
docker compose --env-file .env.staging -f compose.staging.yml up -d
# Check container status and last logs
 docker compose --env-file .env.staging -f compose.staging.yml ps
 docker compose --env-file .env.staging -f compose.staging.yml logs --tail=40 migrate api worker gateway
```

Open `http://127.0.0.1:18080/` and create a NEW local test account. Do not use real passwords or upload sensitive personal material. Register, create a subject, upload a test file, create an exam, and confirm a reminder arrives.

Check API readiness through the container:

```powershell
docker compose --env-file .env.staging -f compose.staging.yml exec api python -m tools.deployment_check
```

This setup uses an **isolated staging DB**. Previous users, exams and uploads from local SQLite are not migrated into it.

## Stop cleanly

```powershell
docker compose --env-file .env.staging -f compose.staging.yml down
```

Do NOT add `-v` unless you intentionally want to delete the staging database and uploads. It does not touch the original SQLite database.

## Caveats

- The existing images must include the corrected `0007_public_limits_and_membership.py` migration (the PostgreSQL `VARCHAR(64)` fix). If `migrate` fails, inspect its logs and rebuild the backend image from the patched local source.
- Do not use `.env.production` or launch `scripts/deploy-production.sh` for this local-only staging test.
- This environment intentionally disables email verification and actual email delivery. A successful smoke test does NOT mean public production readiness.
- If you regenerate `.env.staging` after having created the staging database, the PostgreSQL password in the persistent volume will not automatically change. Reuse the original `.env.staging` file for subsequent starts.
