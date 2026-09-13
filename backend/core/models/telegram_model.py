"""Telegram gateway identity, session, pairing, and replay-protection records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from bson import ObjectId
from odmantic import Field, Model


class TelegramPatientLink(Model):
    telegram_user_id: int
    telegram_chat_id: int
    patient_id: ObjectId
    username: Optional[str] = None
    is_active: bool = True
    linked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"collection": "telegram_patient_links"}


class TelegramSession(Model):
    """A bounded, per-DM conversation state record inspired by Hermes sessions."""

    session_key: str
    telegram_user_id: int
    telegram_chat_id: int
    patient_id: Optional[ObjectId] = None
    state: str = "READY"
    # Workflow state includes scalar registration fields plus dynamic doctor
    # and slot button lists. ODMantic must accept both when sessions reload.
    data: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, str]] = Field(default_factory=list)
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"collection": "telegram_sessions"}


class TelegramLinkCode(Model):
    patient_id: ObjectId
    code_hash: str
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"collection": "telegram_link_codes"}


class TelegramUpdateReceipt(Model):
    update_id: int
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"collection": "telegram_update_receipts"}
