"""HTTP layer only: request parsing, dependencies, status codes, and response envelopes."""
from core.apis.routes import appointment_router, assistant_router, auth_router, clinic_router, doctor_router, management_router, prescription_router, rag_router, telegram_router

__all__ = [
    "appointment_router",
    "assistant_router",
    "auth_router",
    "clinic_router",
    "doctor_router",
    "management_router",
    "prescription_router",
    "rag_router",
    "telegram_router",
]
