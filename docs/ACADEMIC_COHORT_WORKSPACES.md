# Academic Cohort Workspaces (feature branch)

This feature introduces academic navigation by **university → department → branch/specialization → year of study → semester → subject → unit-linked resources**.

## What is implemented

- New `departments` catalog and optional `department_id` on existing `courses` (used as branches).
- Profile selections: department, branch, year of study (1–4 for B.Tech), semester (1–8), and academic session (such as `2026-27`).
- Validation that branch belongs to department and college; year of study must match the semester.
- Academic library navigation in the frontend; read-only endpoints `GET /api/v1/academic/subjects` and `GET /api/v1/academic/resources`.
- Curated subjects separated from existing **personal subjects**, and published resource links separated from existing **private/group uploads**.
- Only published links matching the student's selected branch and semester are shown; session-specific links also require the matching academic session. Null-session links are reusable across sessions.
- SUH's listed B.Tech programs are catalog entries added by migration `0008_academic_cohorts`. Their names originate from SUH's official academics/admissions website, not any assumed student email subdomain.
- Tests for cohort filtering, access without login, legacy profile behavior, and mismatch validation.

## Setup

1. Back up the database **and** uploads before migration. Test on staging first.
2. In `backend/`, run `python -m alembic upgrade head`.
3. Start the backend and frontend as described in the root README.
4. Use **Academic profile** to select a branch, year, semester, academic session.
5. Open **Semester library**.

**The library starts empty:** no subject syllabus or shared resource has been fabricated. A curator needs to approve syllabus-mapped subjects and share-permitted HTTPS resource links before they appear. At present, library curation is through controlled database administration; there is intentionally no unauthenticated upload/publish API. Do not enable direct public uploads into this library.

## Model

`College` → `Department` → `Course` (branch/specialization) → `AcademicSubject` (semester) → `AcademicResource` (optional unit metadata, session, source label and publication flag).

A student's existing `Profile` selects the scope; server-side queries use the authenticated user's profile, never an arbitrary client-supplied branch to access shared content.

## Limitations and safety

- University email domain validation **is not verification of branch/year/semester**. Profile data remains self-reported. No enforcement of unverified `ds.suh.edu.in` mappings.
- New library rows represent *curated external links*, not a replacement for encrypted storage or controlled uploads. Source and access rights require review.
- Existing personal subjects, exams, tasks, private materials and group material access remain unchanged.
- No student-level contribution workflow, faculty role, review queue, or administrator CRUD UI yet.
- No assumed published syllabus or actual exam schedule. Roll out only when authorized content is available.
- For rollback, retain a backup; downgrading the migration drops curated library tables and their data. Test recovery before production.

## Source

The initial five SUH B.Tech branch names were checked against the official [Sreenidhi University academics](https://suh.edu.in/academics/) and [B.Tech admissions](https://btech-admissions.suh.edu.in/) pages.
