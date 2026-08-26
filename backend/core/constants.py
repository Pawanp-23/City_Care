"""Clinic facts and fixed menu values. They are configuration, not database rows."""

from __future__ import annotations

CLINIC = {
    "clinic_name": "CityCare Clinic",
    "doctor_name": "Dr. Pawan Patil",
    "qualification": "MBBS, MD (General Medicine)",
    "specialty": "General Physician",
    "city": "Nagpur",
    "morning_hours": "10:00 - 13:00",
    "evening_hours": "17:00 - 20:00",
    "slot_duration_minutes": 30,
    "booking_window_days": 7,
    "address": "14, Shivaji Nagar Road, Dharampeth, Nagpur - 440010",
    "reception_phone": "+91-712-2456789",
    "emergency_number": "108",
}

SLOTS = (
    "10:00", "10:30", "11:00", "11:30", "12:00", "12:30",
    "17:00", "17:30", "18:00", "18:30", "19:00", "19:30",
)

# The handbook's named fixed-date closure days. Movable holidays are deliberately
# not guessed; an administrator can add them through the deployment calendar.
FIXED_CLOSURE_DATES = {(1, 26), (5, 1), (8, 15), (12, 25)}
MORNING_SLOTS = SLOTS[:6]
