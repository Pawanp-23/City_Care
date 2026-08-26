"""Read-only clinic information and slot availability."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException, status

from commons.logger import get_logger
from core.constants import CLINIC, FIXED_CLOSURE_DATES, MORNING_SLOTS, SLOTS
from core.cruds.appointment_crud import AppointmentCRUD
from core.cruds.user_crud import UserCRUD
from core.models.user_model import User, UserRole

logger = get_logger(__name__)


def validate_booking_date(selected_date: date) -> None:
    """
    Raise 400 if the date is in the past or more than 7 days ahead.
    Used by both ClinicController and AppointmentController.
    """
    today = date.today()
    logger.info("validate_booking_date | selected=%s today=%s", selected_date, today)

    if selected_date < today:
        logger.warning("validate_booking_date | past date rejected | selected=%s", selected_date)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointments cannot be booked in the past",
        )
    if selected_date > today + timedelta(days=7):
        logger.warning(
            "validate_booking_date | too far ahead rejected | selected=%s", selected_date
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointments can only be booked up to 7 days ahead",
        )
    if selected_date.weekday() == 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CityCare is closed on Sundays")
    if (selected_date.month, selected_date.day) in FIXED_CLOSURE_DATES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CityCare is closed on this public holiday")


def slots_for_date(selected_date: date) -> tuple[str, ...]:
    """Return handbook-compliant slots, including the second-Saturday closure."""
    # Saturday whose day falls between 8 and 14 is the second Saturday.
    if selected_date.weekday() == 5 and 8 <= selected_date.day <= 14:
        return MORNING_SLOTS
    return SLOTS


class ClinicController:
    def __init__(
        self,
        appointments: AppointmentCRUD | None = None,
        users: UserCRUD | None = None,
    ) -> None:
        self.appointments = appointments or AppointmentCRUD()
        self.users = users or UserCRUD()

    @staticmethod
    async def clinic_info() -> dict:
        """Return static clinic metadata."""
        logger.info("ClinicController.clinic_info | returning clinic info")
        try:
            return CLINIC
        except Exception:
            logger.exception("ClinicController.clinic_info | unexpected error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load clinic info right now",
            )

    @staticmethod
    def serialize_doctor(doctor: User) -> dict:
        """Expose only public care-team information, never account details."""
        return {
            "id": str(doctor.id),
            "name": f"Dr. {doctor.first_name} {doctor.last_name}".strip(),
            "qualification": doctor.qualification or CLINIC["qualification"],
            "specialty": doctor.specialty or CLINIC["specialty"],
            "consultation_hours": doctor.consultation_hours or "10:00 - 13:00, 17:00 - 20:00",
        }

    async def doctors(self) -> list[dict]:
        try:
            doctors = await self.users.list_doctors()
            return [self.serialize_doctor(doctor) for doctor in doctors]
        except Exception:
            logger.exception("ClinicController.doctors | unexpected error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load the care team right now",
            )

    async def free_slots(self, selected_date: date, doctor_id: str) -> dict:
        """Return all available (unbooked) slots for a given date."""
        logger.info("ClinicController.free_slots | date=%s doctor=%s", selected_date, doctor_id)

        try:
            validate_booking_date(selected_date)

            from bson import ObjectId

            if not ObjectId.is_valid(doctor_id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
            doctor = await self.users.get_by_id(doctor_id)
            if not doctor or doctor.role != UserRole.DOCTOR or not doctor.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

            booked = await self.appointments.list_booked_for_date(
                selected_date.isoformat(), ObjectId(doctor_id)
            )
            booked_slots = {a.slot for a in booked}
            available = [slot for slot in slots_for_date(selected_date) if slot not in booked_slots]

            logger.info(
                "ClinicController.free_slots | date=%s booked=%s available=%s",
                selected_date, len(booked_slots), len(available),
            )
            return {
                "date": selected_date.isoformat(),
                "doctor": self.serialize_doctor(doctor),
                "slots": available,
            }

        except HTTPException:
            raise
        except Exception:
            logger.exception(
                "ClinicController.free_slots | unexpected error | date=%s", selected_date
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load slots right now",
            )
