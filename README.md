# StudyVault

A subject-wise vault for lecture slides and notes, built for the week before
exams. Upload the PDFs and decks your class has scattered across WhatsApp,
then find the right one by searching for a phrase that appears *inside* it.

Java 17 · Spring Boot 3.2 · Spring Security · JPA · Thymeleaf · MySQL or PostgreSQL

---

## What it does

- **Search inside documents.** Text is extracted from every upload with Apache
  Tika and stored alongside the file, so searching "knapsack" finds the deck
  that mentions it on slide 14, with the matching sentence shown in context.
- **Exam countdown.** Give a subject an exam date and it moves to the top of
  the home page with a countdown. The left edge of each card is coloured by how
  close the exam is.
- **Duplicate detection.** Every file is hashed with SHA-256. Uploading a file
  that is already in that subject is detected and skipped.
- **Download a whole subject as a zip**, streamed one file at a time.
- **In-browser preview** for PDFs, so you can check a deck without downloading it.
- **Accounts and roles.** Everyone signs in. `USER` can browse, search, upload
  and download; `ADMIN` can also delete.

## Running it locally

**Prerequisites:** Java 17+, Maven, and a MySQL server (or skip MySQL and point
the app at any PostgreSQL instance instead).

```bash
export SPRING_DATASOURCE_USERNAME=root
export SPRING_DATASOURCE_PASSWORD=your_mysql_password
mvn spring-boot:run
```

Open http://localhost:8080 and sign in with `student` / `student123`, or
`admin` / `admin123` for delete rights. The app logs a warning while those
shipped passwords are still in use; set `SV_ADMIN_PASSWORD` and
`SV_STUDENT_PASSWORD` to change them.

The `studyvault` database and its tables are created on first run.

**Running the tests** needs no database at all, because they run against
in-memory H2:

```bash
mvn test
```

**With Docker:**

```bash
docker build -t studyvault .
docker run -p 8080:8080 \
  -e SPRING_DATASOURCE_URL='jdbc:mysql://host.docker.internal:3306/studyvault' \
  -e SPRING_DATASOURCE_USERNAME=root \
  -e SPRING_DATASOURCE_PASSWORD=your_mysql_password \
  studyvault
```

## How it is put together

```
web/          controllers, flash messages, error handling
service/      validation, hashing, text extraction, view models
repository/   Spring Data interfaces and read-only projections
domain/       Subject and Material entities
config/       security rules and externalised settings
```

Uploaded bytes live in the `materials` table rather than on disk, because free
hosting tiers wipe the local filesystem on every restart while the database
survives. The trade-off is that the database carries the weight; see
"Where to take it next" below.

### Two design decisions worth knowing about

**No file bytes are read to draw a screen.** Both list pages query through
closed projection interfaces (`SubjectSummary`, `MaterialView`) that name only
the columns they display, and the home page gets its counts from a single
aggregate query. The bytes are loaded in exactly one place: the download
handler. `spring.jpa.open-in-view` is off, so a template cannot trigger a
query by accident either.

**The bytes are mapped as `VARBINARY`, not `@Lob`.** Under Hibernate 6,
`@Lob byte[]` maps to PostgreSQL's `oid` large-object type, which needs an
explicit transaction and fails at download time with "Large Objects may not be
used in auto-commit mode". `@JdbcTypeCode(SqlTypes.VARBINARY)` with an explicit
length gives `bytea` on PostgreSQL and `longblob` on MySQL.

## Deploying to Render

`render.yaml` covers the setup. Doing it by hand instead:

1. Create a PostgreSQL database and a web service pointing at your repo, with
   the runtime set to Docker.
2. Set these environment variables on the web service:

   ```
   SPRING_DATASOURCE_URL=jdbc:postgresql://<host>:<port>/<database>
   SPRING_DATASOURCE_USERNAME=<user>
   SPRING_DATASOURCE_PASSWORD=<password>
   SV_ADMIN_PASSWORD=<something long>
   SV_STUDENT_PASSWORD=<something long>
   ```

   Render shows its connection string as `postgres://…`; the JDBC driver needs
   the `jdbc:postgresql://` form, so rewrite the prefix.

No driver class or Hibernate dialect is configured anywhere, which is what lets
the same build run on MySQL locally and PostgreSQL in production. Both are
worked out from the URL.

Check Render's current free-tier terms before you rely on them: free PostgreSQL
instances have expired 30 days after creation.

### Upgrading from the earlier version

The tables were renamed (`ppt_files` is now `materials`) and gained columns, so
Hibernate creates the new schema alongside the old one rather than migrating
it. Copy anything you want to keep across, then drop `ppt_files`.

## Where to take it next

- **Real full-text search.** The current search is a portable `LIKE` scan,
  which is fine for a class-sized vault and will slow down past a few thousand
  files. On PostgreSQL, add a `tsvector` column with a GIN index and switch the
  query to `@@ plainto_tsquery`; on MySQL, a `FULLTEXT` index over
  `content_text`.
- **Move the bytes to object storage.** Cloudflare R2 or Supabase Storage,
  keeping only the metadata and a key in the database. This is the honest
  answer to "does this scale", and it makes downloads streamable.
- **Flyway migrations** instead of `ddl-auto=update`, once the schema stops
  changing every day.
- **Database-backed accounts** with sign-up restricted to your college's email
  domain, replacing the two in-memory users.
- **Generated study packs.** The extracted text is already there: send it to a
  language model and cache a summary, a glossary and practice questions per
  file.
- **Slide thumbnails** rendered from page one with PDFBox, shown on the cards.

## Licence

MIT. See `LICENSE`.
