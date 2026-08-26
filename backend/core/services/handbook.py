"""Grounded, local answers for the supplied CityCare patient handbook.

This is intentionally deterministic: clinic guidance must not require a third
party LLM or invent facts when a question falls outside the handbook.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class HandbookEntry:
    section: str
    answer: str
    keywords: tuple[str, ...]
    policy: str | None = None


ENTRIES = (
    HandbookEntry("Consultation hours", "CityCare is open Monday to Saturday from 10:00-13:00 and 17:00-20:00. It is closed on Sundays, listed public holidays, and on the second Saturday evening session.", ("open", "hours", "sunday", "closed", "holiday", "second saturday", "time"), "POL-HRS-00"),
    HandbookEntry("Appointments", "Online appointments can be booked up to seven days ahead. Walk-ins are only accommodated when a slot is free, usually 12:30-13:00 or 19:30-20:00; booked patients take priority.", ("book", "booking", "advance", "walk", "walkin", "walk-in", "appointment", "slot"), "POL-APT-01"),
    HandbookEntry("Late arrival and cancellation", "For an in-person appointment, cancel or reschedule at least two hours before the time. More than 10 minutes late may lose the slot; more than 15 minutes late is a missed appointment that must be rebooked. Three no-shows in six months suspend online booking for 30 days, though telephone and in-person booking remain available.", ("cancel", "reschedule", "late", "missed", "no-show", "no show"), "POL-CAN-02"),
    HandbookEntry("Fees and payment", "A first consultation costs INR 600 and a follow-up within 15 days costs INR 300. CityCare accepts cash, UPI, and debit or credit cards; cheques are not accepted. There is no cashless insurance facility.", ("fee", "cost", "price", "payment", "insurance", "cashless", "follow-up", "consultation"), "POL-FEE-04"),
    HandbookEntry("Teleconsultation", "A video teleconsultation costs INR 400, lasts up to 20 minutes, and may be cancelled up to 30 minutes before the appointment. It is not suitable for emergencies, pregnancy-related complaints, or a first undiagnosed complaint.", ("teleconsultation", "tele consultation", "video", "remote", "online consult"), "POL-TEL-03"),
    HandbookEntry("Services", "CityCare provides general medicine for people aged 13 and over, chronic-condition follow-up, preventive checks, adult vaccination, minor procedures, ECG, and basic vital monitoring. It does not provide emergency care, admissions, surgery, obstetric, paediatric-under-13, or psychiatric care.", ("service", "treat", "child", "paediatric", "emergency", "surgery", "physiotherapy", "dental", "cardiology")),
    HandbookEntry("Laboratory and imaging", "Sanjeevani Diagnostics collects samples in the building Monday-Saturday, 07:30-10:30; fasting samples must be given before 09:30. X-ray, ultrasound, and CT are not available in the building.", ("blood", "test", "lab", "sample", "fasting", "x-ray", "xray", "ultrasound", "ct", "imaging")),
    HandbookEntry("Vaccination", "Adult vaccinations are by morning appointment. Td is one dose every 10 years. Hepatitis B and HPV require at least 48 hours advance notice, and patients are observed for 20 minutes afterwards.", ("vaccine", "vaccination", "tetanus", "td", "hepatitis", "hpv", "typhoid", "flu"), "POL-VAC-07"),
    HandbookEntry("Emergency", "CityCare is not an emergency facility. For an emergency, call ambulance service 108 or go to a hospital emergency department.", ("emergency", "ambulance", "chest pain", "breathless", "bleeding", "stroke", "urgent"), "POL-EMG-06"),
    HandbookEntry("Records and privacy", "Patients can request their own records: a digital copy is free and provided within three working days; a physical copy costs INR 100. Records are retained for five years from the last visit and are not shared without written consent except where law requires it.", ("record", "privacy", "report", "copy", "consent", "data", "medical record"), "POL-REC-05"),
    HandbookEntry("Facilities and visitors", "One attendant is allowed; two are allowed for elderly or disabled patients. Step-free access, an accessible toilet, a wheelchair on request, and guest WiFi CityCare_Guest are available. Photography and video recording are not allowed.", ("attendant", "wheelchair", "disabled", "elderly", "wifi", "parking", "access", "photograph", "visitor")),
    HandbookEntry("Contact", "Reception: +91-712-2456789 (09:30-13:30 and 16:30-20:30 on working days). Appointment WhatsApp: +91-98765-00001. General email: care@citycareclinic.in. Billing and insurance: billing@citycareclinic.in.", ("contact", "phone", "telephone", "whatsapp", "email", "reception", "billing")),
)


def answer_handbook_question(question: str) -> dict:
    lowered = question.casefold()
    unsupported = {
        "physio": "The CityCare Patient Handbook does not say that CityCare offers physiotherapy.",
        "dental": "The CityCare Patient Handbook does not mention a dental clinic.",
        "cardiology": "The CityCare Patient Handbook does not list cardiology consultations or fees.",
    }
    for term, response in unsupported.items():
        if term in lowered:
            return {"response": response, "sources": []}
    tokens = set(re.findall(r"[a-z0-9]+", question.casefold()))
    ranked = []
    for entry in ENTRIES:
        key_terms = set(re.findall(r"[a-z0-9]+", " ".join(entry.keywords).casefold()))
        score = len(tokens & key_terms)
        if score:
            ranked.append((score, entry))
    if not ranked:
        return {"response": "I don't have that information in the CityCare Patient Handbook. Please ask reception for guidance.", "sources": []}
    _, entry = max(ranked, key=lambda item: item[0])
    source = entry.section + (f" ({entry.policy})" if entry.policy else "")
    return {"response": entry.answer, "sources": [source]}
