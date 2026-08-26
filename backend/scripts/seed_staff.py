"""Provision the first hospital manager or superadmin from the trusted CLI only."""

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
    role = UserRole(args.role)
    if existing:
        existing.role = role
        existing.is_active = True
        await users.save(existing)
        print(f"Promoted existing account {args.email} to {role.value}.")
        return
    await users.create(User(
        first_name=args.first_name,
        last_name=args.last_name,
        email=args.email.lower(),
        mobile_number=args.mobile,
        password_hash=hash_password(args.password),
        role=role,
    ))
    print(f"Created {role.value} account {args.email}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a CityCare staff account")
    parser.add_argument("--role", required=True, choices=["HOSPITAL_MANAGER", "SUPERADMIN"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--first-name", default="CityCare")
    parser.add_argument("--last-name", default="Admin")
    parser.add_argument("--mobile", default="+919876543210")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    try:
        asyncio.run(seed(arguments))
    finally:
        asyncio.run(close_mongo_connection())
