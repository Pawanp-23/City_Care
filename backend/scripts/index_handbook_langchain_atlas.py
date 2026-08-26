"""LangChain + MongoDB Atlas Vector Search handbook indexing.

This is the framework version of the CityCare RAG flow. It is intentionally a
one-time/offline command; do not call it for every chatbot question.

Requirements:
  pip install langchain-community langchain-google-genai langchain-mongodb
  MONGODB_URL must be an Atlas connection string and the Atlas vector index
  must target the ``embedding`` field with this project's embedding dimension.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import settings
from core.services.clinic_rag import handbook_path


def main() -> None:
    if not settings.gemini_api_key:
        raise RuntimeError("Set GEMINI_API_KEY in backend/.env.")
    if "mongodb+srv://" not in settings.mongodb_url:
        raise RuntimeError("MongoDB Atlas is required for vector search; local MongoDB does not support $vectorSearch.")
    try:
        from langchain_community.document_loaders import PyPDFLoader
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        from langchain_mongodb import MongoDBAtlasVectorSearch
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from pymongo import MongoClient
    except ImportError as exc:
        raise RuntimeError("Install langchain-community, langchain-google-genai, and langchain-mongodb first.") from exc

    documents = PyPDFLoader(str(handbook_path())).load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=settings.rag_chunk_size, chunk_overlap=settings.rag_chunk_overlap)
    chunks = splitter.split_documents(documents)
    for index, chunk in enumerate(chunks):
        chunk.metadata.update({"source": "CityCare-Clinic-Patient-Handbook.pdf", "chunk": index})
    embeddings = GoogleGenerativeAIEmbeddings(model=f"models/{settings.rag_embedding_model}", google_api_key=settings.gemini_api_key)
    collection = MongoClient(settings.mongodb_url)[settings.database_name][settings.rag_collection]
    MongoDBAtlasVectorSearch.from_documents(chunks, embeddings, collection=collection, index_name=settings.rag_vector_index)
    print(f"Indexed {len(chunks)} CityCare handbook chunks into Atlas collection {settings.rag_collection}.")


if __name__ == "__main__":
    main()
