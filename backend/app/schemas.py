"""Typed request bodies. Identity, role, university and policy are NEVER accepted from the client: they come from the
authenticated profile and the database. (Extra fields are rejected so a forged `student_id`/`policy` is a 422, not ignored.)"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProfileIn(Strict):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    role: Literal["STUDENT", "PROFESSOR"]
    university_id: str = Field(min_length=1, max_length=80)
    teacher_code: Optional[str] = Field(default=None, max_length=200)


COLORS = ("plum", "slate", "teal", "clay")


class CourseIn(Strict):
    code: str = Field(min_length=1, max_length=30)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    color: Literal["plum", "slate", "teal", "clay"] = "plum"
    section_name: str = Field(default="Main", min_length=1, max_length=80)


class CoursePatch(Strict):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2000)
    color: Optional[Literal["plum", "slate", "teal", "clay"]] = None
    status: Optional[Literal["ACTIVE", "ARCHIVED"]] = None


class AssignmentIn(Strict):
    title: str = Field(min_length=1, max_length=200)
    topic: Optional[str] = Field(default=None, max_length=120)
    prompt: str = Field(min_length=1, max_length=50000)
    due_at: Optional[datetime] = None
    is_programming: bool = False
    publish: bool = False
    classroom_id: Optional[str] = None
    material_ids: list[str] = Field(default_factory=list, max_length=50)
    concepts: list[str] = Field(default_factory=list, max_length=20)


class AssignmentPatch(Strict):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    topic: Optional[str] = Field(default=None, max_length=120)
    prompt: Optional[str] = Field(default=None, min_length=1, max_length=50000)
    due_at: Optional[datetime] = None
    clear_due_at: bool = False
    is_programming: Optional[bool] = None
    material_ids: Optional[list[str]] = Field(default=None, max_length=50)
    concepts: Optional[list[str]] = Field(default=None, max_length=20)


class JoinIn(Strict):
    code: str = Field(min_length=4, max_length=20)

    @field_validator("code")
    @classmethod
    def norm(cls, v: str) -> str:
        v = "".join(ch for ch in v.upper() if ch.isalnum())
        if len(v) != 8:
            raise ValueError("invite codes have 8 letters/digits, e.g. K7M4-9QXA")
        return f"{v[:4]}-{v[4:]}"


class AttemptPatch(Strict):
    draft_text: str = Field(max_length=100000)


class SubmitTextIn(Strict):
    text: str = Field(min_length=1, max_length=100000)


class CoachIn(Strict):
    assignment_id: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)


class VerificationAnswerIn(Strict):
    answer: str = Field(min_length=1, max_length=8000)


class EnrollmentPatch(Strict):
    status: Literal["active", "inactive"]
