# StudyVault: free public email verification using Brevo

## Scope
This feature branch adds an optional Brevo transactional email provider over HTTPS.
It preserves registration verification, password reset, and the existing Resend path.
No sender account or API key has been provisioned automatically. Keep live
EMAIL_PROVIDER=resend until a verified Brevo sender and API key are ready.

## Brevo account setup (owner action)
1. Sign up for a Brevo account and verify your account details.
2. Confirm transactional emails/API access is enabled. Approval may be required.
3. In **Senders, Domains & Dedicated IPs > Senders**, create and verify a
   sender address you control. When using a free mailbox domain such as
   gmail.com, Brevo may substitute its own sender domain or apply other
   restrictions; test inbox delivery and reply-to behavior.
4. In **SMTP & API > API Keys**, create a new API v3 key. Do not paste it into
   ChatGPT, logs, source files, or Vercel. Use Render environment settings.
5. Keep usage within Brevo's current free quota (consult the provider dashboard);
   the free tier is not a guarantee of inbox acceptance or scale.

## Render configuration
Service: `studyvault-api-staging` — branch `feature/free-neon-storage`.
**Deploy the feature branch revision containing the Brevo provider before
changing EMAIL_PROVIDER.** Render auto-deploy is disabled.
Add/update in Render:
```
EMAIL_PROVIDER=brevo
BREVO_API_KEY=<your private Brevo API v3 key>
EMAIL_FROM=StudyVault <your-verified-sender@example.com>
REQUIRE_EMAIL_VERIFICATION=true
```
Retain existing DATABASE_URL, SECRET_KEY, CORS_ORIGINS, PUBLIC_FRONTEND_URL,
STORAGE_BACKEND, S3 settings, and UPLOAD_DIR. No Vercel changes are required.

## Validation sequence
1. Confirm `/health` and `/ready` are healthy after deployment.
2. Check Render logs for startup/configuration errors.
3. From the **existing unverified second account**, use
   `https://studyvault-frontend.vercel.app/check-email` and click
   **Send another verification email**. Do not create another account with
   the same email: its database record already exists.
4. Confirm the email arrives in that external inbox; click the link and
   verify the account. Confirm login and account isolation.
5. Test password reset with another authorized inbox.
6. Check Brevo transactional email logs, including rejected/suppressed sends.
7. Monitor deliverability and abuse; keep per-IP registration limits enabled.

## Known limitations
- The application's Brevo HTTPS adapter has automated mocked tests, but
  sending to arbitrary users remains unverified until the account and sender
  are approved and a real end-to-end message succeeds.
- Brevo's send API lacks the same confirmed idempotency semantics used by
  StudyVault's Resend integration. Retry after an ambiguous network failure
  can cause duplicate reminder emails. Do not advertise exactly-once
  reminder email delivery with this provider.
- Brevo account approval, sender policy, limits, and deliverability may change.
- Even with working public registration, a campus-wide launch needs a reliable
  reminder scheduler, recoverable backups, monitoring, and privacy policies.

## Rollback
If Brevo fails or rate limits messages, change Render EMAIL_PROVIDER back to
`resend` and restore the previous verified test sender while investigating.
Existing database accounts are unaffected. Resend's test sender still cannot
verify arbitrary email addresses.
