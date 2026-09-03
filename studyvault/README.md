# StudyVault

A simple web app where students upload PPTs/PDFs from their computer,
organized by subject, so everything is in one place before exams.

## Tech Stack
- Java (Spring Boot)
- MySQL (database)
- Thymeleaf (server-rendered HTML)
- HTML/CSS (frontend)

## Prerequisites
- Java 17+
- Maven
- MySQL Server running locally

## Setup

1. **Create the database user/password** you want to use, and update
   `src/main/resources/application.properties`:
   ```
   spring.datasource.username=root
   spring.datasource.password=your_mysql_password
   ```
   (The database itself, `ppt_repo`, is created automatically on first run.)

2. **Run the app:**
   ```
   mvn spring-boot:run
   ```

3. **Open your browser:**
   ```
   http://localhost:8080
   ```

## How it works
- Home page (`/`) — lists all subjects, and lets you add a new one.
- Click a subject — see all uploaded files for it, and upload a new one.
- Uploaded files are stored as bytes directly inside the `ppt_files`
  table (not on disk) — this keeps files safe even on hosting
  platforms that wipe the local filesystem on restart.

## Deploying to Render (free)

Render's free tier only offers PostgreSQL (not MySQL) and does not
provide persistent disk storage - which is exactly why this app
stores file bytes in the database rather than on disk.

1. Push this project to a GitHub repository.
2. On Render, create a **PostgreSQL** database (free tier) and a
   **Web Service** connected to your GitHub repo.
3. In the Web Service's Environment settings, add these variables
   (values come from your Render Postgres "Connect" page):
   ```
   SPRING_DATASOURCE_URL=jdbc:postgresql://<host>:<port>/<database>
   SPRING_DATASOURCE_USERNAME=<user>
   SPRING_DATASOURCE_PASSWORD=<password>
   SPRING_DATASOURCE_DRIVER_CLASS_NAME=org.postgresql.Driver
   SPRING_JPA_PROPERTIES_HIBERNATE_DIALECT=org.hibernate.dialect.PostgreSQLDialect
   ```
   These override `application.properties` automatically - no code
   changes needed between local (MySQL) and deployed (Postgres).
4. Build Command: `mvn clean package -DskipTests`
   Start Command: `java -jar target/studyvault-1.0.0.jar`

Note: Render's free Postgres database expires 30 days after
creation. For a college project timeline this is usually fine, but
keep an eye on the date as your submission/demo approaches.

## What's built so far
- [x] Add subjects
- [x] Upload PPT/PDF to a subject
- [x] View + download files per subject
- [x] Deployment-ready for Render (free tier)

## Next features to add
- [ ] Search bar across all subjects
- [ ] Delete a file
- [ ] File size/type display
- [ ] Basic login (optional)
