"""Prescription records and patient-scoped RAG chunks."""

from datetime import UTC, datetime
from typing import Optional

from bson import ObjectId
from odmantic import Field, Model


class Prescription(Model):
    appointment_id: ObjectId
    patient_id: ObjectId
    doctor_id: ObjectId
    diagnosis: str
    medicines: list[str] = Field(default_factory=list)
    instructions: str
    pdf_url: str
    cloudinary_public_id: Optional[str] = None
    attachments: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"collection": "prescriptions"}


class PrescriptionChunk(Model):
    prescription_id: ObjectId
    patient_id: ObjectId
    text: str
    source: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"collection": "prescription_chunks"}


class ClinicKnowledgeChunk(Model):
    """Public clinic-handbook chunks. Never store patient records here."""
    text: str
    source: str
    page: int
    chunk_index: int
    embedding: list[float] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"collection": "clinic_knowledge_chunks"}
