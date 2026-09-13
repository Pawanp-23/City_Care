"""Authenticated Medihub-to-Telegram pairing and Telegram webhook routes."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status

from core.apis.dependencies import Principal, patient_principal
from core.config import settings
from core.schemas.telegram_schema import TelegramUpdatePayload
from core.services.telegram_gateway import TelegramGateway

router = APIRouter(prefix="/api/v1/integrations/telegram", tags=["Telegram Patient Gateway"])


@router.post("/link-code")
async def create_link_code(principal: Principal = Depends(patient_principal)) -> dict:
    """Create a short-lived one-time pairing code for an authenticated patient."""
    data = await TelegramGateway().create_link_code(principal.user_id)
    return {"message": "Telegram link code created", "data": data}


@router.get("/link-status")
async def telegram_link_status(principal: Principal = Depends(patient_principal)) -> dict:
    """Return only the authenticated patient's own Telegram pairing status."""
    data = await TelegramGateway().link_status(principal.user_id)
    return {"message": "Telegram link status retrieved", "data": data}


@router.post("/webhook", include_in_schema=False)
async def telegram_webhook(
    update: TelegramUpdatePayload,
    secret_token: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> dict:
    """Receive Telegram updates only when Telegram echoes the configured secret."""
    expected = settings.telegram_webhook_secret
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram webhook is not configured",
        )
    if not secret_token or not hmac.compare_digest(secret_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")
    await TelegramGateway().handle_update(update)
    return {"ok": True}
