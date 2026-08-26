import base64

from fastapi import APIRouter, Depends, HTTPException

from core.apis.dependencies import Principal, doctor_principal, patient_principal
from core.controllers.prescription_controller import PrescriptionController
from core.schemas.prescription_schema import PrescriptionAttachmentRequest, PrescriptionCreateRequest

router = APIRouter(prefix="/api/v1", tags=["Prescriptions"])

@router.post("/doctor/appointments/{appointment_id}/accept")
async def accept(appointment_id: str, principal: Principal = Depends(doctor_principal)):
    return {"message": "Appointment accepted", "data": await PrescriptionController().accept(appointment_id, principal.user_id)}

@router.post("/doctor/appointments/{appointment_id}/prescriptions")
async def create(appointment_id: str, request: PrescriptionCreateRequest, principal: Principal = Depends(doctor_principal)):
    return {"message": "Prescription generated and stored securely", "data": await PrescriptionController().create(appointment_id, principal.user_id, request)}

@router.post("/doctor/prescriptions/{prescription_id}/attachments")
async def attach(prescription_id: str, request: PrescriptionAttachmentRequest, principal: Principal = Depends(doctor_principal)):
    try:
        content = base64.b64decode(request.content_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Attachment content is not valid base64") from exc
    return {"message": "Document indexed for the patient", "data": await PrescriptionController().attach(prescription_id, principal.user_id, request.filename, content)}

@router.get("/prescriptions/mine")
async def mine(principal: Principal = Depends(patient_principal)):
    return {"message": "Prescriptions retrieved", "data": await PrescriptionController().mine(principal.user_id)}


@router.get("/prescriptions/{prescription_id}/download")
async def download(prescription_id: str, principal: Principal = Depends(patient_principal)):
    return {"message": "Prescription download authorized", "data": await PrescriptionController().download_url(prescription_id, principal.user_id)}
