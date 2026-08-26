"""Patient-isolated prescription retrieval.

Chunks are made with LangChain's splitter, persisted with the patient id, and
retrieved only after an authorization filter. A simple lexical ranker is used
locally so the clinic remains testable without a paid embedding service; swap
`_score` for Atlas Vector Search/embeddings in production without changing the
authorization boundary.
"""
from __future__ import annotations

import re
from bson import ObjectId
from odmantic import AIOEngine
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # Allows core clinic routes to boot before optional RAG extras are installed.
    RecursiveCharacterTextSplitter = None

from core.database.database import engine
from core.models.prescription_model import PrescriptionChunk

_splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=160) if RecursiveCharacterTextSplitter else None

async def index_prescription(db: AIOEngine, prescription_id: ObjectId, patient_id: ObjectId, source: str, content: str) -> None:
    chunks = _splitter.split_text(content) if _splitter else [content[index:index + 900] for index in range(0, len(content), 740)]
    await db.save_all([PrescriptionChunk(prescription_id=prescription_id, patient_id=patient_id, text=chunk, source=source) for chunk in chunks if chunk.strip()])

def _score(query: str, text: str) -> int:
    words = set(re.findall(r"[a-z0-9]+", query.casefold()))
    return sum(text.casefold().count(word) for word in words if len(word) > 2)

async def retrieve_patient_context(patient_id: str, question: str, db: AIOEngine = engine, limit: int = 4) -> list[PrescriptionChunk]:
    records = await db.find(PrescriptionChunk, PrescriptionChunk.patient_id == ObjectId(patient_id))
    return sorted(records, key=lambda record: _score(question, record.text), reverse=True)[:limit]
