"""Schemas exposed at the authentication boundary."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

MOBILE_PATTERN = re.compile(r"^\+91[6-9]\d{9}$")


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    mobile_number: str
    password: str = Field(min_length=8, max_length=72)

    @field_validator("first_name", "last_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("This field cannot be blank")
        return value.strip().title()

    @field_validator("mobile_number")
    @classmethod
    def validate_mobile_number(cls, value: str) -> str:
        compact = value.replace(" ", "").replace("-", "")
        if not MOBILE_PATTERN.fullmatch(compact):
            raise ValueError("Use an Indian mobile number like +919876543210")
        return compact

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not re.search(r"[A-Z]", value) or not re.search(r"[a-z]", value) or not re.search(r"\d", value):
            raise ValueError("Password needs an uppercase letter, lowercase letter, and number")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)
