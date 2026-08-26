"""FastAPI setup: lifespan, security headers, CORS, routes, and error boundaries."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo import ASCENDING
from pymongo.errors import OperationFailure

from commons.logger import configure_logging, get_logger
from core.apis.routes import (
    appointment_router,
    assistant_router,
    auth_router,
    clinic_router,
    doctor_router,
    management_router,
    prescription_router,
    rag_router,
)
from core.config import settings
from core.database.database import close_mongo_connection, engine
from core.models.appointment_model import Appointment, AppointmentStatus
from core.models.prescription_model import ClinicKnowledgeChunk, Prescription, PrescriptionChunk
from core.models.user_model import User

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await engine.configure_database([User, Appointment, Prescription, PrescriptionChunk, ClinicKnowledgeChunk])
    appointments = engine.get_collection(Appointment)
    # Replace prior index definitions. The active-state set changed when the
    # acceptance workflow was introduced, and MongoDB cannot alter a partial
    # index in place.
    for index_name in ("one_active_appointment_per_slot", "one_active_appointment_per_doctor_slot"):
        try:
            await appointments.drop_index(index_name)
        except OperationFailure:
            pass
    # MongoDB remains the final authority when concurrent patients book the
    # same doctor's slot.
    await appointments.create_index(
        [("doctor_id", ASCENDING), ("appointment_date", ASCENDING), ("slot", ASCENDING)],
        name="one_active_appointment_per_doctor_slot",
        unique=True,
        partialFilterExpression={
            "status": {"$in": [AppointmentStatus.PENDING.value, AppointmentStatus.ACCEPTED.value, AppointmentStatus.BOOKED.value]},
            "doctor_id": {"$exists": True},
        },
    )
    await engine.get_collection(Prescription).create_index(
        [("appointment_id", ASCENDING)], name="one_prescription_per_appointment", unique=True
    )
    logger.info("MongoDB indexes verified")
    yield
    await close_mongo_connection()


app = FastAPI(
    title="CityCare Clinic API",
    version="1.0.0",
    description="Secure appointment scheduling for CityCare Clinic, Nagpur.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    messages = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"] if part != "body") or "request"
        messages.append(f"{field}: {error['msg']}")
    return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})


@app.get("/health", tags=["System"])
async def health() -> dict:
    return {"status": "ok"}


app.include_router(auth_router.router)
app.include_router(clinic_router.router)
app.include_router(appointment_router.router)
app.include_router(doctor_router.router)
app.include_router(management_router.router)
app.include_router(assistant_router.router)
app.include_router(prescription_router.router)
app.include_router(rag_router.router)
