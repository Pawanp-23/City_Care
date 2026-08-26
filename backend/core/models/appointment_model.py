"""Appointment document. Uniqueness is added as a partial MongoDB index at startup."""

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from bson import ObjectId
from odmantic import Field, Model


class AppointmentStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    # Retained so appointments created by earlier CityCare versions remain readable.
    BOOKED = "BOOKED"
    CANCELLED = "CANCELLED"


class Symptom(str, Enum):
    FEVER = "fever"
    COUGH = "cough"
    COLD = "cold"
    BODYACHE = "bodyache"
    HEADACHE = "headache"
    OTHER = "other"


class Appointment(Model):
    patient_id: ObjectId
    # Optional only for safely reading appointments created by the original
    # single-doctor build. New bookings always require a doctor_id.
    doctor_id: Optional[ObjectId] = None
    appointment_date: str  # ISO 8601 yyyy-mm-dd, chosen for deterministic daily queries.
    slot: str
    reason: str
    temperature_f: Optional[float] = None
    symptoms: list[Symptom] = Field(default_factory=list)
    status: AppointmentStatus = AppointmentStatus.BOOKED
    cancelled_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"collection": "appointments"}
