r"""Index the bundled CityCare handbook once after MongoDB is running.

Run from backend: .\.venv\Scripts\python.exe scripts\index_handbook.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database.database import close_mongo_connection, engine
from core.models.prescription_model import ClinicKnowledgeChunk
from core.services.clinic_rag import handbook_path, index_handbook


async def main() -> None:
    await engine.configure_database([ClinicKnowledgeChunk])
    try:
        print(await index_handbook(handbook_path(), "CityCare-Clinic-Patient-Handbook.pdf"))
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(main())
