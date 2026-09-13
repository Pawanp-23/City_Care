"""Configuration loaded once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    mongodb_url: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    database_name: str = os.getenv("DATABASE_NAME", "citycare_clinic")
    jwt_secret: str = os.getenv("JWT_SECRET", "unsafe-development-secret-change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_live_model: str = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    rag_embedding_model: str = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-004")
    rag_vector_index: str = os.getenv("RAG_VECTOR_INDEX", "citycare_knowledge_vector")
    rag_collection: str = os.getenv("RAG_COLLECTION", "clinic_knowledge_chunks")
    rag_chunk_size: int = int(os.getenv("RAG_CHUNK_SIZE", "900"))
    rag_chunk_overlap: int = int(os.getenv("RAG_CHUNK_OVERLAP", "160"))
    # Pipecat runs as a separate realtime process; it must not be imported by
    # the appointment API, where missing audio-provider dependencies would
    # otherwise take down bookings.
    deepgram_api_key: str = os.getenv("DEEPGRAM_API_KEY", "")
    cartesia_api_key: str = os.getenv("CARTESIA_API_KEY", "")
    cartesia_voice_id: str = os.getenv("CARTESIA_VOICE_ID", "")
    daily_room_url: str = os.getenv("DAILY_ROOM_URL", "")
    daily_token: str = os.getenv("DAILY_TOKEN", "")
    cloudinary_cloud_name: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    cloudinary_api_key: str = os.getenv("CLOUDINARY_API_KEY", "")
    cloudinary_api_secret: str = os.getenv("CLOUDINARY_API_SECRET", "")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_webhook_secret: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    telegram_public_base_url: str = os.getenv("TELEGRAM_PUBLIC_BASE_URL", "")
    telegram_session_ttl_hours: int = int(os.getenv("TELEGRAM_SESSION_TTL_HOURS", "24"))
    telegram_link_code_minutes: int = int(os.getenv("TELEGRAM_LINK_CODE_MINUTES", "10"))
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    )


settings = Settings()
