"""Patient-only booking and cancellation routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from commons.logger import get_logger
from core.apis.dependencies import Principal, patient_principal
from core.controllers.appointment_controller import AppointmentController
from core.schemas.appointment_schema import AppointmentCreateRequest

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/appointments", tags=["Appointments"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_appointment(
    request: AppointmentCreateRequest,
    principal: Principal = Depends(patient_principal),
) -> dict:
    try:
        data = await AppointmentController().create(request, principal.user_id)
        return {"message": "Appointment booked successfully", "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected booking failure")
        raise HTTPException(status_code=500, detail="Unable to book the appointment right now") from exc


@router.get("/mine")
async def my_appointments(principal: Principal = Depends(patient_principal)) -> dict:
    try:
        data = await AppointmentController().my_appointments(principal.user_id)
        return {"message": "Appointments retrieved", "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected patient appointment list failure")
        raise HTTPException(status_code=500, detail="Unable to retrieve appointments") from exc


@router.post("/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: str,
    principal: Principal = Depends(patient_principal),
) -> dict:
    try:
        data = await AppointmentController().cancel(appointment_id, principal.user_id)
        return {"message": "Appointment cancelled; the slot is available again", "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected appointment cancellation failure")
        raise HTTPException(status_code=500, detail="Unable to cancel the appointment right now") from exc

