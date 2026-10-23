from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

_PHONE_NUMBER_PATTERN = re.compile(r"^\+?[0-9 ()-]+$")


def normalize_phone_number(value: str | None) -> str | None:
    """Normalize a user-entered international phone number for storage."""
    if value is None:
        return None

    candidate = value.strip()
    if not candidate:
        return None
    if not _PHONE_NUMBER_PATTERN.fullmatch(candidate):
        raise ValueError(
            "Phone number may contain only an optional leading +, digits, spaces, "
            "parentheses, and hyphens"
        )

    has_international_prefix = candidate.startswith("+")
    number = candidate[1:] if has_international_prefix else candidate
    digits = re.sub(r"[ ()-]", "", number)
    if not 7 <= len(digits) <= 15:
        raise ValueError("Phone number must contain between 7 and 15 digits")
    if has_international_prefix and digits.startswith("0"):
        raise ValueError("International phone number country code cannot start with 0")

    return ("+" if has_international_prefix else "") + digits


class CollegeCreate(BaseModel):
    name: str
    city: str | None = None


class CollegeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    city: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CourseCreate(BaseModel):
    college_id: str
    name: str
    degree: str | None = None


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    college_id: str
    name: str
    degree: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProfileUpdate(BaseModel):
    college_id: str | None = None
    course_id: str | None = None
    academic_year: str | None = None
    semester: int | None = Field(default=None, ge=1, le=20)
    section: str | None = None
    phone_number: str | None = Field(default=None, max_length=25)
    avatar_url: str | None = None
    bio: str | None = None

    @field_validator("phone_number")
    @classmethod
    def valid_phone_number(cls, value: str | None) -> str | None:
        return normalize_phone_number(value)


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    college_id: str | None = None
    course_id: str | None = None
    academic_year: str | None = None
    semester: int | None = None
    section: str | None = None
    phone_number: str | None = None
    avatar_url: str | None = None
    bio: str | None = None


class UserRegister(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    phone_number: str | None = Field(default=None, max_length=25)

    @field_validator("full_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Full name is required")
        return value.strip()

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must fit within 72 UTF-8 bytes")
        return value

    @field_validator("phone_number")
    @classmethod
    def valid_phone_number(cls, value: str | None) -> str | None:
        return normalize_phone_number(value)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    user: dict
    verification_required: bool = False


class EmailRequest(BaseModel):
    email: EmailStr


class AccountTokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class PasswordResetConfirm(AccountTokenRequest):
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must fit within 72 UTF-8 bytes")
        return value


class MessageOut(BaseModel):
    message: str


class SubjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    semester: int | None = Field(default=None, ge=1, le=20)
    course_id: str | None = None
    color: str | None = None


class SubjectUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    code: str | None = Field(default=None, min_length=1, max_length=40)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    semester: int | None = Field(default=None, ge=1, le=20)
    course_id: str | None = None
    color: str | None = None

    @model_validator(mode="after")
    def required_values_cannot_be_cleared(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one subject field to update")
        for name in self.model_fields_set & {"code", "name"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    course_id: str | None = None
    code: str
    name: str
    semester: int | None = None
    color: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UnitCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    subject_id: str
    name: str = Field(min_length=1, max_length=200)
    order_index: int = Field(default=1, ge=1)


class UnitUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    order_index: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def valid_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one unit field to update")
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    subject_id: str
    name: str
    order_index: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MaterialCreate(BaseModel):
    subject_id: str
    unit_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category: str = "notes"
    visibility: Literal["private", "group"] = "private"
    group_id: str | None = None


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    subject_id: str
    unit_id: str | None = None
    group_id: str | None = None
    title: str
    description: str | None = None
    file_name: str
    mime_type: str
    size_bytes: int
    category: str
    visibility: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExamCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    subject_id: str
    title: str = Field(min_length=1, max_length=200)
    exam_type: str = Field(default="midterm", min_length=1, max_length=60)
    scheduled_for: AwareDatetime
    location: str | None = Field(default=None, max_length=300)
    group_id: str | None = None
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Use a valid IANA time zone, such as Asia/Kolkata") from exc
        return value


class ExamUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    subject_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    exam_type: str | None = Field(default=None, min_length=1, max_length=60)
    scheduled_for: AwareDatetime | None = None
    location: str | None = Field(default=None, max_length=300)
    group_id: str | None = None
    timezone: str | None = None

    @model_validator(mode="after")
    def valid_changes(self):
        for name in self.model_fields_set - {"location", "group_id"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        if self.timezone is not None:
            ExamCreate.valid_timezone(self.timezone)
        return self


class ExamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    subject_id: str
    group_id: str | None = None
    title: str
    exam_type: str
    scheduled_for: datetime
    location: str | None = None
    timezone: str = "UTC"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    exam_id: str
    notify_at: datetime
    channel: str
    sent: bool
    delivery_status: str


class ReminderPreferencesUpdate(BaseModel):
    in_app_enabled: bool = True
    email_enabled: bool = False
    reminder_minutes: list[Literal[10080, 4320, 1440, 60]] = Field(
        default_factory=lambda: [10080, 4320, 1440, 60], max_length=4
    )
    timezone: str = "UTC"

    @field_validator("reminder_minutes")
    @classmethod
    def unique_offsets(cls, value: list[int]) -> list[int]:
        return sorted(set(value), reverse=True)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        return ExamCreate.valid_timezone(value)


class ReminderPreferencesOut(ReminderPreferencesUpdate):
    model_config = ConfigDict(from_attributes=True)
    email_available: bool = False


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    message: str
    exam_id: str
    scheduled_for: datetime
    delivered_at: datetime
    read_at: datetime | None = None


class NotificationList(BaseModel):
    items: list[NotificationOut]
    unread_count: int


class StudyTaskCreate(BaseModel):
    subject_id: str | None = None
    title: str
    description: str | None = None
    due_date: AwareDatetime | None = None
    completed: bool = False


class StudyTaskUpdate(BaseModel):
    subject_id: str | None = None
    title: str | None = None
    description: str | None = None
    due_date: AwareDatetime | None = None
    completed: bool | None = None

    @model_validator(mode="after")
    def required_values_cannot_be_cleared(self):
        for name in self.model_fields_set & {"title", "completed"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class StudyTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    subject_id: str | None = None
    title: str
    description: str | None = None
    due_date: datetime | None = None
    completed: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    owner_id: str
    invite_code: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GroupMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    group_id: str
    user_id: str
    role: str
    joined_at: datetime | None = None


class MaterialReportCreate(BaseModel):
    material_id: str
    reason: str


class MaterialReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    material_id: str
    reporter_id: str
    reason: str
    status: str
    created_at: datetime | None = None
