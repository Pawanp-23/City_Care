"""Doctor-only routes. A valid patient token receives a clear 403."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from commons.logger import get_logger
from core.apis.dependencies import Principal, doctor_principal
from core.controllers.doctor_controller import DoctorController

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/doctor", tags=["Doctor"])


@router.get("/stats")
async def clinic_stats(principal: Principal = Depends(doctor_principal)) -> dict:
    try:
        return {"message": "Clinic stats retrieved", "data": await DoctorController().stats(principal.user_id)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected clinic stats failure")
        raise HTTPException(status_code=500, detail="Unable to retrieve clinic stats") from exc


@router.get("/schedule")
async def daily_schedule(
    selected_date: date = Query(alias="date"),
    principal: Principal = Depends(doctor_principal),
) -> dict:
    try:
        return {"message": "Schedule retrieved", "data": await DoctorController().schedule(selected_date, principal.user_id)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected daily schedule failure")
        raise HTTPException(status_code=500, detail="Unable to retrieve the daily schedule") from exc
