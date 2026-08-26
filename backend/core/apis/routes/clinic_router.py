"""Public clinic metadata and availability routes."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from commons.logger import get_logger
from core.controllers.clinic_controller import ClinicController

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Clinic"])


@router.get("/clinic")
async def clinic_info() -> dict:
    try:
        return {"message": "Clinic information retrieved", "data": await ClinicController.clinic_info()}
    except Exception as exc:
        logger.exception("Unexpected clinic information failure")
        raise HTTPException(status_code=500, detail="Unable to retrieve clinic information") from exc


@router.get("/doctors")
async def doctors() -> dict:
    try:
        return {"message": "Care team retrieved", "data": await ClinicController().doctors()}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected care-team failure")
        raise HTTPException(status_code=500, detail="Unable to retrieve the care team") from exc


@router.get("/appointments/free-slots")
async def free_slots(
    selected_date: date = Query(alias="date"),
    doctor_id: str = Query(alias="doctor_id"),
) -> dict:
    try:
        data = await ClinicController().free_slots(selected_date, doctor_id)
        return {"message": "Free slots retrieved", "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected free slots failure")
        raise HTTPException(status_code=500, detail="Unable to retrieve free slots") from exc
