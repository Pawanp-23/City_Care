"""CityCare handbook RAG: load -> split -> embed -> store -> retrieve.

Atlas Vector Search is used automatically when the configured MongoDB supports
it. A lexical fallback keeps local development functional, but is intentionally
reported as such; it is not falsely labelled semantic vector search.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from urllib.parse import urlencode

from odmantic import AIOEngine

from core.ai.http_client import TransportError, post_json
from core.config import settings
from core.database.database import engine
from core.models.prescription_model import ClinicKnowledgeChunk


def _split_pages(pdf_path: Path) -> list[tuple[int, str]]:
    from pypdf import PdfReader
    pages: list[tuple[int, str]] = []
    for page_number, page in enumerate(PdfReader(str(pdf_path)).pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append((page_number, text))
    return pages


def _chunks_for_page(page: int, text: str) -> list[tuple[int, str]]:
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )
        return [(page, chunk) for chunk in splitter.split_text(text) if chunk.strip()]
    except ImportError:
        stride = settings.rag_chunk_size - settings.rag_chunk_overlap
        return [(page, text[i : i + settings.rag_chunk_size]) for i in range(0, len(text), stride)]


async def _embed_documents(texts: list[str]) -> list[list[float]]:
    if not settings.gemini_api_key:
        return []
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/" + settings.rag_embedding_model + ":batchEmbedContents?" + urlencode({"key": settings.gemini_api_key})
    requests = [{"model": f"models/{settings.rag_embedding_model}", "content": {"parts": [{"text": text}]}, "taskType": "RETRIEVAL_DOCUMENT"} for text in texts]
    _, body = await post_json(endpoint, {"requests": requests}, 45.0)
    return [list(item.get("values", [])) for item in body.get("embeddings", [])]


async def _embed_query(question: str) -> list[float]:
    if not settings.gemini_api_key:
        return []
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/" + settings.rag_embedding_model + ":embedContent?" + urlencode({"key": settings.gemini_api_key})
    _, body = await post_json(endpoint, {"content": {"parts": [{"text": question}]}, "taskType": "RETRIEVAL_QUERY"}, 30.0)
    return list(body.get("embedding", {}).get("values", []))


async def index_handbook(pdf_path: Path, source: str, db: AIOEngine = engine) -> dict:
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Handbook not found: {pdf_path}")
    raw = [item for page in _split_pages(pdf_path) for item in _chunks_for_page(*page)]
    collection = db.get_collection(ClinicKnowledgeChunk)
    await collection.delete_many({"source": source})
    embeddings: list[list[float]] = []
    try:
        for start in range(0, len(raw), 50):
            embeddings.extend(await _embed_documents([text for _, text in raw[start : start + 50]]))
    except TransportError:
        embeddings = []
    records = [
        ClinicKnowledgeChunk(text=text, source=source, page=page, chunk_index=index, embedding=(embeddings[index] if index < len(embeddings) else None))
        for index, (page, text) in enumerate(raw)
    ]
    if records:
        await db.save_all(records)
    return {"source": source, "pages": len({page for page, _ in raw}), "chunks_indexed": len(records), "embeddings_indexed": sum(bool(item.embedding) for item in records)}


def _lexical_score(question: str, text: str) -> int:
    terms = {term for term in re.findall(r"[a-z0-9]+", question.casefold()) if len(term) > 2}
    return sum(text.casefold().count(term) for term in terms)


async def retrieve_handbook(question: str, limit: int = 4, db: AIOEngine = engine) -> dict:
    query_vector: list[float] = []
    try:
        query_vector = await _embed_query(question)
    except TransportError:
        pass
    collection = db.get_collection(ClinicKnowledgeChunk)
    if query_vector:
        try:
            rows = await collection.aggregate([
                {"$vectorSearch": {"index": settings.rag_vector_index, "path": "embedding", "queryVector": query_vector, "numCandidates": max(40, limit * 15), "limit": limit}},
                {"$project": {"text": 1, "source": 1, "page": 1, "score": {"$meta": "vectorSearchScore"}}},
            ]).to_list(length=limit)
            return {"mode": "atlas_vector", "chunks": [{"text": row["text"], "source": row["source"], "page": row["page"], "score": round(float(row.get("score", 0)), 3)} for row in rows]}
        except Exception:
            # Local MongoDB does not implement $vectorSearch; use the explicit
            # fallback below rather than failing the entire assistant.
            pass
    records = await db.find(ClinicKnowledgeChunk)
    ranked = sorted(records, key=lambda item: _lexical_score(question, item.text), reverse=True)[:limit]
    return {"mode": "local_lexical", "chunks": [{"text": item.text, "source": item.source, "page": item.page, "score": _lexical_score(question, item.text)} for item in ranked if _lexical_score(question, item.text)]}


def handbook_path() -> Path:
    return Path(__file__).resolve().parents[3] / "references" / "cliniccare_rag" / "CityCare-Clinic-Patient-Handbook.pdf"
