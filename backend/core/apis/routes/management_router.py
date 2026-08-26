"""Protected hospital manager and superadmin routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from commons.logger import get_logger
from core.apis.dependencies import Principal, manager_principal
from core.controllers.management_controller import ManagementController
from core.models.user_model import UserRole
from core.schemas.management_schema import AccountStatusRequest, CreateUserRequest

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/management", tags=["Hospital Management"])


@router.get("/overview")
async def overview(principal: Principal = Depends(manager_principal)) -> dict:
    del principal
    try:
        return {"message": "Hospital overview retrieved", "data": await ManagementController().overview()}
    except Exception as exc:
        logger.exception("Unexpected management overview failure")
        raise HTTPException(status_code=500, detail="Unable to retrieve hospital overview") from exc


@router.get("/users")
async def users(
    role: UserRole = Query(...),
    principal: Principal = Depends(manager_principal),
) -> dict:
    try:
        return {"message": "Accounts retrieved", "data": await ManagementController().users_by_role(role, principal)}
    except Exception as exc:
        logger.exception("Unexpected management users failure")
        raise HTTPException(status_code=500, detail="Unable to retrieve accounts") from exc


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    principal: Principal = Depends(manager_principal),
) -> dict:
    try:
        data = await ManagementController().create_user(request, principal)
        return {"message": "Account created", "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected management create-user failure")
        raise HTTPException(status_code=500, detail="Unable to create account") from exc


@router.post("/users/{user_id}/status")
async def set_account_status(
    user_id: str,
    request: AccountStatusRequest,
    principal: Principal = Depends(manager_principal),
) -> dict:
    try:
        data = await ManagementController().set_account_status(user_id, request, principal)
        return {"message": "Account status updated", "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected management account-status failure")
        raise HTTPException(status_code=500, detail="Unable to update account status") from exc
