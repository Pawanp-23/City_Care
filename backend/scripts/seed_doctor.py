"""Create or promote a CityCare doctor without exposing a public role selector."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from commons.auth import hash_password
from core.cruds.user_crud import UserCRUD
from core.database.database import close_mongo_connection
from core.models.user_model import User, UserRole


async def seed(args: argparse.Namespace) -> None:
    users = UserCRUD()
    existing = await users.get_by_email(args.email.lower())
    if existing:
        existing.role = UserRole.DOCTOR
        existing.qualification = args.qualification
        existing.specialty = args.specialty
        existing.consultation_hours = args.consultation_hours
        existing.is_active = True
        await users.save(existing)
        print(f"Promoted existing account {args.email} to DOCTOR.")
        return

    doctor = User(
        first_name=args.first_name,
        last_name=args.last_name,
        email=args.email.lower(),
        mobile_number=args.mobile,
        password_hash=hash_password(args.password),
        role=UserRole.DOCTOR,
        qualification=args.qualification,
        specialty=args.specialty,
        consultation_hours=args.consultation_hours,
    )
    await users.create(doctor)
    print(f"Created doctor account {args.email}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a CityCare doctor account")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--first-name", default="Pawan")
    parser.add_argument("--last-name", default="Patil")
    parser.add_argument("--mobile", default="+919876543210")
    parser.add_argument("--qualification", default="MBBS, MD (General Medicine)")
    parser.add_argument("--specialty", default="General Physician")
    parser.add_argument("--consultation-hours", default="10:00 - 13:00, 17:00 - 20:00")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    try:
        asyncio.run(seed(arguments))
    finally:
        asyncio.run(close_mongo_connection())
