"""Open authentication routes."""

from fastapi import APIRouter, HTTPException, status

from commons.logger import get_logger
from core.controllers.auth_controller import AuthController
from core.schemas.auth_schema import LoginRequest, SignupRequest

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest) -> dict:
    try:
        data = await AuthController().signup(request)
        return {"message": "Account created successfully", "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected signup failure")
        raise HTTPException(status_code=500, detail="Unable to create your account right now") from exc


@router.post("/login")
async def login(request: LoginRequest) -> dict:
    try:
        data = await AuthController().login(request)
        return {"message": "Signed in successfully", "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected login failure")
        raise HTTPException(status_code=500, detail="Unable to sign in right now") from exc

