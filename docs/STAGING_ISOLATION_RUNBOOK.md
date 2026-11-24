# StudyVault Faculty/Admin — isolated staging runbook

Status: **infrastructure partially provisioned; no backend/frontend staging deployment yet**.

## Isolation boundaries

- Source: `feature/faculty-admin-publishing`, review PR #5. Do not merge PR #4 or #5 to the production-serving branch for a staging test.
- Database: independent Neon project `hidden-cell-91746062`, branch `br-steep-band-biaf2gq7`, database `studyvault_stage`. **Never use the existing `flat-leaf-59190068` project**.
- Storage: private bucket `studyvault-faculty-staging-private` in the new Neon project. Do not use the existing production `studyvault-private-materials` bucket.
- Backend: create a **separate** Render service (suggested name `studyvault-faculty-api-isolated`), Docker source branch as above, context `./backend`, Dockerfile `./backend/Dockerfile`, region Singapore, Free plan only if the account allows it. Disable auto-deploy until manually reviewed.
- Frontend: create a **separate** Vercel project (suggested name `studyvault-faculty-staging`), Vite build from `frontend`, with its own backend URL and deployment protection. Never connect its output to the existing production aliases.
- Never point the staging frontend at `studyvault-api-staging.onrender.com`; that service is already serving the existing frontend.

## Required safeguards before making the staging API publicly reachable

1. Have a university-approved or controlled **staging-only** access policy. Do not present a publicly accessible API with `REQUIRE_EMAIL_VERIFICATION=false`, `ENVIRONMENT=development`, or a publicly known shared test password as secure staging.
2. Use `ENVIRONMENT=production`, `STUDYVAULT_DEBUG=false`, `SEED_DEMO=false`, `REQUIRE_EMAIL_VERIFICATION=true`, and `PUBLIC_AUTH_LIMIT_ENABLED=true` for production-like external testing.
3. Configure a staging-only email provider and sender correctly; the production configuration rejects missing email delivery. Avoid sending test messages to real faculty/students without authorization.
4. Generate a fresh, strong `SECRET_KEY`, unique to this staging service. Never commit secrets to Git, paste them into chat, or use the production secret.
5. Set `DATABASE_URL` from the **new** Neon staging project only. Set `STORAGE_BACKEND=s3`, `S3_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET`, and short-lived staging-only storage credentials created in Neon. Enter secrets in the hosting platform's protected environment settings, never in code.
6. Set `PUBLIC_FRONTEND_URL` and `CORS_ORIGINS` to the *exact* isolated frontend origin; Vite also needs `VITE_API_URL` set to the isolated API URL with `/api/v1`.
7. Use a staging-specific operator bootstrap procedure to authorize **fictional** staff after verifying their test identity. The production backend intentionally provides no public admin bootstrap endpoint.
8. Confirm billing and quotas before creating more hosting services. No paid plan is authorized by this runbook.

## Deployment procedure (after protected secrets are entered)

1. Confirm backend deployment SHA matches the reviewed `feature/faculty-admin-publishing` commit and that all GitHub Actions checks are green.
2. Apply `alembic upgrade head` **only** to `studyvault_stage`. Confirm `alembic_version` is `0010_faculty_admin_publishing`.
3. Start the separate backend and check `/ready` (database + migration), not just `/health` (liveness).
4. Build and deploy the separate frontend with `VITE_API_URL=https://<isolated-backend-host>/api/v1`. Enable Vercel deployment protection, if available under the plan. Ensure links and tokens remain staging-only.
5. Create fictional admin, faculty, and student accounts in staging, then follow the approved operator-only staff bootstrap procedure.
6. Exercise admin subject creation and faculty assignment; upload a synthetic PDF as a draft, publish it, verify an enrolled fictional student can download it, verify wrong-branch and unenrolled users receive 404, then unpublish and verify download is denied.
7. Verify object storage is private and documents are never sent as public/signed links in API responses. Check that deletion and rollback cleanup leave no orphaned objects.
8. Test backup and recovery using only staging data; review logs for secrets and email disclosure; record the tested deployment commit.
9. Confirm both existing Render services, the original Vercel project, and the prior Neon database remain unchanged.

## Current limitations

- Newly created Neon database currently contains no application tables; migration has not been applied.
- Staging storage bucket is currently empty and private.
- The new Render service and dedicated Vercel project were **not created**. An attempt to pass issued secrets across connected tools was blocked. Do not bypass that boundary or reuse production credentials.
- All earlier CI results apply to isolated GitHub Actions tests; they do not substitute for a hosted end-to-end test.
