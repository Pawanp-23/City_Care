"""Single async ODMantic engine shared by CRUD repositories."""

from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine

from core.config import settings

client = AsyncIOMotorClient(settings.mongodb_url, tz_aware=True)
engine = AIOEngine(client=client, database=settings.database_name)


async def close_mongo_connection() -> None:
    client.close()

