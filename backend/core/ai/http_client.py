"""Small async wrapper around the standard-library HTTPS client."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class TransportError(RuntimeError):
    """An upstream request could not be completed."""


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any]]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed provider URLs only.
            body = response.read().decode("utf-8")
            return int(response.status), json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return int(exc.code), json.loads(body) if body else {}
        except json.JSONDecodeError:
            return int(exc.code), {}
    except (URLError, OSError, json.JSONDecodeError) as exc:
        raise TransportError("The upstream service could not be reached") from exc


async def post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any]]:
    return await asyncio.to_thread(_post_json, url, payload, timeout)
