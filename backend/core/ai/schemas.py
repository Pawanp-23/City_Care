"""Assistant request contracts. Conversation state lives with the signed-in browser."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatHistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "model"]
    text: str = Field(min_length=1, max_length=1200)


class AssistantChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=1800)
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=12)
