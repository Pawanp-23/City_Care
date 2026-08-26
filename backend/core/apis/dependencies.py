"""Authentication and role dependencies for protected HTTP doors."""

from __future__ import annotations

from dataclasses import dataclass

from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from commons.auth import decode_access_token
from core.models.user_model import UserRole

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: UserRole
    first_name: str


async def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    role = payload.get("role")
    if not isinstance(user_id, str) or not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    try:
        parsed_role = UserRole(role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc
    return Principal(user_id=user_id, role=parsed_role, first_name=str(payload.get("first_name", "")))


async def patient_principal(principal: Principal = Depends(current_principal)) -> Principal:
    if principal.role != UserRole.PATIENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This action is available to patients only")
    return principal


async def doctor_principal(principal: Principal = Depends(current_principal)) -> Principal:
    if principal.role != UserRole.DOCTOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This area is available to the doctor only")
    return principal


async def staff_principal(principal: Principal = Depends(current_principal)) -> Principal:
    if principal.role not in {
        UserRole.DOCTOR,
        UserRole.HOSPITAL_MANAGER,
        UserRole.SUPERADMIN,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This area is available to CityCare staff only",
        )
    return principal


async def manager_principal(principal: Principal = Depends(current_principal)) -> Principal:
    if principal.role not in {UserRole.HOSPITAL_MANAGER, UserRole.SUPERADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This area is available to hospital managers only",
        )
    return principal


async def superadmin_principal(principal: Principal = Depends(current_principal)) -> Principal:
    if principal.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This area is available to the superadmin only",
        )
    return principal
