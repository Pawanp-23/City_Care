"""Run the Medihub Telegram gateway locally using Bot API long polling."""

from __future__ import annotations

import asyncio
import logging

from pydantic import ValidationError

from commons.logger import configure_logging
from core.config import settings
from core.integrations.telegram_client import (
    TelegramClient,
    TelegramConfigurationError,
    TelegramDeliveryError,
)
from core.schemas.telegram_schema import TelegramUpdatePayload
from core.services.telegram_gateway import TelegramGateway

logger = logging.getLogger(__name__)


async def run() -> None:
    if not settings.telegram_bot_token:
        raise TelegramConfigurationError("TELEGRAM_BOT_TOKEN is not configured")

    client = TelegramClient()
    gateway = TelegramGateway(client)
    identity = await client.get_me()
    bot = identity.get("result", {})
    username = bot.get("username", "unknown")

    # Polling and webhooks are mutually exclusive in Telegram's Bot API.
    await client.delete_webhook()
    logger.info("Telegram polling started for @%s", username)

    offset: int | None = None
    backoff_seconds = 1
    while True:
        try:
            updates = await client.get_updates(offset)
            for raw_update in updates:
                update_id = raw_update.get("update_id")
                try:
                    update = TelegramUpdatePayload.model_validate(raw_update)
                    await gateway.handle_update(update)
                except ValidationError:
                    logger.warning("Ignoring malformed Telegram update %s", update_id)
                except Exception:
                    # One malformed state or unexpected application error must
                    # not terminate the entire patient bot. The user can resend
                    # the action after receiving the gateway's error message.
                    logger.exception("Telegram update %s failed; continuing", update_id)
                if isinstance(update_id, int):
                    offset = update_id + 1
            backoff_seconds = 1
        except (TelegramDeliveryError, OSError):
            logger.warning(
                "Telegram polling connection failed; retrying in %s second(s)",
                backoff_seconds,
            )
            await asyncio.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 30)


def main() -> None:
    configure_logging()
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Telegram polling stopped")


if __name__ == "__main__":
    main()
