"""User document and role enum."""

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from odmantic import Field, Model


class UserRole(str, Enum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    HOSPITAL_MANAGER = "HOSPITAL_MANAGER"
    SUPERADMIN = "SUPERADMIN"


class User(Model):
    first_name: str
    last_name: str
    email: str = Field(unique=True)
    mobile_number: str
    password_hash: str
    role: UserRole = UserRole.PATIENT
    # CityCare currently operates one hospital. Keeping the identifier on each
    # account makes the authorization boundary explicit and leaves a clean path
    # for a future multi-hospital deployment.
    hospital_id: str = "citycare-nagpur"
    qualification: Optional[str] = None
    specialty: Optional[str] = None
    consultation_hours: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"collection": "users"}
