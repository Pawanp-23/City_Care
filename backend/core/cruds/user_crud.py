"""Database operations for clinic users."""

from __future__ import annotations

from bson import ObjectId
from odmantic import AIOEngine

from core.database.database import engine
from core.models.user_model import User, UserRole


class UserCRUD:
    def __init__(self, db: AIOEngine = engine) -> None:
        self.db = db

    async def create(self, user: User) -> User:
        await self.db.save(user)
        return user

    async def get_by_email(self, email: str) -> User | None:
        return await self.db.find_one(User, User.email == email.lower())

    async def get_by_id(self, user_id: str | ObjectId) -> User | None:
        object_id = user_id if isinstance(user_id, ObjectId) else ObjectId(user_id)
        return await self.db.find_one(User, User.id == object_id)

    async def find_by_ids(self, user_ids: list[ObjectId]) -> list[User]:
        if not user_ids:
            return []
        return await self.db.find(User, User.id.in_(user_ids))

    async def count_patients(self) -> int:
        collection = self.db.get_collection(User)
        return await collection.count_documents({"role": UserRole.PATIENT.value, "is_active": True})

    async def count_active_by_role(self, role: UserRole) -> int:
        collection = self.db.get_collection(User)
        return await collection.count_documents({"role": role.value, "is_active": True})

    async def list_by_role(self, role: UserRole, limit: int = 200) -> list[User]:
        return await self.db.find(User, User.role == role, sort=User.created_at.desc(), limit=limit)

    async def list_doctors(self) -> list[User]:
        return await self.db.find(
            User,
            User.role == UserRole.DOCTOR,
            User.is_active == True,  # noqa: E712 - ODMantic uses expression comparison.
            sort=User.first_name.asc(),
        )

    async def save(self, user: User) -> User:
        await self.db.save(user)
        return user
