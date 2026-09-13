"""Secure Gemini Live session creation for the browser voice agent."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.apis.dependencies import Principal
from core.config import settings
from core.models.user_model import UserRole

TOKEN_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/auth_tokens"


def live_voice_instructions(principal: Principal) -> str:
    role = principal.role.value.lower().replace("_", " ")
    shared = f"""
You are CityCare Compass Live, the realtime voice assistant for CityCare Clinic in Nagpur.
You are speaking with {principal.first_name}, who is signed in with the {role} role.

VOICE STYLE:
- Speak naturally in English, Hindi, or Hinglish, matching the user.
- Keep each turn to one or two short spoken sentences unless the user asks for detail.
- Be calm, warm, direct, and professional. Never use markdown or read punctuation aloud.
- Stop immediately when interrupted and answer the new question.

MEDICAL SAFETY:
- Never diagnose, prescribe, change a medicine, or claim a symptom is harmless.
- For symptoms or medication concerns, provide only general information and recommend the appropriate clinician.
- If the user describes an emergency, tell them to call emergency services at 108 or go to the nearest emergency department.
- Never invent hospital data. Use a tool for doctors, facilities, schedules, appointments, prescriptions, or available slots.
- Never expose another patient's information.
""".strip()

    if principal.role == UserRole.PATIENT:
        role_rules = """
PATIENT WORKFLOW:
- You can list doctors, hospital facilities, the signed-in patient's appointments, prescriptions, and available slots.
- You may book an appointment only after repeating the doctor, date, time, and visit reason and receiving an explicit yes/no confirmation.
- The book_appointment tool must never be called unless confirmed is true and the user just explicitly confirmed.
- Do not cancel an appointment, download a file, or alter a prescription by voice.
- When a tool succeeds, clearly confirm the result. When it fails, explain the failure without pretending it worked.
""".strip()
    else:
        role_rules = """
DOCTOR WORKFLOW:
- You can read the signed-in doctor's schedule and clinic statistics, and list public doctors or facilities.
- Do not accept appointments, issue prescriptions, or change patient records by voice.
- Keep patient details limited to what the authorized schedule tool returns and what is necessary for the question.
""".strip()

    return f"{shared}\n\n{role_rules}\n\nOpen with: Hi {principal.first_name}, I'm CityCare Compass Live. How can I help?"


def token_payload(now: datetime | None = None) -> dict[str, Any]:
    issued_at = now or datetime.now(UTC)
    return {
        "uses": 1,
        "expireTime": (issued_at + timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
        "newSessionExpireTime": (issued_at + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
    }


def _create_token() -> tuple[int, dict[str, Any]]:
    request = Request(
        TOKEN_ENDPOINT,
        data=json.dumps(token_payload()).encode("utf-8"),
        headers={
            "x-goog-api-key": settings.gemini_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=8.0) as response:  # noqa: S310 - fixed provider URL.
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            return int(exc.code), json.loads(exc.read().decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return int(exc.code), {}
    except (URLError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Gemini Live could not be reached") from exc


async def create_live_voice_session(principal: Principal) -> dict[str, str]:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")
    status, payload = await asyncio.to_thread(_create_token)
    token = payload.get("name")
    if status >= 400 or not isinstance(token, str) or not token:
        raise RuntimeError("Gemini could not create a secure live voice session")
    return {
        "token": token,
        "model": settings.gemini_live_model,
        "instructions": live_voice_instructions(principal),
        "role": principal.role.value,
    }
