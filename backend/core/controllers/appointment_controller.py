"""Booking, list, and cancellation use cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from bson import ObjectId
from fastapi import HTTPException, status

from commons.logger import get_logger
from core.controllers.clinic_controller import slots_for_date, validate_booking_date
from core.cruds.appointment_crud import AppointmentCRUD, SlotAlreadyBookedError
from core.cruds.user_crud import UserCRUD
from core.models.appointment_model import Appointment, AppointmentStatus
from core.models.user_model import UserRole
from core.schemas.appointment_schema import AppointmentCreateRequest

logger = get_logger(__name__)
# India has no daylight-saving time, so a fixed offset avoids requiring the
# optional ``tzdata`` package on Windows deployments.
CLINIC_TIMEZONE = timezone(timedelta(hours=5, minutes=30), name="IST")


def serialize_appointment(appointment: Appointment) -> dict:
    """Return a safe public-facing dict for an appointment."""
    return {
        "id": str(appointment.id),
        "doctor_id": str(appointment.doctor_id) if appointment.doctor_id else None,
        "appointment_date": appointment.appointment_date,
        "slot": appointment.slot,
        "reason": appointment.reason,
        "temperature_f": appointment.temperature_f,
        "symptoms": [symptom.value for symptom in appointment.symptoms],
        "status": appointment.status.value,
        "created_at": appointment.created_at.isoformat(),
        "cancelled_at": appointment.cancelled_at.isoformat() if appointment.cancelled_at else None,
    }


class AppointmentController:
    def __init__(
        self,
        appointments: AppointmentCRUD | None = None,
        users: UserCRUD | None = None,
    ) -> None:
        self.appointments = appointments or AppointmentCRUD()
        self.users = users or UserCRUD()

    async def create(self, request: AppointmentCreateRequest, patient_id: str) -> dict:
        """Book a new appointment slot for the authenticated patient."""
        logger.info(
            "AppointmentController.create | patient_id=%s date=%s slot=%s",
            patient_id, request.appointment_date, request.slot,
        )

        try:
            validate_booking_date(request.appointment_date)

            if request.slot not in slots_for_date(request.appointment_date):
                logger.warning(
                    "AppointmentController.create | invalid slot=%s for patient=%s",
                    request.slot, patient_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="That time is not a clinic consultation slot",
                )

            if not ObjectId.is_valid(patient_id):
                logger.warning(
                    "AppointmentController.create | invalid patient_id=%s", patient_id
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid session",
                )

            patient = await self.users.get_by_id(patient_id)
            if not patient or not patient.is_active:
                logger.warning(
                    "AppointmentController.create | patient not found or inactive | id=%s", patient_id
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Your session is no longer valid. Please sign in again.",
                )

            if not ObjectId.is_valid(request.doctor_id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
            doctor = await self.users.get_by_id(request.doctor_id)
            if not doctor or doctor.role != UserRole.DOCTOR or not doctor.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

            date_as_text = request.appointment_date.isoformat()
            doctor_id = ObjectId(request.doctor_id)
            existing = await self.appointments.list_booked_for_date(date_as_text, doctor_id)
            if any(a.slot == request.slot for a in existing):
                logger.warning(
                    "AppointmentController.create | slot conflict | date=%s slot=%s",
                    date_as_text, request.slot,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="That slot has already been booked",
                )

            appointment = Appointment(
                patient_id=patient.id,
                doctor_id=doctor_id,
                appointment_date=date_as_text,
                slot=request.slot,
                reason=request.reason,
                temperature_f=request.temperature_f,
                symptoms=request.symptoms,
                status=AppointmentStatus.PENDING,
            )

            try:
                await self.appointments.create(appointment)
                logger.info(
                    "AppointmentController.create | booked | id=%s patient=%s slot=%s",
                    appointment.id, patient_id, request.slot,
                )
            except SlotAlreadyBookedError as exc:
                logger.warning(
                    "AppointmentController.create | SlotAlreadyBooked (race) | slot=%s", request.slot
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="That slot has already been booked",
                ) from exc
            except Exception:
                logger.exception(
                    "AppointmentController.create | DB error saving appointment | patient=%s", patient_id
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Unable to book appointment right now",
                )

            return serialize_appointment(appointment)

        except HTTPException:
            raise
        except Exception:
            logger.exception(
                "AppointmentController.create | unexpected error | patient=%s", patient_id
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something went wrong",
            )

    async def my_appointments(self, patient_id: str) -> list[dict]:
        """Return all appointments for the authenticated patient."""
        logger.info("AppointmentController.my_appointments | patient_id=%s", patient_id)

        try:
            if not ObjectId.is_valid(patient_id):
                logger.warning(
                    "AppointmentController.my_appointments | invalid patient_id=%s", patient_id
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid session",
                )

            appointments = await self.appointments.list_for_patient(ObjectId(patient_id))
            logger.info(
                "AppointmentController.my_appointments | returning %s appointments | patient=%s",
                len(appointments), patient_id,
            )
            doctor_ids = list({a.doctor_id for a in appointments if a.doctor_id})
            doctors = await self.users.find_by_ids(doctor_ids)
            doctor_names = {
                str(doctor.id): f"Dr. {doctor.first_name} {doctor.last_name}".strip()
                for doctor in doctors
            }
            data = []
            for appointment in appointments:
                serialized = serialize_appointment(appointment)
                serialized["doctor_name"] = doctor_names.get(
                    str(appointment.doctor_id), "CityCare care team"
                )
                data.append(serialized)
            return data

        except HTTPException:
            raise
        except Exception:
            logger.exception(
                "AppointmentController.my_appointments | unexpected error | patient=%s", patient_id
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something went wrong",
            )

    async def cancel(self, appointment_id: str, patient_id: str) -> dict:
        """Cancel an existing appointment owned by the authenticated patient."""
        logger.info(
            "AppointmentController.cancel | appointment_id=%s patient_id=%s",
            appointment_id, patient_id,
        )

        try:
            if not ObjectId.is_valid(appointment_id):
                logger.warning(
                    "AppointmentController.cancel | invalid appointment_id=%s", appointment_id
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Appointment not found",
                )

            appointment = await self.appointments.get_by_id(appointment_id)
            if not appointment:
                logger.warning(
                    "AppointmentController.cancel | appointment not found | id=%s", appointment_id
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Appointment not found",
                )

            if str(appointment.patient_id) != patient_id:
                logger.warning(
                    "AppointmentController.cancel | access denied | patient=%s appointment_owner=%s",
                    patient_id, appointment.patient_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only cancel your own appointments",
                )

            if appointment.status == AppointmentStatus.CANCELLED:
                logger.warning(
                    "AppointmentController.cancel | already cancelled | id=%s", appointment_id
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This appointment is already cancelled",
                )

            appointment_time = datetime.fromisoformat(
                f"{appointment.appointment_date}T{appointment.slot}"
            ).replace(tzinfo=CLINIC_TIMEZONE)
            now = datetime.now(CLINIC_TIMEZONE)
            if appointment_time <= now:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Past appointments cannot be cancelled online")
            if (appointment_time - now).total_seconds() < 2 * 60 * 60:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="In-person appointments must be cancelled at least two hours before the appointment time")

            appointment.status = AppointmentStatus.CANCELLED
            appointment.cancelled_at = datetime.now(UTC)
            appointment.updated_at = datetime.now(UTC)

            try:
                await self.appointments.save(appointment)
                logger.info(
                    "AppointmentController.cancel | cancelled | id=%s patient=%s",
                    appointment_id, patient_id,
                )
            except Exception:
                logger.exception(
                    "AppointmentController.cancel | DB error saving cancellation | id=%s", appointment_id
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Unable to cancel appointment right now",
                )

            return serialize_appointment(appointment)

        except HTTPException:
            raise
        except Exception:
            logger.exception(
                "AppointmentController.cancel | unexpected error | id=%s", appointment_id
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something went wrong",
            )
