"""Create the controlled local CityCare demo accounts in one command.

This script is deliberately a CLI-only bootstrap tool. Public signup never
accepts a role, and passwords are not embedded in source code.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from commons.auth import hash_password
from core.cruds.user_crud import UserCRUD
from core.database.database import close_mongo_connection
from core.models.user_model import User, UserRole


@dataclass(frozen=True)
class DemoAccount:
    first_name: str
    last_name: str
    email: str
    mobile_number: str
    role: UserRole
    qualification: str | None = None
    specialty: str | None = None
    consultation_hours: str | None = None


ACCOUNTS = (
    DemoAccount("CityCare", "Admin", "admin@citycareclinic.com", "+919800000001", UserRole.SUPERADMIN),
    DemoAccount("Ananya", "Deshmukh", "manager@citycareclinic.com", "+919800000002", UserRole.HOSPITAL_MANAGER),
    DemoAccount("Pawan", "Patil", "doctor.patil@citycareclinic.com", "+919800000011", UserRole.DOCTOR, "MBBS, MD (General Medicine)", "General Physician", "10:00 - 13:00, 17:00 - 20:00"),
    DemoAccount("Neha", "Sharma", "doctor.sharma@citycareclinic.com", "+919800000012", UserRole.DOCTOR, "MBBS, DNB (Medicine)", "Internal Medicine", "10:00 - 13:00, 17:00 - 20:00"),
    DemoAccount("Arjun", "Khan", "doctor.khan@citycareclinic.com", "+919800000013", UserRole.DOCTOR, "MBBS, DCH", "Family Medicine", "10:00 - 13:00, 17:00 - 20:00"),
)


async def bootstrap(args: argparse.Namespace) -> None:
    users = UserCRUD()
    password_hash = hash_password(args.password)
    created = 0
    updated = 0

    for account in ACCOUNTS:
        user = await users.get_by_email(account.email)
        if user:
            user.first_name = account.first_name
            user.last_name = account.last_name
            user.mobile_number = account.mobile_number
            user.role = account.role
            user.qualification = account.qualification
            user.specialty = account.specialty
            user.consultation_hours = account.consultation_hours
            user.is_active = True
            if args.reset_passwords:
                user.password_hash = password_hash
            await users.save(user)
            updated += 1
            continue

        await users.create(User(
            first_name=account.first_name,
            last_name=account.last_name,
            email=account.email,
            mobile_number=account.mobile_number,
            password_hash=password_hash,
            role=account.role,
            qualification=account.qualification,
            specialty=account.specialty,
            consultation_hours=account.consultation_hours,
        ))
        created += 1

    print(f"CityCare demo accounts ready: {created} created, {updated} updated.")
    print("Superadmin: admin@citycareclinic.com")
    print("Manager: manager@citycareclinic.com")
    print("Doctors: doctor.patil@citycareclinic.com, doctor.sharma@citycareclinic.com, doctor.khan@citycareclinic.com")
    print("All accounts use the supplied password.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap local CityCare role-demo accounts")
    parser.add_argument("--password", required=True, help="Temporary local-demo password for every bootstrap account")
    parser.add_argument(
        "--reset-passwords",
        action="store_true",
        help="Also replace passwords on matching accounts (use for a local demo reset only)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    try:
        asyncio.run(bootstrap(arguments))
    finally:
        asyncio.run(close_mongo_connection())
