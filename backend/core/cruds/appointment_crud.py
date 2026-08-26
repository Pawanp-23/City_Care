"""Database operations for appointments and the booking uniqueness primitive."""

from __future__ import annotations

from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from odmantic import AIOEngine

from core.database.database import engine
from core.models.appointment_model import Appointment, AppointmentStatus


class SlotAlreadyBookedError(Exception):
    """Raised only when MongoDB's unique index rejects a competing booking."""


class AppointmentCRUD:
    def __init__(self, db: AIOEngine = engine) -> None:
        self.db = db

    async def create(self, appointment: Appointment) -> Appointment:
        try:
            await self.db.save(appointment)
        except DuplicateKeyError as exc:
            raise SlotAlreadyBookedError from exc
        return appointment

    async def get_by_id(self, appointment_id: str) -> Appointment | None:
        return await self.db.find_one(Appointment, Appointment.id == ObjectId(appointment_id))

    async def list_booked_for_date(
        self, appointment_date: str, doctor_id: ObjectId | None = None
    ) -> list[Appointment]:
        queries = [
            Appointment.appointment_date == appointment_date,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.ACCEPTED, AppointmentStatus.BOOKED]),
        ]
        if doctor_id is not None:
            queries.append(Appointment.doctor_id == doctor_id)
        return await self.db.find(Appointment, *queries)

    async def list_for_patient(self, patient_id: ObjectId) -> list[Appointment]:
        return await self.db.find(
            Appointment,
            Appointment.patient_id == patient_id,
            sort=Appointment.created_at.desc(),
        )

    async def list_schedule_for_date(
        self, appointment_date: str, doctor_id: ObjectId | None = None
    ) -> list[Appointment]:
        queries = [
            Appointment.appointment_date == appointment_date,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.ACCEPTED, AppointmentStatus.BOOKED]),
        ]
        if doctor_id is not None:
            queries.append(Appointment.doctor_id == doctor_id)
        return await self.db.find(Appointment, *queries, sort=Appointment.slot.asc())

    async def count_booked_for_date(self, appointment_date: str, doctor_id: ObjectId | None = None) -> int:
        collection = self.db.get_collection(Appointment)
        query = {"appointment_date": appointment_date, "status": {"$in": [item.value for item in (AppointmentStatus.PENDING, AppointmentStatus.ACCEPTED, AppointmentStatus.BOOKED)]}}
        if doctor_id is not None:
            query["doctor_id"] = doctor_id
        return await collection.count_documents(query)

    async def count_upcoming_bookings(self, today: str, doctor_id: ObjectId | None = None) -> int:
        collection = self.db.get_collection(Appointment)
        query = {"appointment_date": {"$gte": today}, "status": {"$in": [item.value for item in (AppointmentStatus.PENDING, AppointmentStatus.ACCEPTED, AppointmentStatus.BOOKED)]}}
        if doctor_id is not None:
            query["doctor_id"] = doctor_id
        return await collection.count_documents(query)

    async def save(self, appointment: Appointment) -> Appointment:
        await self.db.save(appointment)
        return appointment
