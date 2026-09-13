import asyncio
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import HTTPException

from core.constants import SLOTS
from core.ai.tools import _safe_research_query
from core.ai.agent import CityCareAgent
from core.ai.schemas import AssistantChatRequest
from core.apis.dependencies import Principal
from core.controllers.clinic_controller import slots_for_date, validate_booking_date
from core.models.user_model import UserRole
from core.models.appointment_model import Symptom
from core.models.telegram_model import TelegramSession
from core.schemas.appointment_schema import AppointmentCreateRequest
from core.schemas.auth_schema import SignupRequest
from core.schemas.telegram_schema import TelegramUpdatePayload
from core.services.telegram_gateway import (
    TelegramGateway,
    classify_intent,
    extract_symptoms,
    parse_patient_date,
    patient_keyboard,
    telegram_session_key,
)
from core.services.live_voice import live_voice_instructions, token_payload


def test_clinic_has_twelve_fixed_half_hour_slots():
    assert len(SLOTS) == 12
    assert SLOTS[0] == "10:00"
    assert SLOTS[-1] == "19:30"


def test_booking_window_is_today_to_seven_days():
    validate_booking_date(date.today())
    validate_booking_date(date.today() + timedelta(days=7))
    with pytest.raises(HTTPException) as error:
        validate_booking_date(date.today() + timedelta(days=8))
    assert error.value.status_code == 400


def test_sunday_and_second_saturday_handbook_rules():
    # 2026-08-09 is Sunday; 2026-08-08 is the second Saturday.
    with pytest.raises(HTTPException):
        validate_booking_date(date(2026, 8, 9))
    assert slots_for_date(date(2026, 8, 8)) == SLOTS[:6]


def test_public_signup_cannot_supply_a_role():
    with pytest.raises(Exception):
        SignupRequest(
            first_name="Asha",
            last_name="Patel",
            email="asha@example.com",
            mobile_number="+919876543210",
            password="SecurePass123",
            role="DOCTOR",
        )


def test_appointment_reason_and_temperature_are_validated():
    with pytest.raises(Exception):
        AppointmentCreateRequest(
            appointment_date=date.today(),
            doctor_id="0" * 24,
            slot="10:00",
            reason="cough",
            temperature_f=120,
        )


def test_role_hierarchy_includes_the_four_citycare_roles():
    assert {role.value for role in UserRole} == {
        "PATIENT", "DOCTOR", "HOSPITAL_MANAGER", "SUPERADMIN",
    }


def test_live_voice_prompt_is_role_scoped_and_requires_booking_confirmation():
    patient = Principal(user_id="0" * 24, role=UserRole.PATIENT, first_name="Asha")
    instructions = live_voice_instructions(patient)
    assert "Asha" in instructions
    assert "explicit yes/no confirmation" in instructions
    assert "Never diagnose" in instructions
    assert "another patient's information" in instructions

    doctor = Principal(user_id="1" * 24, role=UserRole.DOCTOR, first_name="Arjun")
    doctor_instructions = live_voice_instructions(doctor)
    assert "signed-in doctor's schedule" in doctor_instructions
    assert "Do not accept appointments" in doctor_instructions
    assert "book_appointment" not in doctor_instructions


def test_live_voice_token_is_short_lived_and_single_use():
    issued_at = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
    payload = token_payload(issued_at)
    assert payload == {
        "uses": 1,
        "expireTime": "2026-08-26T12:20:00Z",
        "newSessionExpireTime": "2026-08-26T12:01:00Z",
    }


def test_public_research_query_rejects_obvious_contact_data():
    assert _safe_research_query("seasonal flu prevention for adults")
    with pytest.raises(ValueError):
        _safe_research_query("advice for patient Riya at +919876543210")


def test_telegram_gateway_understands_natural_patient_requests():
    assert classify_intent("Show me available doctors") == "doctors"
    assert classify_intent("Can you find a doctor for general medicine?") == "doctors"
    assert classify_intent("I need to book an appointment with Dr Patil") == "book"
    assert classify_intent("Has my doctor confirmed the booking?") == "appointments"
    assert classify_intent("Please show my latest prescription") == "prescriptions"
    assert classify_intent("Do you have wheelchair and WiFi facilities?") == "facilities"
    assert classify_intent("👨‍⚕️ Find doctors") == "doctors"
    assert classify_intent("📅 Book with Dr. Patil") == "book"
    assert classify_intent("🔎 Find by specialization") == "specialization_prompt"
    assert classify_intent("💬 Ask a health question") == "health_prompt"
    assert classify_intent("📝 Register to book") == "register"
    assert classify_intent("🔄 New conversation") == "new"
    assert classify_intent("clear chat") == "new"
    assert classify_intent("🏠 Main menu") == "menu"
    assert classify_intent("/start link_A1B2C3D4") == "link"


def test_telegram_keyboard_changes_with_patient_workflow():
    menu = patient_keyboard("READY", linked=True)
    assert any(button["text"] == "📅 Book appointment" for row in menu["keyboard"] for button in row)
    assert any(button["text"] == "🔄 New conversation" for row in menu["keyboard"] for button in row)

    slots = patient_keyboard(
        "BOOK_SLOT", linked=True, data={"available_slots": ["10:00", "10:30"]}
    )
    labels = [button["text"] for row in slots["keyboard"] for button in row]
    assert "10:00" in labels
    assert "10:30" in labels
    assert "❌ /cancel" in labels

    doctors = patient_keyboard(
        "BOOK_DOCTOR",
        linked=True,
        data={"doctor_options": ["👨‍⚕️ Dr. Asha Patel", "👨‍⚕️ Dr. Ravi Shah"]},
    )
    doctor_labels = [button["text"] for row in doctors["keyboard"] for button in row]
    assert "👨‍⚕️ Dr. Asha Patel" in doctor_labels
    assert "👨‍⚕️ Dr. Ravi Shah" in doctor_labels

    public_menu = patient_keyboard(
        "READY",
        linked=False,
        data={"ready_doctor_options": ["📅 Book with Dr. Asha Patel"]},
    )
    public_labels = [button["text"] for row in public_menu["keyboard"] for button in row]
    assert "📝 Register to book" in public_labels
    assert "📅 Book with Dr. Asha Patel" not in public_labels

    linked_menu = patient_keyboard(
        "READY",
        linked=True,
        data={"ready_doctor_options": ["📅 Book with Dr. Asha Patel"]},
    )
    linked_labels = [button["text"] for row in linked_menu["keyboard"] for button in row]
    assert "📅 Book with Dr. Asha Patel" in linked_labels


def test_unlinked_doctor_booking_starts_registration_and_preserves_request():
    message = TelegramUpdatePayload.model_validate(
        {
            "update_id": 10,
            "message": {
                "message_id": 3,
                "from": {"id": 88, "first_name": "Asha", "is_bot": False},
                "chat": {"id": 88, "type": "private"},
                "text": "📅 Book with Dr. Arjun Khan",
            },
        }
    ).message
    assert message is not None
    session = TelegramSession(
        session_key=telegram_session_key(88),
        telegram_user_id=88,
        telegram_chat_id=88,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    response = asyncio.run(TelegramGateway()._route(message, session, None))
    assert session.state == "REGISTER_FIRST"
    assert session.data["resume_booking"] == "📅 Book with Dr. Arjun Khan"
    assert "first name" in response.casefold()


def test_registration_resumes_the_exact_requested_doctor(monkeypatch):
    class FakeUsers:
        async def get_by_email(self, _email):
            return None

        async def create(self, user):
            return user

    gateway = TelegramGateway()
    gateway.users = FakeUsers()

    async def fake_create_link(_message, _user):
        return object()

    async def fake_booking_step(text, session, _link):
        assert text == "Dr. Arjun Khan"
        session.state = "BOOK_DATE"
        session.data = {"doctor_name": "Dr. Arjun Khan"}
        return "Choose a date"

    monkeypatch.setattr(gateway, "_create_link", fake_create_link)
    monkeypatch.setattr(gateway, "_booking_step", fake_booking_step)

    update = TelegramUpdatePayload.model_validate(
        {
            "update_id": 11,
            "message": {
                "message_id": 4,
                "from": {"id": 99, "first_name": "Asha", "is_bot": False},
                "chat": {"id": 99, "type": "private"},
                "text": "✅ I consent",
            },
        }
    )
    session = TelegramSession(
        session_key=telegram_session_key(99),
        telegram_user_id=99,
        telegram_chat_id=99,
        state="REGISTER_CONSENT",
        data={
            "resume_booking": "📅 Book with Dr. Arjun Khan",
            "first_name": "Asha",
            "last_name": "Patel",
            "email": "asha.telegram@example.com",
            "mobile_number": "+919876543210",
        },
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert update.message is not None
    response = asyncio.run(gateway._registration_step(update.message, session))
    assert session.state == "BOOK_DATE"
    assert session.data["doctor_name"] == "Dr. Arjun Khan"
    assert "registration complete" in response.casefold()
    assert "choose a date" in response.casefold()


def test_registration_rejects_existing_email_before_collecting_mobile():
    class ExistingUsers:
        async def get_by_email(self, _email):
            return object()

    gateway = TelegramGateway()
    gateway.users = ExistingUsers()
    update = TelegramUpdatePayload.model_validate(
        {
            "update_id": 12,
            "message": {
                "message_id": 5,
                "from": {"id": 100, "first_name": "Asha", "is_bot": False},
                "chat": {"id": 100, "type": "private"},
                "text": "existing@example.com",
            },
        }
    )
    session = TelegramSession(
        session_key=telegram_session_key(100),
        telegram_user_id=100,
        telegram_chat_id=100,
        state="REGISTER_EMAIL",
        data={"first_name": "Asha", "last_name": "Patel"},
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert update.message is not None
    response = asyncio.run(gateway._registration_step(update.message, session))
    assert session.state == "READY"
    assert session.data == {}
    assert "already belongs" in response.casefold()
    assert "connect telegram" in response.casefold()


def test_registration_accepts_plain_ten_digit_indian_mobile():
    gateway = TelegramGateway()
    update = TelegramUpdatePayload.model_validate(
        {
            "update_id": 13,
            "message": {
                "message_id": 6,
                "from": {"id": 101, "first_name": "Asha", "is_bot": False},
                "chat": {"id": 101, "type": "private"},
                "text": "9876543210",
            },
        }
    )
    session = TelegramSession(
        session_key=telegram_session_key(101),
        telegram_user_id=101,
        telegram_chat_id=101,
        state="REGISTER_MOBILE",
        data={
            "first_name": "Asha",
            "last_name": "Patel",
            "email": "new@example.com",
        },
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert update.message is not None
    asyncio.run(gateway._registration_step(update.message, session))
    assert session.state == "REGISTER_CONSENT"
    assert session.data["mobile_number"] == "+919876543210"


def test_telegram_booking_parses_dates_and_symptoms():
    current = date(2026, 8, 26)
    assert parse_patient_date("tomorrow", current) == date(2026, 8, 27)
    assert parse_patient_date("28-08-2026", current) == date(2026, 8, 28)
    assert parse_patient_date("not a date", current) is None
    assert set(extract_symptoms("Fever, cough and a severe headache")) == {
        Symptom.FEVER,
        Symptom.COUGH,
        Symptom.HEADACHE,
    }


def test_telegram_session_is_isolated_per_direct_chat():
    assert telegram_session_key(12345) == "agent:medihub:telegram:dm:12345"
    assert telegram_session_key(12345) != telegram_session_key(54321)


def test_telegram_session_accepts_dynamic_button_lists():
    session = TelegramSession(
        session_key=telegram_session_key(12345),
        telegram_user_id=12345,
        telegram_chat_id=12345,
        state="BOOK_DOCTOR",
        data={"doctor_options": ["Dr. Asha Patel", "Dr. Ravi Shah"]},
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert session.data["doctor_options"] == ["Dr. Asha Patel", "Dr. Ravi Shah"]


def test_telegram_update_contract_accepts_bot_api_from_alias():
    update = TelegramUpdatePayload.model_validate(
        {
            "update_id": 9,
            "message": {
                "message_id": 2,
                "from": {"id": 77, "first_name": "Asha", "is_bot": False},
                "chat": {"id": 77, "type": "private"},
                "text": "show my appointments",
            },
        }
    )
    assert update.message is not None
    assert update.message.from_user.id == 77
    assert update.message.text == "show my appointments"


def test_patient_voice_fallback_is_short_and_does_not_invent_directions():
    principal = Principal(user_id="0" * 24, role=UserRole.PATIENT, first_name="Asha")
    request = AssistantChatRequest(message="What dose is on my prescription?")
    result = asyncio.run(
        CityCareAgent().local_patient_voice_fallback(
            request,
            principal,
            has_matching_record=True,
            sources=["prescription.pdf"],
        )
    )
    assert result is not None
    assert "exact directions" in result["response"].casefold()
    assert "check with your doctor" in result["response"].casefold()
    assert result["sources"] == ["prescription.pdf"]


def test_patient_voice_fast_path_declines_unhandled_medical_question():
    principal = Principal(user_id="0" * 24, role=UserRole.PATIENT, first_name="Asha")
    request = AssistantChatRequest(message="Why does my knee hurt?")
    result = asyncio.run(
        CityCareAgent().local_patient_voice_fallback(
            request,
            principal,
            allow_generic=False,
        )
    )
    assert result is None


def test_doctor_identity_question_uses_instant_local_path():
    principal = Principal(user_id="0" * 24, role=UserRole.DOCTOR, first_name="Arjun")
    request = AssistantChatRequest(message="What is my name?")
    result = asyncio.run(
        CityCareAgent().local_operational_fallback(
            request,
            principal,
            allow_generic=False,
        )
    )
    assert result == {
        "response": "You're signed in as Arjun, with the doctor role.",
        "mode": "instant",
    }


@pytest.mark.parametrize(
    ("message", "expected_text"),
    [
        ("Tell me about yourself", "I'm CityCare Compass"),
        ("How are you?", "I'm ready and working, Arjun"),
        ("What can you do?", "check your schedule"),
    ],
)
def test_doctor_generic_conversation_uses_instant_local_path(message, expected_text):
    principal = Principal(user_id="0" * 24, role=UserRole.DOCTOR, first_name="Arjun")
    result = asyncio.run(
        CityCareAgent().local_operational_fallback(
            AssistantChatRequest(message=message),
            principal,
            allow_generic=False,
        )
    )
    assert result is not None
    assert expected_text in result["response"]
    assert result["mode"] == "instant"
