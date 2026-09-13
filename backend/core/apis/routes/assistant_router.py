"""Doctor and patient CityCare Compass endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from commons.logger import get_logger
from core.ai.agent import AssistantConfigurationError, AssistantUpstreamError, CityCareAgent
from core.apis.dependencies import Principal, current_principal, doctor_principal, patient_principal
from core.models.user_model import UserRole
from core.services.prescription_rag import retrieve_patient_context
from core.services.clinic_rag import retrieve_handbook
from core.services.live_voice import create_live_voice_session
from core.ai.schemas import AssistantChatRequest

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/assistant", tags=["CityCare Compass"])


@router.get("/live-session")
async def live_session(principal: Principal = Depends(current_principal)) -> dict:
    """Issue one short-lived, single-use Gemini Live token to an authorized user."""
    if principal.role not in {UserRole.PATIENT, UserRole.DOCTOR}:
        raise HTTPException(status_code=403, detail="Live voice is available to patients and doctors only")
    try:
        data = await create_live_voice_session(principal)
        return {"message": "Secure live voice session created", "data": data}
    except RuntimeError as exc:
        logger.warning("Unable to create Gemini Live session: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live voice is temporarily unavailable. Check Gemini Live access and quota, then try again.",
        ) from exc


@router.post("/chat")
async def chat(
    request: AssistantChatRequest,
    principal: Principal = Depends(doctor_principal),
) -> dict:
    agent = CityCareAgent()
    instant = await agent.local_operational_fallback(request, principal, allow_generic=False)
    if instant:
        return {"message": "Assistant response generated from local CityCare data", "data": instant}
    try:
        data = await agent.reply(request, principal)
        return {"message": "Assistant response generated", "data": data}
    except AssistantConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AssistantUpstreamError as exc:
        fallback = await agent.local_operational_fallback(request, principal)
        if fallback:
            logger.warning("CityCare Compass used local operational fallback")
            return {"message": "Assistant response generated from local CityCare data", "data": fallback}
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected CityCare assistant failure")
        raise HTTPException(status_code=500, detail="Unable to process the assistant request") from exc


@router.post("/voice-chat")
async def voice_chat(
    request: AssistantChatRequest,
    principal: Principal = Depends(doctor_principal),
) -> dict:
    """Low-latency voice endpoint — 1-2 spoken sentences, no tool loop."""
    agent = CityCareAgent()
    instant = await agent.local_operational_fallback(request, principal, allow_generic=False)
    if instant:
        return {"message": "Voice response generated from local data", "data": instant}
    try:
        data = await agent.voice_reply(request, principal)
        return {"message": "Voice response generated", "data": data}
    except AssistantConfigurationError as exc:
        logger.warning("voice_chat used local fallback because Gemini is not configured: %s", exc)
        fallback = await agent.local_operational_fallback(request, principal)
        return {"message": "Voice response from local data", "data": fallback}
    except AssistantUpstreamError as exc:
        fallback = await agent.local_operational_fallback(request, principal)
        if fallback:
            return {"message": "Voice response from local data", "data": fallback}
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected voice chat failure")
        raise HTTPException(status_code=500, detail="Unable to process voice request") from exc


@router.post("/patient-chat")
async def patient_chat(
    request: AssistantChatRequest,
    principal: Principal = Depends(patient_principal),
) -> dict:
    """Grounded patient Q&A. Gemini answers using retrieved prescription and handbook context."""
    chunks = await retrieve_patient_context(principal.user_id, request.message)
    context_parts: list[str] = []
    sources: list[str] = []

    if chunks:
        context_parts.append("\n\n".join(chunk.text for chunk in chunks))
        sources = sorted({chunk.source for chunk in chunks})
    else:
        result = await retrieve_handbook(request.message)
        if result["chunks"]:
            context_parts.append("\n\n".join(item["text"] for item in result["chunks"][:3]))
            sources = [f"{item['source']} - page {item['page']}" for item in result["chunks"]]

    combined_context = "\n\n".join(context_parts)

    agent = CityCareAgent()
    instant = await agent.local_patient_voice_fallback(
        request,
        principal,
        has_matching_record=bool(context),
        sources=sources,
        allow_generic=False,
    )
    if instant:
        return {"message": "Patient voice response generated from local data", "data": instant}
    try:
        data = await agent.patient_reply(request, principal, combined_context, sources)
        return {"message": "Patient assistant response generated", "data": data}
    except AssistantConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AssistantUpstreamError as exc:
        if combined_context:
            logger.warning("patient_chat used raw context fallback (Gemini unavailable)")
            return {
                "message": "Patient assistant response generated from local data",
                "data": {"response": combined_context[:1200], "sources": sources},
            }
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected patient chat failure")
        raise HTTPException(status_code=500, detail="Unable to process the assistant request") from exc


@router.post("/patient-voice")
async def patient_voice(
    request: AssistantChatRequest,
    principal: Principal = Depends(patient_principal),
) -> dict:
    """Low-latency patient voice endpoint — short answers, no markdown."""
    chunks = await retrieve_patient_context(principal.user_id, request.message)
    context = "\n\n".join(chunk.text for chunk in chunks) if chunks else ""
    sources = sorted({chunk.source for chunk in chunks}) if chunks else []

    agent = CityCareAgent()
    try:
        data = await agent.voice_reply(request, principal, context=context, sources=sources, is_patient=True)
        return {"message": "Patient voice response generated", "data": data}
    except AssistantConfigurationError as exc:
        logger.warning("patient_voice used local fallback because Gemini is not configured: %s", exc)
        fallback = await agent.local_patient_voice_fallback(
            request,
            principal,
            has_matching_record=bool(context),
            sources=sources,
        )
        return {"message": "Patient voice response from local data", "data": fallback}
    except AssistantUpstreamError as exc:
        logger.warning("patient_voice used local fallback because Gemini was unavailable: %s", exc)
        fallback = await agent.local_patient_voice_fallback(
            request,
            principal,
            has_matching_record=bool(context),
            sources=sources,
        )
        return {"message": "Patient voice response from local data", "data": fallback}
    except Exception as exc:
        logger.exception("Unexpected patient voice failure")
        raise HTTPException(status_code=500, detail="Unable to process voice request") from exc
