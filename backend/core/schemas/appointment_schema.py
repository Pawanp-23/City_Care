"""Schemas used when a patient creates an appointment."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.models.appointment_model import Symptom


class AppointmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    appointment_date: date
    doctor_id: str = Field(min_length=24, max_length=24)
    slot: str = Field(min_length=5, max_length=5)
    reason: str = Field(min_length=10, max_length=1000)
    temperature_f: float | None = Field(default=None, ge=95, le=110)
    symptoms: list[Symptom] = Field(default_factory=list, max_length=6)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 10:
            raise ValueError("Reason must be at least 10 characters")
        return cleaned

    @field_validator("symptoms")
    @classmethod
    def unique_symptoms(cls, value: list[Symptom]) -> list[Symptom]:
        if len(value) != len(set(value)):
            raise ValueError("Symptoms cannot contain duplicates")
        return value
