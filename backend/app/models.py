from __future__ import annotations

import uuid

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.datetime_type import UTCDateTime, utcnow


class College(Base):
    __tablename__ = "colleges"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    city = Column(String, nullable=True)
    created_at = Column(UTCDateTime, default=utcnow)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

    courses = relationship("Course", back_populates="college")
    profiles = relationship("Profile", back_populates="college")


class Course(Base):
    __tablename__ = "courses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    college_id = Column(String, ForeignKey("colleges.id"), nullable=False)
    name = Column(String, nullable=False)
    degree = Column(String, nullable=True)
    created_at = Column(UTCDateTime, default=utcnow)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

    college = relationship("College", back_populates="courses")
    profiles = relationship("Profile", back_populates="course")
    subjects = relationship("Subject", back_populates="course")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    email_verified_at = Column(UTCDateTime, nullable=True)
    token_version = Column(Integer, nullable=False, default=0)
    created_at = Column(UTCDateTime, default=utcnow)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

    profile = relationship("Profile", uselist=False, back_populates="user")
    subjects = relationship("Subject", back_populates="user")
    materials = relationship("Material", back_populates="user")
    exams = relationship("Exam", back_populates="user")
    tasks = relationship("StudyTask", back_populates="user")
    memberships = relationship("ClassMember", back_populates="user")
    group_owned = relationship("ClassGroup", back_populates="owner")
    reports = relationship("MaterialReport", back_populates="reporter")
    storage_usage = relationship("UserStorageUsage", uselist=False, back_populates="user")
    account_tokens = relationship("AccountToken", back_populates="user")


class AccountToken(Base):
    __tablename__ = "account_tokens"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('email_verification', 'password_reset')",
            name="ck_account_tokens_purpose",
        ),
        Index("ix_account_tokens_user_purpose_created", "user_id", "purpose", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    purpose = Column(String(32), nullable=False)
    token_digest = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(UTCDateTime, nullable=False)
    used_at = Column(UTCDateTime, nullable=True)
    created_at = Column(UTCDateTime, nullable=False, default=utcnow)

    user = relationship("User", back_populates="account_tokens")


class UserStorageUsage(Base):
    __tablename__ = "user_storage_usage"
    __table_args__ = (CheckConstraint("used_bytes >= 0", name="ck_user_storage_usage_nonnegative"),)

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    used_bytes = Column(BigInteger, nullable=False, default=0)
    updated_at = Column(UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="storage_usage")


class PublicRateLimit(Base):
    """Hashed per-IP auth abuse controls; no raw IP addresses are retained."""
    __tablename__ = "public_rate_limits"
    __table_args__ = (
        CheckConstraint("hits >= 0", name="ck_public_rate_limits_nonnegative"),
        Index("ix_public_rate_limits_updated_at", "updated_at"),
    )

    key_hash = Column(String(64), primary_key=True)
    hits = Column(Integer, nullable=False, default=0)
    window_started_at = Column(UTCDateTime, nullable=False, default=utcnow)
    updated_at = Column(UTCDateTime, nullable=False, default=utcnow)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (
        CheckConstraint("failed_attempts >= 0", name="ck_login_attempts_nonnegative"),
        Index("ix_login_attempts_updated_at", "updated_at"),
    )

    identifier_hash = Column(String(64), primary_key=True)
    failed_attempts = Column(Integer, nullable=False, default=0)
    window_started_at = Column(UTCDateTime, nullable=False, default=utcnow)
    locked_until = Column(UTCDateTime, nullable=True)
    updated_at = Column(UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow)


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    college_id = Column(String, ForeignKey("colleges.id"), nullable=True)
    course_id = Column(String, ForeignKey("courses.id"), nullable=True)
    academic_year = Column(String, nullable=True)
    semester = Column(Integer, nullable=True)
    section = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    created_at = Column(UTCDateTime, default=utcnow)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="profile")
    college = relationship("College", back_populates="profiles")
    course = relationship("Course", back_populates="profiles")


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    course_id = Column(String, ForeignKey("courses.id"), nullable=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    semester = Column(Integer, nullable=True)
    color = Column(String, default="#4f46e5")
    created_at = Column(UTCDateTime, default=utcnow)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="subjects")
    course = relationship("Course", back_populates="subjects")
    units = relationship("Unit", back_populates="subject")
    materials = relationship("Material", back_populates="subject")
    tasks = relationship("StudyTask", back_populates="subject")
    exams = relationship("Exam", back_populates="subject")


class Unit(Base):
    __tablename__ = "units"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    name = Column(String, nullable=False)
    order_index = Column(Integer, default=1)
    created_at = Column(UTCDateTime, default=utcnow)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

    subject = relationship("Subject", back_populates="units")
    materials = relationship("Material", back_populates="unit")


class ClassGroup(Base):
    __tablename__ = "class_groups"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    invite_code = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(UTCDateTime, default=utcnow)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

    owner = relationship("User", back_populates="group_owned")
    members = relationship("ClassMember", back_populates="group")
    materials = relationship("Material", back_populates="group")
    exams = relationship("Exam", back_populates="group")


class ClassMember(Base):
    __tablename__ = "class_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_class_members_group_user"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id = Column(String, ForeignKey("class_groups.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(String, default="member")
    joined_at = Column(UTCDateTime, default=utcnow)

    user = relationship("User", back_populates="memberships")
    group = relationship("ClassGroup", back_populates="members")


class Material(Base):
    __tablename__ = "materials"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    unit_id = Column(String, ForeignKey("units.id"), nullable=True)
    group_id = Column(String, ForeignKey("class_groups.id"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    file_name = Column(String, nullable=False)
    storage_key = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer, default=0)
    category = Column(String, default="notes")
    visibility = Column(String, default="private")
    created_at = Column(UTCDateTime, default=utcnow)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="materials")
    subject = relationship("Subject", back_populates="materials")
    unit = relationship("Unit", back_populates="materials")
    group = relationship("ClassGroup", back_populates="materials")
    reports = relationship("MaterialReport", back_populates="material")


class Exam(Base):
    __tablename__ = "exams"
    __table_args__ = (
        CheckConstraint(
            "subject_id IS NOT NULL OR deleted_at IS NOT NULL",
            name="ck_exams_subject_or_archived",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    # Deleted exams are retained as audit history. If their subject is later
    # deleted, this reference is cleared while the snapshots below preserve the
    # subject context that existed when the exam was scheduled.
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=True)
    subject_code_snapshot = Column(String, nullable=False)
    subject_name_snapshot = Column(String, nullable=False)
    group_id = Column(String, ForeignKey("class_groups.id"), nullable=True)
    title = Column(String, nullable=False)
    exam_type = Column(String, default="midterm")
    scheduled_for = Column(UTCDateTime, nullable=False)
    location = Column(String, nullable=True)
    # Retain the original database column so existing installations and migration
    # history stay intact. Reminder timing is controlled by ReminderPreference.
    legacy_reminder_minutes = Column("reminder_minutes", Integer, nullable=True)
    timezone = Column(String, nullable=False, default="UTC", server_default="UTC")
    reminder_generation = Column(Integer, nullable=False, default=0, server_default="0")
    deleted_at = Column(UTCDateTime, nullable=True)
    created_at = Column(UTCDateTime, default=utcnow)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="exams")
    subject = relationship("Subject", back_populates="exams")
    group = relationship("ClassGroup", back_populates="exams")
    reminders = relationship("Reminder", back_populates="exam")


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        Index(
            "uq_reminder_slot", "exam_id", "generation", "channel", "offset_minutes", unique=True
        ),
        Index("ix_reminder_due", "delivery_status", "next_attempt_at", "notify_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = Column(String, ForeignKey("exams.id"), nullable=False)
    notify_at = Column(UTCDateTime, nullable=False)
    channel = Column(String, default="in_app")
    sent = Column(Boolean, default=False)
    delivery_status = Column(String, default="pending")
    user_id = Column(String, nullable=True, index=True)
    offset_minutes = Column(Integer, nullable=True)
    exam_scheduled_for = Column(UTCDateTime, nullable=True)
    generation = Column(Integer, nullable=False, default=0, server_default="0")
    delivery_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at = Column(UTCDateTime, nullable=True)
    first_attempt_at = Column(UTCDateTime, nullable=True)
    delivered_at = Column(UTCDateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    claim_token = Column(String, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(UTCDateTime, default=utcnow)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

    exam = relationship("Exam", back_populates="reminders")


class ReminderPreference(Base):
    __tablename__ = "reminder_preferences"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    in_app_enabled = Column(Boolean, nullable=False, default=True)
    email_enabled = Column(Boolean, nullable=False, default=False)
    reminder_minutes = Column(JSON, nullable=False, default=lambda: [10080, 4320, 1440, 60])
    timezone = Column(String, nullable=False, default="UTC")
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    reminder_id = Column(String, ForeignKey("reminders.id"), nullable=False, unique=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    exam_id = Column(String, ForeignKey("exams.id"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    scheduled_for = Column(UTCDateTime, nullable=False)
    delivered_at = Column(UTCDateTime, nullable=False, default=utcnow)
    read_at = Column(UTCDateTime, nullable=True)


class ReminderLock(Base):
    """One database row shared by schedulers and mutations, never an in-process lock."""

    __tablename__ = "reminder_lock"
    id = Column(Integer, primary_key=True)
    version = Column(Integer, nullable=False, default=0)


class StudyTask(Base):
    __tablename__ = "study_tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(UTCDateTime, nullable=True)
    completed = Column(Boolean, default=False)
    created_at = Column(UTCDateTime, default=utcnow)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="tasks")
    subject = relationship("Subject", back_populates="tasks")


class MaterialReport(Base):
    __tablename__ = "material_reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    material_id = Column(String, ForeignKey("materials.id"), nullable=False)
    reporter_id = Column(String, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String, default="open")
    created_at = Column(UTCDateTime, default=utcnow)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

    material = relationship("Material", back_populates="reports")
    reporter = relationship("User", back_populates="reports")
