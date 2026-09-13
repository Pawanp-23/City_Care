"""Narrow Telegram Bot API contracts accepted at the gateway boundary."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TelegramUserPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    first_name: str = Field(default="Patient", max_length=128)
    username: Optional[str] = Field(default=None, max_length=64)
    is_bot: bool = False


class TelegramChatPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    type: str


class TelegramMessagePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_id: int
    from_user: TelegramUserPayload = Field(alias="from")
    chat: TelegramChatPayload
    text: Optional[str] = Field(default=None, max_length=4096)


class TelegramUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    update_id: int
    message: Optional[TelegramMessagePayload] = None
