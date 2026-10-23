import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]


def run_module(module, env):
    result = subprocess.run(
        [sys.executable, "-m", module],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def run_alembic(env, *args):
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_migrations_and_restart(tmp_path):
    env = {
        **os.environ,
        "DATABASE_URL": "sqlite:///" + (tmp_path / "migration.db").as_posix(),
        "UPLOAD_DIR": str(tmp_path / "files"),
    }
    run_module("tools.init_db", env)
    run_module("tools.init_db", env)
    source = """
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from pypdf import PdfWriter
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings
with TestClient(app) as c:
    r = c.post('/api/v1/auth/register', json={'full_name':'Persistent Student','email':'persist@example.com','password':'Password123!'})
    assert r.status_code == 201, r.text
    h = {'Authorization':'Bearer '+r.json()['access_token']}
    assert c.put('/api/v1/profile/me', headers=h, json={'academic_year':'2026-27','semester':2}).status_code == 200
    subject = c.post('/api/v1/subjects', headers=h, json={'code':'P1','name':'Persisted subject'})
    assert subject.status_code == 201
    sid = subject.json()['id']
    unit = c.post(f'/api/v1/subjects/{sid}/units', headers=h, json={'subject_id':sid,'name':'Persisted unit'})
    assert unit.status_code == 201
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    pdf = BytesIO()
    writer.write(pdf)
    Path(get_settings().upload_dir).mkdir(parents=True, exist_ok=True)
    Path(get_settings().upload_dir, 'expected.bytes').write_bytes(pdf.getvalue())
    material = c.post('/api/v1/materials/upload', headers=h, params={'subject_id':sid,'unit_id':unit.json()['id'],'title':'Persisted PDF'}, files={'file':('persisted.pdf',pdf.getvalue(),'application/pdf')})
    assert material.status_code == 201, material.text
    exam = c.post('/api/v1/exams', headers=h, json={'subject_id':sid,'title':'Persisted exam','scheduled_for':(datetime.now(timezone.utc)+timedelta(days=3)).isoformat()})
    assert exam.status_code == 201, exam.text
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    source = """
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings
with TestClient(app) as c:
    r = c.post('/api/v1/auth/login',json={'email':'persist@example.com','password':'Password123!'})
    assert r.status_code == 200
    h = {'Authorization':'Bearer '+r.json()['access_token']}
    subject = c.get('/api/v1/subjects',headers=h).json()[0]
    assert subject['name'] == 'Persisted subject'
    assert c.get('/api/v1/profile/me',headers=h).json()['semester'] == 2
    assert c.get(f"/api/v1/subjects/{subject['id']}/units",headers=h).json()[0]['name'] == 'Persisted unit'
    material = c.get('/api/v1/materials',headers=h).json()[0]
    assert material['title'] == 'Persisted PDF'
    download = c.get(f"/api/v1/materials/{material['id']}/download",headers=h)
    assert download.status_code == 200
    assert download.content == Path(get_settings().upload_dir, 'expected.bytes').read_bytes()
    assert c.get('/api/v1/exams',headers=h).json()[0]['title'] == 'Persisted exam'
    assert c.get('/api/v1/dashboard',headers=h).json()['next_exam']['title'] == 'Persisted exam'
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    env["DATABASE_URL"] = "sqlite:///" + (tmp_path / "roundtrip.db").as_posix()
    source = "from alembic.config import Config; from alembic import command; c=Config('alembic.ini'); command.upgrade(c,'head'); command.check(c); command.downgrade(c,'base'); command.upgrade(c,'head'); command.check(c)"
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_legacy_adoption_preserves_rows(tmp_path):
    url = "sqlite:///" + (tmp_path / "legacy.db").as_posix()
    env = {**os.environ, "DATABASE_URL": url}
    # Build the actual original schema, not the evolving current ORM metadata.
    run_alembic(env, "upgrade", "0001")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO colleges (id,name) VALUES ('legacy','Existing College')")
        conn.exec_driver_sql("DELETE FROM alembic_version")
    engine.dispose()
    run_module("tools.init_db", env)
    engine = create_engine(url)
    with engine.connect() as conn:
        colleges = conn.exec_driver_sql("SELECT id,name FROM colleges ORDER BY name").all()
        assert ("legacy", "Existing College") in colleges
        assert ("192b6a88-03c6-515a-afcc-0cb6055b59fd", "Sreenidhi University") in colleges
        assert (
            conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()
            == "0007_public_limits_and_membership"
        )
    engine.dispose()


def test_exam_reminder_migration_preserves_existing_student_data(tmp_path):
    url = "sqlite:///" + (tmp_path / "existing-student.db").as_posix()
    env = {**os.environ, "DATABASE_URL": url}
    run_alembic(env, "upgrade", "0001")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO users (id,email,password_hash,full_name,is_active) "
            "VALUES ('student','kept@example.com','original-password-hash','Original Student',1)"
        )
        conn.exec_driver_sql(
            "INSERT INTO subjects (id,user_id,code,name) "
            "VALUES ('subject','student','OLD101','Original subject')"
        )
        conn.exec_driver_sql(
            "INSERT INTO materials (id,user_id,subject_id,title,file_name,storage_key,mime_type,size_bytes) "
            "VALUES ('material','student','subject','Original notes','notes.pdf','original.pdf','application/pdf',42)"
        )
        conn.exec_driver_sql(
            "INSERT INTO exams (id,user_id,subject_id,title,scheduled_for,reminder_minutes) "
            "VALUES ('exam','student','subject','Original final','2035-01-20 09:30:00.000000',60)"
        )
        conn.exec_driver_sql(
            "INSERT INTO reminders (id,exam_id,notify_at,channel,sent,delivery_status) "
            "VALUES ('reminder','exam','2035-01-20 08:30:00.000000','in_app',0,'pending')"
        )
        snapshots = {
            table: conn.exec_driver_sql(f"SELECT * FROM {table}").mappings().all()
            for table in ["users", "subjects", "materials", "exams", "reminders"]
        }
    engine.dispose()
    run_module("tools.init_db", env)
    run_module("tools.init_db", env)
    run_alembic(env, "check")
    engine = create_engine(url)
    with engine.connect() as conn:
        for table, original in snapshots.items():
            current = conn.exec_driver_sql(f"SELECT * FROM {table}").mappings().all()
            assert len(current) >= len(original)
            for before in original:
                after = next(row for row in current if row["id"] == before["id"])
                # The upgrade may cancel obsolete queued delivery work, but keeps
                # every student's original content and reminder audit row.
                for key, value in before.items():
                    if table != "reminders" or key not in {"delivery_status", "updated_at"}:
                        assert after[key] == value, (table, key)
        exam = conn.exec_driver_sql("SELECT * FROM exams WHERE id='exam'").mappings().one()
        assert exam["timezone"] == "UTC"
        assert exam["deleted_at"] is None
        assert exam["subject_code_snapshot"] == "OLD101"
        assert exam["subject_name_snapshot"] == "Original subject"
        subject_id_column = next(
            column
            for column in conn.exec_driver_sql("PRAGMA table_info(exams)").mappings()
            if column["name"] == "subject_id"
        )
        assert subject_id_column["notnull"] == 0
        exam_table_sql = conn.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='exams'"
        ).scalar_one()
        assert "ck_exams_subject_or_archived" in exam_table_sql
        user = conn.exec_driver_sql("SELECT * FROM users WHERE id='student'").mappings().one()
        assert user["email_verified_at"] is not None
        assert user["token_version"] == 0
        assert (
            conn.exec_driver_sql(
                "SELECT used_bytes FROM user_storage_usage WHERE user_id='student'"
            ).scalar()
            == 42
        )
        assert (
            conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()
            == "0007_public_limits_and_membership"
        )
    engine.dispose()


def test_catalog_migration_is_reversible_and_does_not_suppress_demo_seed(tmp_path):
    url = "sqlite:///" + (tmp_path / "catalog.db").as_posix()
    env = {**os.environ, "DATABASE_URL": url, "UPLOAD_DIR": str(tmp_path / "uploads")}
    run_alembic(env, "upgrade", "0002")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO colleges (id,name,city) VALUES "
            "('existing-college','Existing College','Existing City')"
        )
    engine.dispose()
    run_alembic(env, "upgrade", "head")
    run_alembic(env, "upgrade", "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        assert (
            conn.exec_driver_sql(
                "SELECT COUNT(*) FROM colleges "
                "WHERE id='192b6a88-03c6-515a-afcc-0cb6055b59fd' "
                "AND name='Sreenidhi University'"
            ).scalar()
            == 1
        )
        assert (
            conn.exec_driver_sql("SELECT city FROM colleges WHERE id='existing-college'").scalar()
            == "Existing City"
        )
    engine.dispose()

    source = """
from fastapi.testclient import TestClient
from app.database import SessionLocal
from app.main import app
from app.seed import seed_database
with SessionLocal() as db:
    seed_database(db)
    seed_database(db)
with TestClient(app) as client:
    colleges = client.get('/api/v1/colleges').json()
    names = [college['name'] for college in colleges]
    assert names.count('Sreenidhi University') == 1
    assert names.count('National College of Engineering') == 1
    assert client.post('/api/v1/auth/login', json={'email':'demo@studyvault.dev','password':'Password123!'}).status_code == 200
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    run_alembic(env, "downgrade", "0002")
    engine = create_engine(url)
    with engine.connect() as conn:
        assert (
            conn.exec_driver_sql(
                "SELECT COUNT(*) FROM colleges WHERE id='192b6a88-03c6-515a-afcc-0cb6055b59fd'"
            ).scalar()
            == 0
        )
        assert (
            conn.exec_driver_sql("SELECT city FROM colleges WHERE id='existing-college'").scalar()
            == "Existing City"
        )
        assert (
            conn.exec_driver_sql(
                "SELECT COUNT(*) FROM colleges WHERE name='National College of Engineering'"
            ).scalar()
            == 1
        )
    engine.dispose()


def test_security_limits_migration_backfills_owned_material_bytes(tmp_path):
    url = "sqlite:///" + (tmp_path / "security-limits.db").as_posix()
    env = {**os.environ, "DATABASE_URL": url}
    run_alembic(env, "upgrade", "0003")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO users (id,email,password_hash,full_name,is_active) "
            "VALUES ('quota-user','quota@example.com','hash','Quota User',1)"
        )
        conn.exec_driver_sql(
            "INSERT INTO subjects (id,user_id,code,name) "
            "VALUES ('quota-subject','quota-user','Q1','Quota subject')"
        )
        conn.exec_driver_sql(
            "INSERT INTO materials "
            "(id,user_id,subject_id,title,file_name,storage_key,mime_type,size_bytes) VALUES "
            "('first','quota-user','quota-subject','First','first.pdf','first.pdf',"
            "'application/pdf',40),"
            "('second','quota-user','quota-subject','Second','second.pdf','second.pdf',"
            "'application/pdf',60)"
        )
    engine.dispose()

    run_alembic(env, "upgrade", "head")
    run_alembic(env, "upgrade", "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        assert (
            conn.exec_driver_sql(
                "SELECT used_bytes FROM user_storage_usage WHERE user_id='quota-user'"
            ).scalar()
            == 100
        )
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM materials").scalar() == 2
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM login_attempts").scalar() == 0
    engine.dispose()

    run_alembic(env, "downgrade", "0003")
    engine = create_engine(url)
    with engine.connect() as conn:
        tables = set(
            conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").scalars()
        )
        assert "login_attempts" not in tables
        assert "user_storage_usage" not in tables
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM materials").scalar() == 2
    engine.dispose()


def test_account_security_migration_preserves_and_verifies_existing_users(tmp_path):
    url = "sqlite:///" + (tmp_path / "account-security.db").as_posix()
    env = {**os.environ, "DATABASE_URL": url}
    run_alembic(env, "upgrade", "0004_security_limits")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO users (id,email,password_hash,full_name,is_active) "
            "VALUES ('existing-user','existing@example.com','kept-hash','Existing User',1)"
        )
        before = (
            conn.exec_driver_sql(
                "SELECT id,email,password_hash,full_name,is_active FROM users WHERE id='existing-user'"
            )
            .mappings()
            .one()
        )
    engine.dispose()

    run_alembic(env, "upgrade", "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        after = (
            conn.exec_driver_sql(
                "SELECT id,email,password_hash,full_name,is_active,email_verified_at,token_version "
                "FROM users WHERE id='existing-user'"
            )
            .mappings()
            .one()
        )
        for key, value in before.items():
            assert after[key] == value
        assert after["email_verified_at"] is not None
        assert after["token_version"] == 0
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM account_tokens").scalar() == 0
    engine.dispose()

    run_alembic(env, "downgrade", "0004_security_limits")
    engine = create_engine(url)
    with engine.connect() as conn:
        restored = (
            conn.exec_driver_sql(
                "SELECT id,email,password_hash,full_name,is_active FROM users WHERE id='existing-user'"
            )
            .mappings()
            .one()
        )
        assert dict(restored) == dict(before)
    engine.dispose()

