"""Telegram patient gateway with bounded sessions and a least-privilege tool surface.

The design borrows Hermes' useful gateway ideas (deterministic session keys,
durable routing state, pairing, bounded history, webhook verification, and
idempotent updates) without exposing Hermes' general terminal/file tools to
patients.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import re
import secrets
import string
from time import perf_counter
from datetime import UTC, date, datetime, timedelta

from bson import ObjectId
from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter, ValidationError
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from commons.auth import hash_password
from commons.logger import get_logger
from core.ai.agent import AssistantConfigurationError, AssistantUpstreamError, CityCareAgent
from core.ai.schemas import AssistantChatRequest, ChatHistoryMessage
from core.apis.dependencies import Principal
from core.config import settings
from core.controllers.appointment_controller import AppointmentController
from core.controllers.clinic_controller import ClinicController
from core.controllers.prescription_controller import PrescriptionController
from core.cruds.user_crud import UserCRUD
from core.database.database import engine
from core.integrations.telegram_client import (
    TelegramClient,
    TelegramConfigurationError,
    TelegramDeliveryError,
)
from core.models.appointment_model import Symptom
from core.models.telegram_model import (
    TelegramLinkCode,
    TelegramPatientLink,
    TelegramSession,
    TelegramUpdateReceipt,
)
from core.models.user_model import User, UserRole
from core.schemas.appointment_schema import AppointmentCreateRequest
from core.schemas.auth_schema import MOBILE_PATTERN, SignupRequest
from core.schemas.telegram_schema import TelegramMessagePayload, TelegramUpdatePayload
from core.services.handbook import answer_handbook_question
from core.services.prescription_rag import retrieve_patient_context

logger = get_logger(__name__)
EMAIL_ADAPTER = TypeAdapter(EmailStr)

READY = "READY"
REGISTER_FIRST = "REGISTER_FIRST"
REGISTER_LAST = "REGISTER_LAST"
REGISTER_EMAIL = "REGISTER_EMAIL"
REGISTER_MOBILE = "REGISTER_MOBILE"
REGISTER_CONSENT = "REGISTER_CONSENT"
BOOK_DOCTOR = "BOOK_DOCTOR"
BOOK_DATE = "BOOK_DATE"
BOOK_SLOT = "BOOK_SLOT"
BOOK_REASON = "BOOK_REASON"
BOOK_CONFIRM = "BOOK_CONFIRM"

HELP_TEXT = """💬 Talk to me naturally — the buttons are only shortcuts.

You can ask me to:
• find doctors or search by specialization
• book an appointment
• check doctor confirmation
• show your prescriptions
• explain hospital facilities
• discuss a health concern for general guidance

Account commands: /register, /link CODE, /menu, /new, /cancel, /help"""


def telegram_session_key(chat_id: int) -> str:
    return f"agent:medihub:telegram:dm:{chat_id}"


def _link_code_hash(code: str) -> str:
    return hmac.new(
        settings.jwt_secret.encode("utf-8"), code.strip().upper().encode("ascii"), hashlib.sha256
    ).hexdigest()


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def classify_intent(text: str) -> str:
    """Conservative natural-language router; clinical writes remain state-gated."""
    value = _normalized(text)
    if re.fullmatch(r"/start(?:@[A-Za-z0-9_]+)?\s+link_[A-Za-z0-9]{8}", text.strip()):
        return "link"
    if (
        text.startswith(("/new", "/clear", "/reset"))
        or value
        in {"clear chat", "fresh chat", "new chat", "new conversation", "start fresh", "reset chat"}
    ):
        return "new"
    if text.startswith("/start") or value in {"start", "hello", "hi", "hey"}:
        return "start"
    if text.startswith("/help") or value == "help":
        return "help"
    if text.startswith("/menu") or value in {"menu", "main menu", "home"}:
        return "menu"
    if text.startswith("/register") or value.startswith("register") or value == "sign up" or "create account" in value:
        return "register"
    if text.startswith("/link") or value in {"link account", "link existing account"}:
        return "link"
    if text.startswith("/cancel") or value in {"cancel", "stop", "never mind", "nevermind"}:
        return "cancel"
    if "prescription" in value or "medicine slip" in value:
        return "prescriptions"
    if "doctor confirm" in value or "booking status" in value:
        return "appointments"
    if "book" in value.split() and (
        "appointment" in value or "doctor" in value or "dr" in value.split()
    ):
        return "book"
    if "my appointment" in value:
        return "appointments"
    if value in {"ask a health question", "health question", "discuss health concern"}:
        return "health_prompt"
    if value in {"find by specialization", "search by specialization", "specializations", "specialties"}:
        return "specialization_prompt"
    words = set(value.split())
    if words.intersection(
        {"facility", "facilities", "service", "services", "wheelchair", "wifi", "lab", "laboratory", "parking"}
    ):
        return "facilities"
    doctor_discovery = any(
        phrase in value
        for phrase in (
            "list doctor", "show doctor", "find doctor", "find a doctor", "available doctor",
            "which doctor", "what doctor", "doctor available", "specialist",
        )
    )
    if doctor_discovery or text.startswith("/doctors"):
        return "doctors"
    return "chat"


def _reply_keyboard(rows: list[list[str]], placeholder: str) -> dict:
    return {
        "keyboard": [[{"text": label} for label in row] for row in rows],
        "resize_keyboard": True,
        "is_persistent": True,
        "input_field_placeholder": placeholder[:64],
    }


def patient_keyboard(state: str, linked: bool, data: dict | None = None) -> dict:
    """Return state-aware shortcuts; patients can always type free text instead."""
    data = data or {}
    workflow_navigation = ["❌ /cancel", "🏠 Main menu"]
    if state == REGISTER_CONSENT:
        return _reply_keyboard([["✅ I consent"], workflow_navigation], "Confirm or cancel")
    if state.startswith("REGISTER_"):
        return _reply_keyboard([workflow_navigation], "Type your answer")
    if state == BOOK_DOCTOR:
        doctor_options = [str(label)[:64] for label in data.get("doctor_options", [])]
        rows = [[label] for label in doctor_options]
        rows.extend([["🔎 Find by specialization"], workflow_navigation])
        return _reply_keyboard(rows, "Tap a doctor or type a specialty")
    if state == BOOK_DATE:
        return _reply_keyboard([["Today", "Tomorrow"], workflow_navigation], "Choose or type a date")
    if state == BOOK_SLOT:
        slots = [str(slot) for slot in data.get("available_slots", [])]
        rows = [slots[index:index + 3] for index in range(0, len(slots), 3)]
        rows.append(workflow_navigation)
        return _reply_keyboard(rows, "Choose an available time")
    if state == BOOK_REASON:
        return _reply_keyboard([workflow_navigation], "Describe the reason for your visit")
    if state == BOOK_CONFIRM:
        return _reply_keyboard([["✅ Confirm"], workflow_navigation], "Confirm the appointment")

    common = [
        ["👨‍⚕️ Find doctors", "🔎 Find by specialization"],
        ["🏥 Hospital facilities", "💬 Ask a health question"],
    ]
    ready_doctors = [str(label)[:64] for label in data.get("ready_doctor_options", [])]
    if linked and ready_doctors:
        common[0:0] = [[label] for label in ready_doctors]
    if linked:
        common.insert(1, ["📅 Book appointment", "🗓 My appointments"])
        common.insert(2, ["💊 My prescriptions"])
    else:
        common.insert(0, ["📝 Register to book", "🔗 Link existing account"])
    common.append(["🏠 Main menu", "🔄 New conversation"])
    return _reply_keyboard(common, "Ask Medihub anything…")


def parse_patient_date(value: str, today: date | None = None) -> date | None:
    today = today or date.today()
    normalized = _normalized(value)
    if normalized == "today":
        return today
    if normalized == "tomorrow":
        return today + timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    return None


def extract_symptoms(reason: str) -> list[Symptom]:
    aliases = {
        Symptom.FEVER: ("fever", "temperature"),
        Symptom.COUGH: ("cough",),
        Symptom.COLD: ("cold", "runny nose"),
        Symptom.BODYACHE: ("body ache", "bodyache"),
        Symptom.HEADACHE: ("headache", "head ache"),
    }
    lowered = reason.casefold()
    found = [symptom for symptom, terms in aliases.items() if any(term in lowered for term in terms)]
    return found or [Symptom.OTHER]


class TelegramGateway:
    def __init__(self, client: TelegramClient | None = None) -> None:
        self.client = client or TelegramClient()
        self._background_tasks: set[asyncio.Task[None]] = set()
        self.users = UserCRUD()
        self.clinic = ClinicController()
        self.appointments = AppointmentController()
        self.prescriptions = PrescriptionController()

    async def create_link_code(self, patient_id: str) -> dict:
        now = datetime.now(UTC)
        code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        await engine.get_collection(TelegramLinkCode).update_many(
            {"patient_id": ObjectId(patient_id), "used_at": None}, {"$set": {"used_at": now}}
        )
        record = TelegramLinkCode(
            patient_id=ObjectId(patient_id),
            code_hash=_link_code_hash(code),
            expires_at=now + timedelta(minutes=settings.telegram_link_code_minutes),
        )
        await engine.save(record)
        return {"code": code, "expires_at": record.expires_at.isoformat(), "command": f"/link {code}"}

    async def link_status(self, patient_id: str) -> dict:
        link = await engine.find_one(
            TelegramPatientLink,
            TelegramPatientLink.patient_id == ObjectId(patient_id),
            TelegramPatientLink.is_active == True,  # noqa: E712
        )
        if not link:
            return {"linked": False}
        return {
            "linked": True,
            "username": f"@{link.username}" if link.username else None,
            "linked_at": link.linked_at.isoformat(),
        }

    async def handle_update(self, update: TelegramUpdatePayload) -> None:
        if not await self._claim_update(update.update_id):
            return
        try:
            message = update.message
            if not message or not message.text or message.from_user.is_bot:
                return
            if message.chat.type != "private":
                await self.client.send_message(message.chat.id, "For privacy, Medihub patient services work only in a direct chat with this bot.")
                return
            started_at = perf_counter()
            intent = classify_intent(message.text.strip())
            # Typing is useful for AI chat, but it must not add a serial network
            # round trip before menus, doctors, dates, slots, or booking writes.
            if intent == "chat":
                task = asyncio.create_task(self._send_typing_safely(message.chat.id))
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)

            session = await self._session_for(message)
            link = await self._link_for(message.from_user.id)
            if link:
                session.patient_id = link.patient_id
            else:
                # A session must never retain authorization after its verified
                # Telegram link has been removed or deactivated.
                session.patient_id = None
            response = await self._route(message, session, link)
            # A new conversation intentionally leaves neither the previous
            # context nor the reset command in the model's future history.
            if classify_intent(message.text.strip()) != "new":
                await self._append_history(session, "user", message.text)
                await self._append_history(session, "model", response)
            await self._save_session(session)
            await self.client.send_message(
                message.chat.id,
                response,
                reply_markup=patient_keyboard(
                    session.state,
                    bool(link or session.patient_id),
                    session.data,
                ),
            )
            logger.info(
                "Telegram update completed | intent=%s latency_ms=%d",
                intent,
                round((perf_counter() - started_at) * 1000),
            )
        except Exception:
            # Clear the replay claim and give the patient an actionable recovery
            # message. The polling worker then continues with later updates.
            await engine.get_collection(TelegramUpdateReceipt).delete_one({"update_id": update.update_id})
            if update.message:
                try:
                    await self.client.send_message(
                        update.message.chat.id,
                        "⚠️ I couldn't complete that step. Please try once more, or send /cancel to restart.",
                    )
                except (TelegramDeliveryError, TelegramConfigurationError):
                    logger.warning("Could not deliver Telegram recovery message", exc_info=True)
            raise

    async def _send_typing_safely(self, chat_id: int) -> None:
        try:
            await self.client.send_typing(chat_id)
        except (TelegramDeliveryError, TelegramConfigurationError):
            logger.debug("Telegram typing indicator failed", exc_info=True)

    @staticmethod
    async def _claim_update(update_id: int) -> bool:
        try:
            await engine.get_collection(TelegramUpdateReceipt).insert_one(
                {"update_id": update_id, "processed_at": datetime.now(UTC)}
            )
            return True
        except DuplicateKeyError:
            return False

    async def _session_for(self, message: TelegramMessagePayload) -> TelegramSession:
        key = telegram_session_key(message.chat.id)
        now = datetime.now(UTC)
        session = await engine.find_one(TelegramSession, TelegramSession.session_key == key)
        expires = now + timedelta(hours=settings.telegram_session_ttl_hours)
        if not session:
            return TelegramSession(
                session_key=key,
                telegram_user_id=message.from_user.id,
                telegram_chat_id=message.chat.id,
                expires_at=expires,
            )
        if session.expires_at <= now:
            session.state, session.data, session.history = READY, {}, []
        session.telegram_user_id = message.from_user.id
        session.expires_at = expires
        session.updated_at = now
        return session

    async def _save_session(self, session: TelegramSession) -> None:
        session.updated_at = datetime.now(UTC)
        session.expires_at = session.updated_at + timedelta(hours=settings.telegram_session_ttl_hours)
        await engine.save(session)

    @staticmethod
    async def _append_history(session: TelegramSession, role: str, text: str) -> None:
        session.history.append({"role": role, "text": text[:1200]})
        session.history = session.history[-12:]

    @staticmethod
    async def _link_for(telegram_user_id: int) -> TelegramPatientLink | None:
        return await engine.find_one(
            TelegramPatientLink,
            TelegramPatientLink.telegram_user_id == telegram_user_id,
            TelegramPatientLink.is_active == True,  # noqa: E712
        )

    async def _route(
        self, message: TelegramMessagePayload, session: TelegramSession, link: TelegramPatientLink | None
    ) -> str:
        text = message.text.strip()
        intent = classify_intent(text)

        if intent == "cancel":
            session.state, session.data = READY, {}
            return "✅ Cancelled. Nothing was booked or changed. What would you like to do next?"
        if intent == "new":
            session.state, session.data, session.history = READY, {}, []
            return (
                "🔄 Fresh conversation started. I cleared our saved chat memory and cancelled any unfinished steps.\n\n"
                "Your secure patient-account link is still active. What would you like help with?"
            )
        if intent == "menu":
            session.state, session.data = READY, {}
            return "🏠 Main menu\n\nChoose an option below, or type your request naturally."
        if intent == "start":
            session.state, session.data = READY, {}
            status = (
                "Your patient account is securely linked."
                if link
                else "To use appointments and prescriptions, register here or securely link your existing account."
            )
            return f"👋 Hi {message.from_user.first_name}! I’m the Medihub Patient Assistant.\n\n{status}\n\n{HELP_TEXT}"
        if intent == "help":
            return HELP_TEXT
        if session.state.startswith("REGISTER_"):
            return await self._registration_step(message, session)
        if session.state.startswith("BOOK_"):
            return await self._booking_step(text, session, link)
        if intent == "health_prompt":
            return (
                "💬 Tell me what is bothering you, when it started, and how severe it feels. "
                "I can provide general guidance, but I cannot diagnose you or replace a doctor."
            )
        if intent == "specialization_prompt":
            doctors = await self.clinic.doctors()
            specialties = sorted({doctor["specialty"] for doctor in doctors if doctor.get("specialty")})
            if not specialties:
                return "No doctor specializations are listed right now. Please contact reception."
            return "🔎 Which specialization do you need?\n\n" + "\n".join(
                f"• {specialty}" for specialty in specialties
            ) + "\n\nType the specialization in your own words."
        if intent == "register":
            if link:
                return "This Telegram account is already linked to a Medihub patient."
            session.state, session.data = REGISTER_FIRST, {}
            return "📝 Let’s register you securely. What is your first name?\n\nYou can type /cancel at any time."
        if intent == "link":
            return await self._consume_link_code(message, session)
        if intent == "doctors":
            return await self._doctor_response(text, session)
        if intent == "facilities":
            result = answer_handbook_question(text)
            return f"🏥 Hospital information\n\n{result['response']}"
        if intent == "book" and not link:
            # Preserve the requested doctor while completing first-time
            # registration, then continue that same booking automatically.
            session.state = REGISTER_FIRST
            session.data = {"resume_booking": text}
            return (
                "🔒 Before I can book that doctor, I need to create and securely link your patient profile.\n\n"
                "What is your first name? You can use /cancel or Main menu at any time."
            )
        if intent in {"appointments", "prescriptions"} and not link:
            return (
                "🔒 This uses private patient data. Choose Register if you are new, or choose "
                "Link existing account and enter the secure code from your signed-in Medihub account."
            )
        if intent == "book":
            doctor_hint = re.split(r"\bwith\b", text, flags=re.IGNORECASE, maxsplit=1)
            if len(doctor_hint) == 2 and doctor_hint[1].strip():
                session.state, session.data = BOOK_DOCTOR, {}
                return await self._booking_step(doctor_hint[1].strip(), session, link)
            return await self._start_booking(session)
        if intent == "appointments":
            return await self._appointment_status(str(link.patient_id))
        if intent == "prescriptions":
            return await self._send_prescriptions(message.chat.id, str(link.patient_id))
        return await self._patient_chat(text, session, link, message.from_user.first_name)

    async def _doctor_response(self, query: str, session: TelegramSession | None = None) -> str:
        doctors = await self.clinic.doctors()
        if not doctors:
            return "No active doctors are listed right now. Please contact hospital reception."
        normalized = _normalized(query)
        generic = {
            "doctor", "doctors", "available", "list", "show", "find", "hospital",
            "specialist", "specialization", "which", "what", "are", "is", "can",
            "you", "based", "by", "on", "for", "me", "please", "find",
        }
        terms = [word for word in normalized.split() if word not in generic]
        if terms:
            needle = " ".join(terms)
            filtered = [
                doctor for doctor in doctors
                if needle in _normalized(f"{doctor['name']} {doctor['specialty']} {doctor['qualification']}")
                or all(term in _normalized(f"{doctor['name']} {doctor['specialty']}") for term in terms)
            ]
        else:
            filtered = doctors
        if not filtered:
            specialties = ", ".join(sorted({doctor["specialty"] for doctor in doctors}))
            return f"I couldn't find a matching doctor. Available specialties: {specialties or 'none listed'}."
        can_book = bool(session and session.patient_id)
        if session is not None and can_book:
            session.data["ready_doctor_options"] = [
                f"📅 Book with {doctor['name']}"[:64] for doctor in filtered
            ]
        elif session is not None:
            session.data.pop("ready_doctor_options", None)
        listing = "\n\n".join(
            f"{index}. {doctor['name']}\n   {doctor['specialty']} • {doctor['consultation_hours']}"
            for index, doctor in enumerate(filtered, start=1)
        )
        next_step = (
            "Tap a Book with… button below, or type something like “Book with Dr. Patil”."
            if can_book
            else "To continue, tap “Register to book” below, or securely link your existing Medihub account."
        )
        return f"👨‍⚕️ Available doctors\n\n{listing}\n\n{next_step}"

    async def _start_booking(self, session: TelegramSession) -> str:
        doctors = await self.clinic.doctors()
        if not doctors:
            session.state, session.data = READY, {}
            return "No active doctors are available for online booking right now. Please contact reception."
        session.state = BOOK_DOCTOR
        session.data = {"doctor_options": [f"👨‍⚕️ {doctor['name']}"[:64] for doctor in doctors]}
        return "👨‍⚕️ Choose a doctor below, or type a doctor name or specialization."

    async def _registration_step(self, message: TelegramMessagePayload, session: TelegramSession) -> str:
        value = message.text.strip()
        if session.state == REGISTER_FIRST:
            if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,59}", value):
                return "Please enter a valid first name using letters."
            session.data["first_name"] = value.strip().title()
            session.state = REGISTER_LAST
            return f"Thanks, {session.data['first_name']}! What is your last name?"
        if session.state == REGISTER_LAST:
            if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,59}", value):
                return "Please enter a valid last name using letters."
            session.data["last_name"] = value.strip().title()
            session.state = REGISTER_EMAIL
            return "What is your email address? If it already belongs to a Medihub account, use /link instead."
        if session.state == REGISTER_EMAIL:
            try:
                email = str(EMAIL_ADAPTER.validate_python(value)).casefold()
            except ValidationError:
                return "That email address is not valid. Please check it and try again."
            if await self.users.get_by_email(email):
                session.state, session.data = READY, {}
                return (
                    "🔐 That email already belongs to a Medihub patient. I won't create a duplicate record.\n\n"
                    "Sign in to the Medihub patient dashboard and choose Connect Telegram, or ask reception "
                    "to verify your identity if you cannot access the account."
                )
            session.data["email"] = email
            session.state = REGISTER_MOBILE
            return "Enter your Indian mobile number as +919876543210 or as a 10-digit number."
        if session.state == REGISTER_MOBILE:
            compact = value.replace(" ", "").replace("-", "")
            if re.fullmatch(r"[6-9]\d{9}", compact):
                compact = f"+91{compact}"
            elif re.fullmatch(r"91[6-9]\d{9}", compact):
                compact = f"+{compact}"
            if not MOBILE_PATTERN.fullmatch(compact):
                return "That number is invalid. Use +919876543210 or a valid 10-digit Indian mobile number."
            session.data["mobile_number"] = compact
            session.state = REGISTER_CONSENT
            return (
                f"Please confirm: register {session.data['first_name']} {session.data['last_name']} "
                f"with {session.data['email']} and {compact}, and link it to this Telegram account? "
                "Reply “I consent” to register or /cancel."
            )
        if session.state == REGISTER_CONSENT:
            if _normalized(value) not in {"i consent", "yes i consent", "confirm", "yes"}:
                return "Registration has not been submitted. Reply “I consent” or /cancel."
            password = secrets.token_urlsafe(24) + "Aa1"
            resume_booking = str(session.data.get("resume_booking", ""))
            signup_data = {
                key: session.data[key]
                for key in ("first_name", "last_name", "email", "mobile_number")
                if key in session.data
            }
            try:
                validated = SignupRequest(password=password, **signup_data)
            except Exception as exc:
                session.state = REGISTER_EMAIL
                return f"Those details could not be validated ({str(exc).splitlines()[0]}). Please enter your email again."
            if await self.users.get_by_email(str(validated.email)):
                session.state, session.data = READY, {}
                return "That email is already registered. For safety, create a Telegram link code from your signed-in Medihub account or ask reception to help; then use /link CODE."
            user = User(
                first_name=validated.first_name,
                last_name=validated.last_name,
                email=str(validated.email).casefold(),
                mobile_number=validated.mobile_number,
                password_hash=hash_password(password),
                role=UserRole.PATIENT,
            )
            try:
                await self.users.create(user)
                created_link = await self._create_link(message, user)
            except DuplicateKeyError:
                session.state, session.data = READY, {}
                return "That account already exists. Use the secure /link CODE flow instead."
            session.patient_id = user.id
            if resume_booking:
                doctor_hint = re.split(r"\bwith\b", resume_booking, flags=re.IGNORECASE, maxsplit=1)
                if len(doctor_hint) == 2 and doctor_hint[1].strip():
                    session.state, session.data = BOOK_DOCTOR, {}
                    next_step = await self._booking_step(
                        doctor_hint[1].strip(), session, created_link
                    )
                else:
                    next_step = await self._start_booking(session)
                return f"✅ Registration complete! Your patient profile is securely linked.\n\n{next_step}"
            session.state, session.data = READY, {}
            return "✅ Registration complete! This Telegram account is now linked. You can book appointments and view your prescriptions here."
        session.state, session.data = READY, {}
        return "Registration state was reset. Send /register to start again."

    async def _create_link(self, message: TelegramMessagePayload, patient: User) -> TelegramPatientLink:
        existing_patient_link = await engine.find_one(
            TelegramPatientLink, TelegramPatientLink.patient_id == patient.id, TelegramPatientLink.is_active == True  # noqa: E712
        )
        if existing_patient_link and existing_patient_link.telegram_user_id != message.from_user.id:
            raise HTTPException(status_code=409, detail="This patient account is linked to another Telegram user")
        existing_user_link = await self._link_for(message.from_user.id)
        if existing_user_link:
            if existing_user_link.patient_id != patient.id:
                raise HTTPException(status_code=409, detail="This Telegram user is linked to another patient")
            existing_user_link.telegram_chat_id = message.chat.id
            existing_user_link.username = message.from_user.username
            await engine.save(existing_user_link)
            return existing_user_link
        link = TelegramPatientLink(
            telegram_user_id=message.from_user.id,
            telegram_chat_id=message.chat.id,
            patient_id=patient.id,
            username=message.from_user.username,
        )
        await engine.save(link)
        return link

    async def _consume_link_code(self, message: TelegramMessagePayload, session: TelegramSession) -> str:
        value = message.text.strip()
        deep_link = re.fullmatch(
            r"/start(?:@[A-Za-z0-9_]+)?\s+link_([A-Za-z0-9]{8})",
            value,
        )
        parts = value.split(maxsplit=1)
        code = deep_link.group(1) if deep_link else (parts[1] if len(parts) == 2 else "")
        if not re.fullmatch(r"[A-Za-z0-9]{8}", code):
            return "Use /link followed by the 8-character code, for example: /link A1B2C3D4."
        now = datetime.now(UTC)
        raw_record = await engine.get_collection(TelegramLinkCode).find_one_and_update(
            {
                "code_hash": _link_code_hash(code),
                "used_at": None,
                "expires_at": {"$gt": now},
            },
            {"$set": {"used_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if not raw_record:
            return "That link code is invalid or expired. Generate a new one from your authenticated Medihub account."
        patient = await self.users.get_by_id(raw_record["patient_id"])
        if not patient or patient.role != UserRole.PATIENT or not patient.is_active:
            return "The linked patient account is unavailable. Contact hospital reception."
        try:
            await self._create_link(message, patient)
        except (HTTPException, DuplicateKeyError) as exc:
            # Restore the code only when pairing itself failed; no patient data
            # was disclosed, and the owner can retry from the correct account.
            await engine.get_collection(TelegramLinkCode).update_one(
                {"_id": raw_record["_id"], "used_at": now}, {"$set": {"used_at": None}}
            )
            if isinstance(exc, HTTPException):
                return str(exc.detail)
            return "This Telegram or patient account is already linked elsewhere."
        session.patient_id = patient.id
        return f"Linked securely. Welcome, {patient.first_name}. You can now use appointments and prescriptions here."

    async def _booking_step(
        self, text: str, session: TelegramSession, link: TelegramPatientLink | None
    ) -> str:
        if not link:
            session.state, session.data = READY, {}
            return "Link or register your patient account before booking."
        if session.state == BOOK_DOCTOR:
            doctors = await self.clinic.doctors()
            if not doctors:
                session.state, session.data = READY, {}
                return "No active doctors are available for online booking right now. Please contact reception."
            value = _normalized(text).removeprefix("dr ").strip()
            matches = [
                doctor for doctor in doctors
                if value in _normalized(f"{doctor['name']} {doctor['specialty']}")
                or all(term in _normalized(f"{doctor['name']} {doctor['specialty']}") for term in value.split())
            ]
            if len(matches) != 1:
                choices = matches or doctors
                session.data["doctor_options"] = [
                    f"👨‍⚕️ {item['name']}"[:64] for item in choices
                ]
                listing = "\n".join(f"• {item['name']} — {item['specialty']}" for item in choices)
                return f"Choose a doctor below, or type a more specific specialty:\n{listing}"
            doctor = matches[0]
            session.data.pop("doctor_options", None)
            session.data.update({"doctor_id": doctor["id"], "doctor_name": doctor["name"]})
            session.state = BOOK_DATE
            return f"📅 When should I check availability for {doctor['name']}? Choose below or type a date."
        if session.state == BOOK_DATE:
            selected = parse_patient_date(text)
            if not selected:
                return "I couldn't read that date. Use today, tomorrow, YYYY-MM-DD, or DD-MM-YYYY."
            try:
                availability = await self.clinic.free_slots(selected, session.data["doctor_id"])
            except HTTPException as exc:
                return str(exc.detail)
            if not availability["slots"]:
                return "No slots are free on that date. Please choose another date within the next seven days."
            session.data["appointment_date"] = selected.isoformat()
            session.data["available_slots"] = availability["slots"]
            session.state = BOOK_SLOT
            return f"⏰ Available times on {selected.strftime('%d %b %Y')} are shown below. Choose one or type the time you want."
        if session.state == BOOK_SLOT:
            match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
            if not match:
                return "Type a time in HH:MM format, such as 10:30."
            slot = f"{int(match.group(1)):02d}:{match.group(2)}"
            availability = await self.clinic.free_slots(
                datetime.strptime(session.data["appointment_date"], "%Y-%m-%d").date(),
                session.data["doctor_id"],
            )
            if slot not in availability["slots"]:
                return f"That slot is not available. Choose one of: {', '.join(availability['slots'])}."
            session.data["slot"] = slot
            session.data.pop("available_slots", None)
            session.state = BOOK_REASON
            return "🩺 Briefly describe the health problem or reason for the visit (at least 10 characters)."
        if session.state == BOOK_REASON:
            reason = " ".join(text.split())
            if len(reason) < 10:
                return "Please add a little more detail so the doctor knows the reason for the visit."
            session.data["reason"] = reason[:1000]
            session.state = BOOK_CONFIRM
            return (
                f"📋 Please confirm your appointment\n\n👨‍⚕️ Doctor: {session.data['doctor_name']}\n"
                f"📅 Date: {session.data['appointment_date']}\n⏰ Time: {session.data['slot']}\n"
                f"🩺 Reason: {session.data['reason']}\n\nChoose Confirm or /cancel. "
                "After booking, the doctor must accept the request."
            )
        if session.state == BOOK_CONFIRM:
            if _normalized(text) not in {"confirm", "yes", "yes confirm", "book it"}:
                return "Nothing has been booked yet. Reply “confirm” or /cancel."
            try:
                request = AppointmentCreateRequest(
                    appointment_date=datetime.strptime(session.data["appointment_date"], "%Y-%m-%d").date(),
                    doctor_id=session.data["doctor_id"],
                    slot=session.data["slot"],
                    reason=session.data["reason"],
                    symptoms=extract_symptoms(session.data["reason"]),
                )
                appointment = await self.appointments.create(request, str(link.patient_id))
            except HTTPException as exc:
                session.state, session.data = READY, {}
                return f"I couldn't book that appointment: {exc.detail}"
            session.state, session.data = READY, {}
            return (
                f"✅ Appointment requested\n\nReference: {appointment['id']}\n"
                f"Status: {appointment['status']} — waiting for the assigned doctor to confirm. "
                "I'll message you here when the doctor accepts it."
            )
        session.state, session.data = READY, {}
        return "Booking state was reset. Say “book an appointment” to start again."

    async def _appointment_status(self, patient_id: str) -> str:
        items = await self.appointments.my_appointments(patient_id)
        if not items:
            return "You have no appointments yet. Say “book an appointment” to start."
        lines = []
        for item in items[:8]:
            status_text = {
                "PENDING": "Waiting for doctor confirmation",
                "ACCEPTED": "Confirmed by doctor",
                "BOOKED": "Booked (legacy record)",
                "CANCELLED": "Cancelled",
            }.get(item["status"], item["status"])
            lines.append(f"• {item['appointment_date']} at {item['slot']} — {item['doctor_name']} — {status_text}")
        return "🗓 Your appointments\n\n" + "\n".join(lines)

    async def _send_prescriptions(self, chat_id: int, patient_id: str) -> str:
        items = await self.prescriptions.mine(patient_id)
        if not items:
            return "No prescriptions have been issued to your account yet. A doctor must accept the appointment and issue one first."
        for item in items[:3]:
            medicines = ", ".join(item["medicines"]) or "None listed"
            caption = (
                f"Prescription — {item['created_at'][:10]}\nDiagnosis: {item['diagnosis']}\n"
                f"Medicines: {medicines}\nInstructions: {item['instructions']}"
            )
            download = await self.prescriptions.download_url(item["id"], patient_id)
            if download["url"].startswith("data:application/pdf;base64,"):
                contents = base64.b64decode(download["url"].split(",", 1)[1])
                await self.client.send_document_bytes(chat_id, contents, download["filename"], caption)
            else:
                await self.client.send_document_url(chat_id, download["url"], caption)
        return f"I sent your {min(len(items), 3)} most recent prescription PDF(s) above."

    async def _patient_chat(
        self,
        question: str,
        session: TelegramSession,
        link: TelegramPatientLink | None,
        first_name: str,
    ) -> str:
        lowered = question.casefold()
        if any(term in lowered for term in ("chest pain", "can't breathe", "cannot breathe", "stroke", "heavy bleeding", "unconscious")):
            return "This could be an emergency. Medihub Telegram cannot assess emergencies—call ambulance 108 or go to the nearest emergency department now."

        # Deterministic clinic facts are faster and safer than an LLM round
        # trip. If the local handbook has an exact answer, use it immediately.
        local_handbook = answer_handbook_question(question)
        if not local_handbook["response"].startswith("I don't have that information"):
            return local_handbook["response"]

        context_parts: list[str] = []
        sources: list[str] = []
        patient_id = str(link.patient_id) if link else ""
        record_terms = {
            "prescription", "medicine", "medicines", "medication", "dose", "dosage",
            "diagnosis", "instruction", "instructions", "tablet", "capsule",
        }
        if patient_id and set(_normalized(question).split()).intersection(record_terms):
            chunks = await retrieve_patient_context(patient_id, question)
            if chunks:
                context_parts.append("\n\n".join(chunk.text for chunk in chunks))
                sources.extend(sorted({chunk.source for chunk in chunks}))

        history = [
            ChatHistoryMessage(role=item["role"], text=item["text"])
            for item in session.history[-10:]
            if item.get("role") in {"user", "model"} and item.get("text")
        ]
        principal = Principal(user_id=patient_id, role=UserRole.PATIENT, first_name=first_name)
        try:
            result = await CityCareAgent().patient_reply(
                AssistantChatRequest(message=question, history=history),
                principal,
                "\n\n".join(context_parts),
                sources,
            )
            return result["response"]
        except (AssistantConfigurationError, AssistantUpstreamError):
            local = answer_handbook_question(question)
            if not local["response"].startswith("I don't have that information"):
                return local["response"]
            return (
                "I can discuss general health information, but I can't diagnose your condition or prescribe treatment. "
                "Please describe the concern for your doctor, or say “book an appointment” to arrange a consultation."
            )


async def notify_appointment_accepted(patient_id: ObjectId, appointment_date: str, slot: str) -> None:
    """Best-effort notification; Telegram failure must never roll back clinical state."""
    if not settings.telegram_bot_token:
        return
    link = await engine.find_one(
        TelegramPatientLink,
        TelegramPatientLink.patient_id == patient_id,
        TelegramPatientLink.is_active == True,  # noqa: E712
    )
    if not link:
        return
    try:
        await TelegramClient().send_message(
            link.telegram_chat_id,
            f"Your appointment for {appointment_date} at {slot} has been confirmed by the doctor.",
        )
    except (TelegramConfigurationError, TelegramDeliveryError):
        logger.exception("Could not deliver Telegram appointment confirmation")


async def notify_prescription_issued(patient_id: ObjectId, prescription: dict) -> None:
    if not settings.telegram_bot_token:
        return
    link = await engine.find_one(
        TelegramPatientLink,
        TelegramPatientLink.patient_id == patient_id,
        TelegramPatientLink.is_active == True,  # noqa: E712
    )
    if not link:
        return
    try:
        await TelegramClient().send_message(
            link.telegram_chat_id,
            "Your doctor issued a new prescription. Send “show my prescriptions” to view the details and PDF securely.",
        )
    except (TelegramConfigurationError, TelegramDeliveryError):
        logger.exception("Could not deliver Telegram prescription notification")
