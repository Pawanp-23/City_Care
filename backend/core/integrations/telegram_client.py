"""Minimal Telegram Bot API client used by the patient gateway."""

from __future__ import annotations

import asyncio
import json
import secrets
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.config import settings


class TelegramConfigurationError(RuntimeError):
    pass


class TelegramDeliveryError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token if token is not None else settings.telegram_bot_token

    def _endpoint(self, method: str) -> str:
        if not self.token:
            raise TelegramConfigurationError("TELEGRAM_BOT_TOKEN is not configured")
        return f"https://api.telegram.org/bot{self.token}/{method}"

    @staticmethod
    def _request(request: Request, timeout: float = 20.0) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed Telegram endpoint.
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, OSError, json.JSONDecodeError) as exc:
            raise TelegramDeliveryError("Telegram could not be reached") from exc
        if not result.get("ok"):
            raise TelegramDeliveryError(str(result.get("description", "Telegram rejected the request")))
        return result

    async def call(
        self, method: str, payload: dict[str, Any], *, timeout: float = 20.0
    ) -> dict[str, Any]:
        request = Request(
            self._endpoint(method),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        return await asyncio.to_thread(self._request, request, timeout)

    async def get_me(self) -> dict[str, Any]:
        return await self.call("getMe", {})

    async def delete_webhook(self) -> None:
        # Telegram does not allow getUpdates while a webhook is active.
        await self.call("deleteWebhook", {"drop_pending_updates": False})

    async def get_updates(self, offset: int | None, timeout: int = 25) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset
        response = await self.call("getUpdates", payload, timeout=timeout + 10)
        result = response.get("result", [])
        return result if isinstance(result, list) else []

    async def send_typing(self, chat_id: int) -> None:
        await self.call("sendChatAction", {"chat_id": chat_id, "action": "typing"})

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        # Telegram caps a text message at 4096 characters. Split on safe boundaries.
        remaining = text.strip() or "I couldn't produce a response."
        while remaining:
            if len(remaining) <= 3900:
                chunk, remaining = remaining, ""
            else:
                cut = remaining.rfind("\n", 0, 3900)
                if cut < 1000:
                    cut = 3900
                chunk, remaining = remaining[:cut], remaining[cut:].lstrip()
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "link_preview_options": {"is_disabled": True},
                "protect_content": True,
            }
            # Attach the keyboard only to the final chunk so Telegram does not
            # repeatedly redraw it when a long response is split.
            if reply_markup is not None and not remaining:
                payload["reply_markup"] = reply_markup
            await self.call("sendMessage", payload)

    async def send_document_url(self, chat_id: int, url: str, caption: str) -> None:
        await self.call(
            "sendDocument",
            {
                "chat_id": chat_id,
                "document": url,
                "caption": caption[:1024],
                "protect_content": True,
            },
        )

    async def send_document_bytes(
        self, chat_id: int, contents: bytes, filename: str, caption: str
    ) -> None:
        boundary = f"----MedihubTelegram{secrets.token_hex(12)}"
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption[:1024]}\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"protect_content\"\r\n\r\ntrue\r\n".encode(),
            (
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; "
                f"filename=\"{filename.replace(chr(34), '')}\"\r\nContent-Type: application/pdf\r\n\r\n"
            ).encode(),
            contents,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
        request = Request(
            self._endpoint("sendDocument"),
            data=b"".join(parts),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        await asyncio.to_thread(self._request, request, 30.0)
