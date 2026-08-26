"""Hospital-wide staff administration. Authorization decisions stay here, not in routes."""

from __future__ import annotations

import asyncio

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from commons.auth import hash_password
from commons.logger import get_logger
from core.apis.dependencies import Principal
from core.constants import CLINIC
from core.cruds.appointment_crud import AppointmentCRUD
from core.cruds.user_crud import UserCRUD
from core.models.user_model import User, UserRole
from core.schemas.management_schema import AccountStatusRequest, CreateUserRequest

logger = get_logger(__name__)


def serialize_managed_user(user: User) -> dict:
    """Return contact data only to authorized hospital staff."""
    return {
        "id": str(user.id),
        "name": f"{user.first_name} {user.last_name}".strip(),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "mobile_number": user.mobile_number,
        "role": user.role.value,
        "qualification": user.qualification,
        "specialty": user.specialty,
        "consultation_hours": user.consultation_hours,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
    }


class ManagementController:
    def __init__(
        self,
        users: UserCRUD | None = None,
        appointments: AppointmentCRUD | None = None,
    ) -> None:
        self.users = users or UserCRUD()
        self.appointments = appointments or AppointmentCRUD()

    async def overview(self) -> dict:
        """Operational numbers for the single CityCare hospital."""
        from datetime import date

        today = date.today().isoformat()
        patients, doctors, managers, todays_visits, upcoming_visits = await asyncio.gather(
            self.users.count_active_by_role(UserRole.PATIENT),
            self.users.count_active_by_role(UserRole.DOCTOR),
            self.users.count_active_by_role(UserRole.HOSPITAL_MANAGER),
            self.appointments.count_booked_for_date(today),
            self.appointments.count_upcoming_bookings(today),
        )
        return {
            "hospital": {"id": "citycare-nagpur", "name": CLINIC["clinic_name"], "city": CLINIC["city"]},
            "active_patients": patients,
            "active_doctors": doctors,
            "active_managers": managers,
            "todays_visits": todays_visits,
            "upcoming_visits": upcoming_visits,
        }

    async def users_by_role(self, role: UserRole, principal: Principal) -> list[dict]:
        if principal.role == UserRole.HOSPITAL_MANAGER and role not in {
            UserRole.PATIENT,
            UserRole.DOCTOR,
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers may only view patient and doctor accounts",
            )
        users = await self.users.list_by_role(role)
        return [serialize_managed_user(user) for user in users]

    async def create_user(self, request: CreateUserRequest, principal: Principal) -> dict:
        """Provision only roles the current staff member is entitled to create."""
        target = request.role
        allowed = (
            {UserRole.PATIENT, UserRole.DOCTOR}
            if principal.role == UserRole.HOSPITAL_MANAGER
            else {UserRole.PATIENT, UserRole.DOCTOR, UserRole.HOSPITAL_MANAGER}
        )
        if target not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to provision that role",
            )
        if target == UserRole.DOCTOR and not (request.qualification and request.specialty):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A doctor needs both qualification and specialty",
            )

        email = str(request.email).lower()
        if await self.users.get_by_email(email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
        user = User(
            first_name=request.first_name,
            last_name=request.last_name,
            email=email,
            mobile_number=request.mobile_number,
            password_hash=hash_password(request.password),
            role=target,
            qualification=request.qualification if target == UserRole.DOCTOR else None,
            specialty=request.specialty if target == UserRole.DOCTOR else None,
            consultation_hours=request.consultation_hours if target == UserRole.DOCTOR else None,
        )
        try:
            await self.users.create(user)
        except DuplicateKeyError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists") from exc
        logger.info("ManagementController.create_user | actor=%s role=%s target=%s", principal.user_id, target.value, user.id)
        return serialize_managed_user(user)

    async def set_account_status(
        self, user_id: str, request: AccountStatusRequest, principal: Principal
    ) -> dict:
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        user = await self.users.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        if user.id == ObjectId(principal.user_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot change your own account status")
        if principal.role == UserRole.HOSPITAL_MANAGER and user.role not in {UserRole.PATIENT, UserRole.DOCTOR}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers cannot change administrator accounts")
        if user.role == UserRole.SUPERADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The superadmin account cannot be changed here")
        user.is_active = request.is_active
        await self.users.save(user)
        logger.info("ManagementController.set_account_status | actor=%s target=%s active=%s", principal.user_id, user.id, user.is_active)
        return serialize_managed_user(user)
