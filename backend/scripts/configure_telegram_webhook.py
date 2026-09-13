"""Register the Medihub webhook and patient command shortcuts with Telegram."""

from __future__ import annotations

import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from core.config import settings


def telegram_call(method: str, payload: dict) -> dict:
    endpoint = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed Telegram endpoint.
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Telegram webhook configuration failed") from exc
    if not result.get("ok"):
        raise RuntimeError(str(result.get("description", "Telegram rejected the request")))
    return result


def main() -> int:
    if not settings.telegram_bot_token:
        print("TELEGRAM_BOT_TOKEN is required", file=sys.stderr)
        return 2
    if not settings.telegram_public_base_url.startswith("https://"):
        print("TELEGRAM_PUBLIC_BASE_URL must be a public HTTPS URL", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", settings.telegram_webhook_secret):
        print("TELEGRAM_WEBHOOK_SECRET must be 16-256 letters, digits, underscores, or hyphens", file=sys.stderr)
        return 2

    webhook_url = urljoin(
        settings.telegram_public_base_url.rstrip("/") + "/",
        "api/v1/integrations/telegram/webhook",
    )
    telegram_call(
        "setWebhook",
        {
            "url": webhook_url,
            "secret_token": settings.telegram_webhook_secret,
            "allowed_updates": ["message"],
        },
    )
    telegram_call(
        "setMyCommands",
        {
            "commands": [
                {"command": "start", "description": "Open the Medihub patient assistant"},
                {"command": "register", "description": "Register as a new patient"},
                {"command": "link", "description": "Link an existing patient account"},
                {"command": "doctors", "description": "List available doctors"},
                {"command": "menu", "description": "Return to the main menu"},
                {"command": "new", "description": "Start a fresh private conversation"},
                {"command": "help", "description": "See natural-language examples"},
                {"command": "cancel", "description": "Cancel the current bot workflow"},
            ]
        },
    )
    print(f"Telegram webhook configured: {webhook_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
