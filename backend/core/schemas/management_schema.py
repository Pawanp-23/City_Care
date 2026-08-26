"""Strict payloads for internal CityCare staff provisioning."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from core.models.user_model import UserRole
from core.schemas.auth_schema import MOBILE_PATTERN, SignupRequest


class CreateUserRequest(SignupRequest):
    """Staff-created account. Role authorization is enforced in the controller."""

    role: UserRole
    qualification: str | None = Field(default=None, max_length=120)
    specialty: str | None = Field(default=None, max_length=120)
    consultation_hours: str | None = Field(default=None, max_length=120)

    @field_validator("qualification", "specialty", "consultation_hours")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else None


class AccountStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool

