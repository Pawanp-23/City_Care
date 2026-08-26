"""Doctor-only schedule and clinic metrics."""

from __future__ import annotations

import asyncio
from datetime import date

from bson import ObjectId
from fastapi import HTTPException, status

from commons.logger import get_logger
from core.cruds.appointment_crud import AppointmentCRUD
from core.cruds.user_crud import UserCRUD

logger = get_logger(__name__)


class DoctorController:
    def __init__(
        self,
        appointments: AppointmentCRUD | None = None,
        users: UserCRUD | None = None,
    ) -> None:
        self.appointments = appointments or AppointmentCRUD()
        self.users = users or UserCRUD()

    async def stats(self, doctor_id: str) -> dict:
        """Return aggregated clinic metrics for the doctor dashboard."""
        logger.info("DoctorController.stats | fetching clinic stats")

        try:
            today = date.today().isoformat()
            patients, today_visits, upcoming = await asyncio.gather(
                self.users.count_patients(),
                self.appointments.count_booked_for_date(today, ObjectId(doctor_id)),
                self.appointments.count_upcoming_bookings(today, ObjectId(doctor_id)),
            )
            logger.info(
                "DoctorController.stats | patients=%s today=%s upcoming=%s",
                patients, today_visits, upcoming,
            )
            return {
                "total_registered_patients": patients,
                "todays_visits": today_visits,
                "upcoming_visits": upcoming,
            }
        except HTTPException:
            raise
        except Exception:
            logger.exception("DoctorController.stats | unexpected error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load clinic stats right now",
            )

    async def schedule(self, selected_date: date, doctor_id: str) -> dict:
        """Return the appointment schedule for a given date with patient names."""
        logger.info("DoctorController.schedule | date=%s", selected_date)

        try:
            appointments = await self.appointments.list_schedule_for_date(
                selected_date.isoformat(), ObjectId(doctor_id)
            )

            patient_ids = list({a.patient_id for a in appointments})
            patients = await self.users.find_by_ids(patient_ids)
            names = {
                str(p.id): f"{p.first_name} {p.last_name}".strip()
                for p in patients
            }

            logger.info(
                "DoctorController.schedule | date=%s appointments=%s",
                selected_date, len(appointments),
            )
            return {
                "date": selected_date.isoformat(),
                "appointments": [
                    {
                        "id": str(a.id),
                        "slot": a.slot,
                        "patient_name": names.get(str(a.patient_id), "Unknown patient"),
                        "reason": a.reason,
                        "temperature_f": a.temperature_f,
                        "symptoms": [s.value for s in a.symptoms],
                        "status": a.status.value,
                    }
                    for a in appointments
                ],
            }
        except HTTPException:
            raise
        except Exception:
            logger.exception("DoctorController.schedule | unexpected error | date=%s", selected_date)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load schedule right now",
            )
