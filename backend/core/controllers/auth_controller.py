"""Authentication use cases — signup and login."""

from __future__ import annotations

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from commons.auth import create_access_token, hash_password, verify_password
from commons.logger import get_logger
from core.cruds.user_crud import UserCRUD
from core.models.user_model import User, UserRole
from core.schemas.auth_schema import LoginRequest, SignupRequest

logger = get_logger(__name__)


def serialize_user(user: User) -> dict:
    """Return a safe public-facing dict — no password hash."""
    return {
        "id": str(user.id),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "mobile_number": user.mobile_number,
        "role": user.role.value,
    }


class AuthController:
    def __init__(self, users: UserCRUD | None = None) -> None:
        self.users = users or UserCRUD()

    async def signup(self, request: SignupRequest) -> dict:
        """Register a new patient account and return a JWT session."""
        email = str(request.email).lower()
        logger.info("AuthController.signup | attempt for email=%s", email)

        try:
            existing = await self.users.get_by_email(email)
        except Exception:
            logger.exception("AuthController.signup | DB error checking email=%s", email)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to create your account right now",
            )

        if existing:
            logger.warning("AuthController.signup | email already registered | email=%s", email)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )

        # Role is deliberately not accepted from the request body.
        user = User(
            first_name=request.first_name,
            last_name=request.last_name,
            email=email,
            mobile_number=request.mobile_number,
            password_hash=hash_password(request.password),
            role=UserRole.PATIENT,
        )

        try:
            await self.users.create(user)
            logger.info(
                "AuthController.signup | patient account created | email=%s id=%s", email, user.id
            )
        except DuplicateKeyError as exc:
            logger.warning(
                "AuthController.signup | DuplicateKeyError (race) for email=%s", email
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            ) from exc
        except Exception:
            logger.exception(
                "AuthController.signup | unexpected DB error saving user email=%s", email
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to create your account right now",
            )

        return self._session_response(user)

    async def login(self, request: LoginRequest) -> dict:
        """Authenticate a user and return a JWT session."""
        email = str(request.email).lower()
        logger.info("AuthController.login | attempt for email=%s", email)

        try:
            user = await self.users.get_by_email(email)
        except Exception:
            logger.exception(
                "AuthController.login | DB error fetching user email=%s", email
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to sign in right now",
            )

        if not user or not verify_password(request.password, user.password_hash):
            logger.warning(
                "AuthController.login | invalid credentials for email=%s", email
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            logger.warning(
                "AuthController.login | inactive account blocked | email=%s id=%s", email, user.id
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is inactive. Please contact the clinic.",
            )

        logger.info(
            "AuthController.login | success | email=%s role=%s id=%s",
            email, user.role.value, user.id,
        )
        return self._session_response(user)

    @staticmethod
    def _session_response(user: User) -> dict:
        """Build the standard auth response payload."""
        return {
            "access_token": create_access_token(
                user_id=str(user.id),
                role=user.role.value,
                first_name=user.first_name,
            ),
            "token_type": "bearer",
            "user": serialize_user(user),
        }
