"""Prescription flow: only the assigned doctor writes; only its patient reads."""
from __future__ import annotations

from datetime import UTC, datetime
from bson import ObjectId
from fastapi import HTTPException, status

from core.cruds.appointment_crud import AppointmentCRUD
from core.cruds.user_crud import UserCRUD
from core.models.appointment_model import AppointmentStatus
from core.models.prescription_model import Prescription
from core.schemas.prescription_schema import PrescriptionCreateRequest
from core.services.prescription_files import build_prescription_pdf, extract_attachment_text, read_local_pdf, upload_pdf_to_cloudinary
from core.services.prescription_rag import index_prescription
from core.database.database import engine


def serialize(p: Prescription) -> dict:
    return {"id": str(p.id), "appointment_id": str(p.appointment_id), "diagnosis": p.diagnosis, "medicines": p.medicines, "instructions": p.instructions, "pdf_url": p.pdf_url, "storage": "local" if p.pdf_url.startswith("local:") else "cloudinary", "attachments": p.attachments, "created_at": p.created_at.isoformat()}


class PrescriptionController:
    def __init__(self) -> None:
        self.appointments = AppointmentCRUD()
        self.users = UserCRUD()

    async def create(self, appointment_id: str, doctor_id: str, payload: PrescriptionCreateRequest) -> dict:
        if not ObjectId.is_valid(appointment_id):
            raise HTTPException(status_code=404, detail="Appointment not found")
        appointment = await self.appointments.get_by_id(appointment_id)
        if not appointment or str(appointment.doctor_id) != doctor_id:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if appointment.status != AppointmentStatus.ACCEPTED:
            raise HTTPException(status_code=409, detail="Accept the appointment before issuing a prescription")
        existing = await engine.find_one(Prescription, Prescription.appointment_id == appointment.id)
        if existing:
            raise HTTPException(status_code=409, detail="A prescription has already been issued for this appointment")
        patient, doctor = await self.users.get_by_id(str(appointment.patient_id)), await self.users.get_by_id(doctor_id)
        if not patient or not doctor:
            raise HTTPException(status_code=404, detail="Patient or doctor account not found")
        pdf = build_prescription_pdf(patient_name=f"{patient.first_name} {patient.last_name}", doctor_name=f"{doctor.first_name} {doctor.last_name}", diagnosis=payload.diagnosis, medicines=payload.medicines, instructions=payload.instructions)
        url, public_id = upload_pdf_to_cloudinary(pdf, f"citycare/prescriptions/{appointment_id}-{int(datetime.now(UTC).timestamp())}")
        prescription = Prescription(appointment_id=appointment.id, patient_id=appointment.patient_id, doctor_id=ObjectId(doctor_id), diagnosis=payload.diagnosis, medicines=payload.medicines, instructions=payload.instructions, pdf_url=url, cloudinary_public_id=public_id)
        await engine.save(prescription)
        content = f"Prescription\nDiagnosis: {payload.diagnosis}\nMedicines: {'; '.join(payload.medicines)}\nInstructions: {payload.instructions}"
        await index_prescription(engine, prescription.id, prescription.patient_id, "prescription", content)
        return serialize(prescription)

    async def attach(self, prescription_id: str, doctor_id: str, filename: str, content: bytes) -> dict:
        if not ObjectId.is_valid(prescription_id): raise HTTPException(status_code=404, detail="Prescription not found")
        prescription = await engine.find_one(Prescription, Prescription.id == ObjectId(prescription_id))
        if not prescription or str(prescription.doctor_id) != doctor_id: raise HTTPException(status_code=404, detail="Prescription not found")
        if not content or len(content) > 10 * 1024 * 1024: raise HTTPException(status_code=400, detail="Attachment must be between 1 byte and 10 MB")
        extracted = extract_attachment_text(filename, content)
        if not extracted: raise HTTPException(status_code=422, detail="No readable text found in the attachment")
        prescription.attachments.append({"filename": filename, "text_indexed": True})
        await engine.save(prescription)
        await index_prescription(engine, prescription.id, prescription.patient_id, filename, extracted)
        return serialize(prescription)

    async def mine(self, patient_id: str) -> list[dict]:
        items = await engine.find(Prescription, Prescription.patient_id == ObjectId(patient_id), sort=Prescription.created_at.desc())
        return [serialize(item) for item in items]

    async def download_url(self, prescription_id: str, patient_id: str) -> dict:
        if not ObjectId.is_valid(prescription_id):
            raise HTTPException(status_code=404, detail="Prescription not found")
        prescription = await engine.find_one(Prescription, Prescription.id == ObjectId(prescription_id))
        if not prescription or str(prescription.patient_id) != patient_id:
            # Avoid confirming another patient's prescription exists.
            raise HTTPException(status_code=404, detail="Prescription not found")
        local_pdf = read_local_pdf(prescription.pdf_url)
        if prescription.pdf_url.startswith("local:"):
            if local_pdf is None:
                raise HTTPException(status_code=404, detail="Prescription file not found")
            import base64
            return {"url": "data:application/pdf;base64," + base64.b64encode(local_pdf).decode("ascii"), "filename": f"citycare-prescription-{prescription_id}.pdf", "storage": "local"}
        return {"url": prescription.pdf_url, "filename": f"citycare-prescription-{prescription_id}.pdf", "storage": "cloudinary"}

    async def accept(self, appointment_id: str, doctor_id: str) -> dict:
        appointment = await self.appointments.get_by_id(appointment_id) if ObjectId.is_valid(appointment_id) else None
        if not appointment or str(appointment.doctor_id) != doctor_id: raise HTTPException(status_code=404, detail="Appointment not found")
        if appointment.status == AppointmentStatus.CANCELLED: raise HTTPException(status_code=409, detail="Cancelled appointments cannot be accepted")
        appointment.status = AppointmentStatus.ACCEPTED
        appointment.updated_at = datetime.now(UTC)
        await self.appointments.save(appointment)
        return {"id": str(appointment.id), "status": appointment.status.value}
