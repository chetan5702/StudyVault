# StudyVault zero-cost staging: database and object storage

This is a staging integration, **not a claim of production readiness**.

The current frontend is hosted on Vercel, the FastAPI backend is intended for a free web
service, and Neon can provide a free PostgreSQL database and S3-compatible object
storage within its published usage limits. The free services can suspend or enforce
limits; they do not provide guaranteed uptime or reliable time-critical reminders.

## External services to connect

1. Provision a Neon Free project and PostgreSQL database in the region nearest the
   backend. Use the **pooled** Postgres connection string if appropriate for the
   app's request concurrency, and keep it private.
2. Enable object storage in Neon, create a **private** bucket, and retrieve its S3
   endpoint, region and access credentials. Check the current Neon free-plan limits.
3. For the backend, configure the following secret environment variables through
   the hosting dashboard; never commit them:
   - `DATABASE_URL` — Neon connection URL. For this application use
     `postgresql+psycopg://...` (plain `postgresql://` is normalized).
   - `STORAGE_BACKEND=s3`
   - `S3_ENDPOINT_URL` — full HTTPS endpoint
   - `S3_REGION` — provider's required S3 region
   - `S3_BUCKET` — private bucket
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
4. Run `alembic upgrade head` from the `backend` working directory **before**
   starting requests. Back up any populated database before running migrations.
5. Configure `SECRET_KEY` as a stable, randomly generated value; set
   `PUBLIC_FRONTEND_URL=https://studyvault-frontend.vercel.app` and
   `CORS_ORIGINS=https://studyvault-frontend.vercel.app`.
6. For production mode, the application's validator **requires** verified Resend
   email sending: `ENVIRONMENT=production`, `REQUIRE_EMAIL_VERIFICATION=true`,
   `EMAIL_PROVIDER=resend`, `EMAIL_FROM`, and `RESEND_API_KEY`. Without a
   verified sender, keep the application private; do not disable security checks
   to launch publicly.
7. Once the API is publicly healthy, set the frontend's
   `VITE_API_URL=https://YOUR-API.onrender.com/api/v1` on Vercel and rebuild.
8. Test multi-account private file access, PDF/PNG/JPEG/DOCX uploads, missing
   objects, database migrations, login/verification, and reminder delivery.

## Notes

The object storage adapter keeps legacy local files readable when the original
volume is present. Remote objects use `s3:`-prefixed keys in the materials
table, with private authenticated API downloads. It does not automatically copy
legacy local files to the new bucket. No public object ACL should be enabled.

The current Render Blueprint (`render.yaml`) provisions **paid** services. Do
not apply that blueprint for a strict ₹0 budget.

Render's legacy `StudyVault` service has separate configuration and may serve
older code. Do not overwrite it or assume it is using the latest GitHub commit
without checking its build settings and current data.

A robust public launch needs restore-tested backups, repeatable migrations,
rate-limit validation behind the hosting proxy, privacy review, and dependable
scheduled workers. The free-tier prototype does not yet provide those guarantees.
