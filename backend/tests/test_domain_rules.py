from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from core.constants import SLOTS
from core.ai.tools import _safe_research_query
from core.controllers.clinic_controller import slots_for_date, validate_booking_date
from core.models.user_model import UserRole
from core.schemas.appointment_schema import AppointmentCreateRequest
from core.schemas.auth_schema import SignupRequest


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


def test_public_research_query_rejects_obvious_contact_data():
    assert _safe_research_query("seasonal flu prevention for adults")
    with pytest.raises(ValueError):
        _safe_research_query("advice for patient Riya at +919876543210")
