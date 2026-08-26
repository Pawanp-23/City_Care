"""Gemini function-calling loop, deliberately separate from FastAPI and database code."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any
from urllib.parse import urlencode

from commons.logger import get_logger
from core.ai.http_client import TransportError, post_json
from core.ai.schemas import AssistantChatRequest
from core.ai.tools import TOOL_DECLARATIONS, ToolContext, run_tool
from core.apis.dependencies import Principal
from core.config import settings

logger = get_logger(__name__)


class AssistantConfigurationError(RuntimeError):
    """Raised when the administrator has not supplied a Gemini key."""


class AssistantUpstreamError(RuntimeError):
    """Raised only for a non-recoverable Gemini response."""


def _system_instruction(principal: Principal) -> str:
    return f"""
You are CityCare Compass — the smart, friendly assistant built into CityCare Clinic, Nagpur.
You're talking to {principal.first_name}, a {principal.role.value.lower().replace('_', ' ')} here at the clinic.

Personality:
- You're like that knowledgeable colleague everyone loves — warm, sharp, and easy to talk to.
- Keep replies short, conversational, and clear. No walls of text.
- Use natural contractions ("you've", "I'll", "here's") and a light, upbeat tone.
- If something's good news, say so. If it's quiet today, that's worth a smile.
- Don't start every message with "Certainly!" or "Of course!" — just get to the point naturally.

Capabilities:
- Pull up real schedule, patient counts, and clinic stats from CityCare's live data.
- Research general public-health topics for clinical context (never patient-identifying details).
- Guide staff to the right workflow when something needs a human touch.

Boundaries (keep these firm but friendly):
- Don't invent data — always use a tool if the answer needs live clinic info.
- Don't diagnose, prescribe, or assess urgency — that's the doctor's job.
- Appointments can't be created or changed by chat — point people to the booking workflow.
- Keep patient data confidential — share only what this user is authorized to see.
""".strip()


def _voice_system_instruction(principal: Principal) -> str:
    """Ultra-short prompt for voice responses — optimised for ears, not eyes."""
    return f"""
You are CityCare Compass, the voice assistant for CityCare Clinic, Nagpur.
You're speaking out loud with {principal.first_name}, a {principal.role.value.lower().replace('_', ' ')}.

Critical rules for voice:
- Reply in ONE or TWO short spoken sentences only. Never more.
- Sound warm and natural — like a helpful colleague, not a call-centre bot.
- No bullet points, markdown, lists, or asterisks — this is spoken audio.
- Use contractions freely: "you've", "I'll", "here's", "that's".
- If you don't know something, say so briefly and suggest where to find it.
- Never diagnose, prescribe, or assess urgency.
""".strip()


def _patient_voice_system_instruction(principal: Principal, context: str) -> str:
    return f"""
You are CityCare Compass, the friendly voice assistant at CityCare Clinic, Nagpur.
You're speaking with {principal.first_name}, one of the clinic's patients.

Patient context (use only when directly relevant):
{context if context else "No records found for this question."}

Critical rules for voice:
- Reply in ONE or TWO natural spoken sentences. Never more.
- Warm, clear, and reassuring — like a caring clinic friend.
- No bullet points, markdown, or lists — spoken audio only.
- For medical concerns, say: "I'd check that one with your doctor."
- If the question doesn't relate to the context, just chat naturally.
""".strip()




def _patient_system_instruction(principal: Principal, context: str, sources: list[str]) -> str:
    sources_str = ", ".join(sources) if sources else "none"
    return f"""
You are CityCare Compass — a friendly, caring assistant at CityCare Clinic, Nagpur.
You're chatting with {principal.first_name}, one of our patients.

Personality:
- Think of yourself as a knowledgeable clinic friend — warm, reassuring, and easy to understand.
- Keep it short and human. No medical jargon unless you explain it simply.
- Use a friendly, conversational tone. Contractions are fine. Empathy is great.
- For greetings or small talk, just chat naturally — don't immediately dump medical info.
- Don't be robotic. "Here's what I found" beats "The records indicate the following."

Patient records available for {principal.first_name} (use only when relevant to the question):
--- RECORDS START ---
{context if context else "No records found for this question."}
--- RECORDS END ---
Source(s): {sources_str}

Boundaries (always):
- Only refer to the records above when the patient's question genuinely relates to them.
- Never invent, guess, or fill in details not present in the records.
- For any medical concern — symptoms, dosage worries, side effects — always say something like "best to check with Dr. Patil on that one" rather than advising directly.
- Appointments can't be booked or changed here — guide them to the booking page.
- Never share or hint at another patient's data.
""".strip()


def _content_from_history(request: AssistantChatRequest) -> list[dict[str, Any]]:
    contents = [
        {"role": item.role, "parts": [{"text": item.text.strip()}]}
        for item in request.history[-12:]
        if item.text.strip()
    ]
    contents.append({"role": "user", "parts": [{"text": request.message.strip()}]})
    return contents


def _response_text(content: dict[str, Any]) -> str:
    return "".join(
        str(part.get("text", ""))
        for part in content.get("parts", [])
        if isinstance(part, dict) and part.get("text")
    ).strip()


def _gemini_configuration_error(response_status: int, body: dict[str, Any]) -> str | None:
    """Return a safe actionable message without reflecting provider payloads to users."""
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    provider_status = str(error.get("status", "")).upper()
    if response_status in {400, 401, 403}:
        logger.warning(
            "CityCareAgent.reply | Gemini configuration rejected | http=%s provider_status=%s",
            response_status,
            provider_status or "unknown",
        )
        return (
            "Gemini rejected the clinic configuration. Verify GEMINI_API_KEY is the plain key "
            "value (without GOOGLE_API_KEY=), verify GEMINI_MODEL, then restart the API."
        )
    return None


async def _post_with_retry(
    endpoint: str, payload: dict[str, Any], timeout: float, max_retries: int = 1
) -> tuple[int, dict[str, Any]]:
    """POST to Gemini. Retries once on 429 with a short 2s delay."""
    for attempt in range(max_retries + 1):
        try:
            status, body = await post_json(endpoint, payload, timeout)
        except TransportError:
            raise
        if status != 429 or attempt == max_retries:
            return status, body
        logger.warning("Gemini 429 rate-limit (attempt %d/%d), retrying in 2s…", attempt + 1, max_retries + 1)
        await asyncio.sleep(2.0)
    return status, body  # unreachable


class CityCareAgent:
    """A maximum-four-pass Gemini agent loop with role-scoped server tools."""

    async def reply(self, request: AssistantChatRequest, principal: Principal) -> dict[str, Any]:
        if not settings.gemini_api_key:
            raise AssistantConfigurationError("The CityCare assistant is not configured. Add GEMINI_API_KEY on the API server.")

        contents = _content_from_history(request)
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": _system_instruction(principal)}]},
            "contents": contents,
            "tools": [{"functionDeclarations": TOOL_DECLARATIONS}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 550},
        }
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?{urlencode({'key': settings.gemini_api_key})}"
        )
        tools_used: list[str] = []
        context = ToolContext(principal=principal)

        for _ in range(4):
            try:
                response_status, body = await _post_with_retry(endpoint, payload, 35.0)
            except TransportError as exc:
                logger.warning("CityCareAgent.reply | Gemini network failure")
                raise AssistantUpstreamError("The assistant service could not be reached. Please try again.") from exc

            if response_status >= 400:
                configuration_error = _gemini_configuration_error(response_status, body)
                if configuration_error:
                    raise AssistantConfigurationError(configuration_error)
                logger.warning("CityCareAgent.reply | Gemini status=%s", response_status)
                if response_status == 429:
                    raise AssistantUpstreamError(
                        "I'm a little busy right now — Gemini hit its rate limit. Give it a moment and try again!"
                    )
                raise AssistantUpstreamError("The assistant is temporarily unavailable. Please try again shortly.")
            candidates = body.get("candidates") or []
            if not candidates or not isinstance(candidates[0].get("content"), dict):
                raise AssistantUpstreamError("The assistant returned no usable response. Please try again.")

            model_content = candidates[0]["content"]
            calls = [
                part.get("functionCall")
                for part in model_content.get("parts", [])
                if isinstance(part, dict) and isinstance(part.get("functionCall"), dict)
            ]
            if not calls:
                text = _response_text(model_content)
                if text:
                    return {"response": text, "tools_used": tools_used}
                raise AssistantUpstreamError("The assistant did not provide a response. Please try again.")

            contents.append(model_content)
            function_responses = []
            for call in calls[:3]:
                name = str(call.get("name", ""))
                arguments = call.get("args") if isinstance(call.get("args"), dict) else {}
                result = await run_tool(name, arguments, context)
                tools_used.append(name)
                function_responses.append(
                    {"functionResponse": {"name": name, "response": {"result": result}}}
                )
            contents.append({"role": "user", "parts": function_responses})
            payload["contents"] = contents

        raise AssistantUpstreamError("The assistant needed too many tool steps. Please ask a narrower question.")

    async def patient_reply(
        self,
        request: AssistantChatRequest,
        principal: Principal,
        context: str,
        sources: list[str],
    ) -> dict[str, Any]:
        """Gemini-powered patient Q&A grounded in retrieved prescription/handbook context."""
        if not settings.gemini_api_key:
            raise AssistantConfigurationError("The CityCare assistant is not configured. Add GEMINI_API_KEY on the API server.")

        contents = _content_from_history(request)
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": _patient_system_instruction(principal, context, sources)}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 450},
        }
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?{urlencode({'key': settings.gemini_api_key})}"
        )
        try:
            response_status, body = await _post_with_retry(endpoint, payload, 30.0)
        except TransportError as exc:
            raise AssistantUpstreamError("The assistant service could not be reached. Please try again.") from exc

        if response_status >= 400:
            config_err = _gemini_configuration_error(response_status, body)
            if config_err:
                raise AssistantConfigurationError(config_err)
            if response_status == 429:
                raise AssistantUpstreamError(
                    "I'm a little busy right now — Gemini hit its rate limit. Give it a moment and try again!"
                )
            raise AssistantUpstreamError("The assistant is temporarily unavailable. Please try again shortly.")

        candidates = body.get("candidates") or []
        if not candidates or not isinstance(candidates[0].get("content"), dict):
            raise AssistantUpstreamError("The assistant returned no usable response. Please try again.")

        text = _response_text(candidates[0]["content"])
        if not text:
            raise AssistantUpstreamError("The assistant did not provide a response. Please try again.")

        result: dict[str, Any] = {"response": text}
        if sources:
            result["sources"] = sources
        return result

    async def voice_reply(
        self,
        request: AssistantChatRequest,
        principal: Principal,
        context: str = "",
        sources: list[str] | None = None,
        is_patient: bool = False,
    ) -> dict[str, Any]:
        """Low-latency voice response — 1-2 spoken sentences, no tool-calling loop."""
        if not settings.gemini_api_key:
            raise AssistantConfigurationError("The CityCare assistant is not configured.")

        sys = (
            _patient_voice_system_instruction(principal, context)
            if is_patient
            else _voice_system_instruction(principal)
        )
        contents = _content_from_history(request)
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": sys}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 70},
        }
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?{urlencode({'key': settings.gemini_api_key})}"
        )
        try:
            # Voice: NO retries — fail fast to local fallback. Speed > resilience here.
            status, body = await post_json(endpoint, payload, 12.0)
        except TransportError as exc:
            raise AssistantUpstreamError("Couldn't reach the assistant. Try again!") from exc

        if status >= 400:
            config_err = _gemini_configuration_error(status, body)
            if config_err:
                raise AssistantConfigurationError(config_err)
            if status == 429:
                raise AssistantUpstreamError("I'm a little busy — try again in a moment!")
            raise AssistantUpstreamError("The assistant is temporarily unavailable.")

        candidates = body.get("candidates") or []
        if not candidates or not isinstance(candidates[0].get("content"), dict):
            raise AssistantUpstreamError("Sorry, I didn't catch that. Try again?")

        text = _response_text(candidates[0]["content"])
        if not text:
            raise AssistantUpstreamError("Sorry, no response. Please try again.")

        result: dict[str, Any] = {"response": text}
        if sources:
            result["sources"] = sources
        return result

    async def local_operational_fallback(

        self, request: AssistantChatRequest, principal: Principal
    ) -> dict[str, Any] | None:
        """Keep essential doctor workflows available during an AI-provider outage.

        Handles greetings and common operational queries without Gemini.
        Never poses as Gemini — responses are clearly from local CityCare data.
        """
        message = request.message.casefold().strip()
        context = ToolContext(principal=principal)
        today = date.today().isoformat()
        name = principal.first_name

        # ── Instant replies (no tool calls needed) ─────────────────────────
        greetings = ("hi", "hii", "hello", "hey", "good morning", "good evening", "good afternoon", "sup", "howdy", "helo", "hai")
        if message in greetings or any(message.startswith(g + " ") for g in greetings) or message in ("hii!", "hi!", "hello!", "hey!"):
            return {"response": f"Hey {name}! 👋 I'm CityCare Compass. I'm in offline mode right now but I can still check your schedule and clinic stats. What do you need?", "mode": "instant"}

        thanks = ("thanks", "thank you", "thank u", "thx", "ty", "great", "ok", "okay", "cool", "got it", "nice")
        if message in thanks or any(message.startswith(t) for t in thanks):
            return {"response": f"Anytime, {name}! 😊 Let me know if there's anything else.", "mode": "instant"}

        # Schedule
        if any(term in message for term in ("schedule", "today's appointments", "todays appointments", "my appointments", "who do i have")):
            data = await run_tool("get_my_schedule", {"date": today}, context)
            appointments = data.get("appointments") if isinstance(data, dict) else None
            if not isinstance(appointments, list):
                return None
            if not appointments:
                text = f"Your schedule for today ({today}) is all clear — no booked appointments. Enjoy the calm! 😊"
            else:
                entries = ", ".join(
                    f"{item['slot']} — {item['patient_name']}" for item in appointments[:8]
                )
                text = f"Here's your schedule for today ({today}): {entries}."
            return {
                "response": text,
                "tools_used": ["get_my_schedule"],
                "mode": "local_operational_fallback",
            }

        # Stats / counts
        if any(term in message for term in ("how many", "visit", "patient count", "appointment count", "statistics", "stats", "patients today")):
            data = await run_tool("get_clinic_statistics", {}, context)
            if not isinstance(data, dict) or data.get("error"):
                return None
            return {
                "response": (
                    f"Here's the quick snapshot, {name}: you've got {data.get('todays_visits', 0)} visit(s) today "
                    f"and {data.get('upcoming_visits', 0)} upcoming. CityCare has "
                    f"{data.get('total_registered_patients', 0)} active patient accounts total."
                ),
                "tools_used": ["get_clinic_statistics"],
                "mode": "local_operational_fallback",
            }

        # Generic fallback for anything else — don't leave user stranded
        return {
            "response": f"Hey {name}, I'm in offline mode at the moment (Gemini's rate limit). I can still check your schedule or clinic stats — just ask! For anything else, try again in a minute.",
            "mode": "local_operational_fallback",
        }
