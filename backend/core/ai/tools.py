"""Server-owned tools the model may request. Tool authorization is never delegated to Gemini."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from core.ai.http_client import TransportError, post_json
from core.apis.dependencies import Principal
from core.config import settings
from core.controllers.doctor_controller import DoctorController
from core.controllers.management_controller import ManagementController
from core.models.user_model import UserRole


TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "get_my_schedule",
        "description": "Get the signed-in doctor's booked schedule for one date. Never use this for another doctor's schedule.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"date": {"type": "STRING", "description": "Date in YYYY-MM-DD format."}},
            "required": ["date"],
        },
    },
    {
        "name": "get_clinic_statistics",
        "description": "Get operational counts for the signed-in doctor's workload. Doctors receive their own appointment counts; managers receive hospital-wide counts.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "get_hospital_overview",
        "description": "Get CityCare hospital-wide operational counts. Available only to hospital managers and superadmins.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "search_public_health_guidance",
        "description": "Search public, general health guidance with Tavily. Use only for non-diagnostic, non-identifying research. Never put a patient's name, contact details, medical record, or other identifiable detail in the query.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"query": {"type": "STRING", "description": "A generic public-health research question."}},
            "required": ["query"],
        },
    },
]


@dataclass(frozen=True)
class ToolContext:
    principal: Principal


def _safe_date(value: Any) -> date:
    if not isinstance(value, str):
        raise ValueError("date must be YYYY-MM-DD")
    return date.fromisoformat(value)


def _safe_research_query(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("query must be text")
    query = " ".join(value.split())
    if not query or len(query) > 280:
        raise ValueError("query must be between 1 and 280 characters")
    # This is intentionally conservative: Tavily is a public third party and
    # should never receive obvious patient identifiers from CityCare.
    sensitive_patterns = (
        r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        r"\+?91[\s-]?[6-9]\d{9}",
        r"\b(?:mr|mrs|ms|patient)\.?\s+[A-Z][a-z]+",
    )
    if any(re.search(pattern, query, flags=re.IGNORECASE) for pattern in sensitive_patterns):
        raise ValueError("Use a general question without patient-identifying details")
    return query


async def _search_tavily(query: str) -> dict[str, Any]:
    if not settings.tavily_api_key:
        return {"available": False, "message": "Tavily is not configured by the clinic administrator."}
    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 3,
        "include_answer": False,
    }
    try:
        response_status, data = await post_json("https://api.tavily.com/search", payload, 15.0)
        if response_status >= 400:
            return {"available": False, "message": "Public-health search is temporarily unavailable."}
        return {
            "available": True,
            "results": [
                {
                    "title": item.get("title", "Untitled"),
                    "url": item.get("url", ""),
                    "snippet": str(item.get("content", ""))[:700],
                }
                for item in data.get("results", [])[:3]
            ],
        }
    except TransportError:
        return {"available": False, "message": "Public-health search is temporarily unavailable."}


async def run_tool(name: str, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Run one bounded tool call and return an LLM-readable, least-data result."""
    role = context.principal.role
    try:
        if name == "get_my_schedule":
            if role != UserRole.DOCTOR:
                return {"error": "Only a doctor may access a personal clinical schedule."}
            selected_date = _safe_date(arguments.get("date"))
            schedule = await DoctorController().schedule(selected_date, context.principal.user_id)
            return {"date": schedule["date"], "appointments": schedule["appointments"][:30]}

        if name == "get_clinic_statistics":
            if role == UserRole.DOCTOR:
                return await DoctorController().stats(context.principal.user_id)
            if role in {UserRole.HOSPITAL_MANAGER, UserRole.SUPERADMIN}:
                return await ManagementController().overview()
            return {"error": "You are not authorized to access clinic statistics."}

        if name == "get_hospital_overview":
            if role not in {UserRole.HOSPITAL_MANAGER, UserRole.SUPERADMIN}:
                return {"error": "Only management may access the hospital overview."}
            return await ManagementController().overview()

        if name == "search_public_health_guidance":
            return await _search_tavily(_safe_research_query(arguments.get("query")))

        return {"error": f"Unknown tool: {name}"}
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    except Exception:
        # Do not expose operational or patient-record details into a model response.
        return {"error": "The requested CityCare data is temporarily unavailable."}
