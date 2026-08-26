"""CityCare realtime voice assistant, built with Pipecat SmallWebRTC.

Run separately from the booking API:
    python voice/bot.py

The Pipecat runner serves POST /api/offer on port 7860. Every browser caller
gets its own pipeline and conversation context. The voice agent is deliberately
read-only: it can answer handbook questions but cannot book, cancel, prescribe,
or expose another patient's records from speech alone.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import settings
from core.services.clinic_rag import retrieve_handbook

SYSTEM_INSTRUCTION = """You are CityCare Compass Voice — the friendly voice assistant at CityCare Clinic, Nagpur.

Personality:
- Sound like a warm, calm, and genuinely helpful clinic receptionist — not a robot.
- Keep every response to one or two short, natural spoken sentences. No bullet points, markdown, or lists.
- Use contractions and conversational language. "Here's what I know" not "The information indicates".
- If you don't know something, say so simply and suggest they ask at reception — no fuss.

Rules:
- Only answer from the CityCare handbook context provided in the conversation.
- Never diagnose, prescribe, or assess how urgent a symptom is — always refer to the doctor for that.
- Never book, cancel, or change an appointment by voice — direct them to the app or front desk.
- For any emergency, calmly say: "Please call ambulance service at 1-0-8 immediately." """


def require_configuration() -> None:
    missing = [name for name, value in {
        "DEEPGRAM_API_KEY": settings.deepgram_api_key,
        "GEMINI_API_KEY": settings.gemini_api_key,
    }.items() if not value]
    if missing:
        raise RuntimeError("Voice service requires " + ", ".join(missing) + " in backend/.env.")


async def run_bot(transport, runner_args) -> None:
    """Build one streaming STT -> context -> Gemini -> TTS pipeline per call."""
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.frames.frames import LLMRunFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineParams, PipelineWorker
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
        LLMUserAggregatorParams,
    )
    from pipecat.adapters.schemas.function_schema import FunctionSchema
    from pipecat.adapters.schemas.tools_schema import ToolsSchema
    from pipecat.services.deepgram.stt import DeepgramSTTService
    from pipecat.services.deepgram.tts import DeepgramTTSService
    from pipecat.services.google.llm import GoogleLLMService
    from pipecat.workers.runner import WorkerRunner

    stt = DeepgramSTTService(api_key=settings.deepgram_api_key)
    tts = DeepgramTTSService(
        api_key=settings.deepgram_api_key,
        settings=DeepgramTTSService.Settings(voice="aura-2-andromeda-en"),
    )
    handbook_tool = FunctionSchema(
        name="search_citycare_handbook",
        description="Search CityCare's public clinic handbook for policy, hours, fees, services, facilities, or contact details. Never use it for patient records.",
        properties={"question": {"type": "string", "description": "The caller's clinic question."}},
        required=["question"],
    )
    llm = GoogleLLMService(
        api_key=settings.gemini_api_key,
        settings=GoogleLLMService.Settings(system_instruction=SYSTEM_INSTRUCTION),
    )
    context = LLMContext(tools=ToolsSchema(standard_tools=[handbook_tool]))

    async def search_citycare_handbook(params) -> None:
        """RAG tool: retrieve only public handbook chunks before Gemini replies."""
        question = str(params.arguments.get("question", ""))
        result = await retrieve_handbook(question, limit=3)
        passages = [
            {"source": item["source"], "page": item["page"], "text": item["text"]}
            for item in result["chunks"]
        ]
        await params.result_callback({"mode": result["mode"], "passages": passages})

    llm.register_function("search_citycare_handbook", search_citycare_handbook)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )
    pipeline = Pipeline([
        transport.input(),        # browser microphone -> audio frames
        stt,                      # audio -> transcript
        user_aggregator,          # final user turns -> conversation context
        llm,                      # context -> streamed answer text
        tts,                      # text -> streamed spoken audio
        transport.output(),       # audio -> browser speaker
        assistant_aggregator,     # spoken reply -> context history
    ])
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_, __) -> None:
        context.add_message({
            "role": "developer",
            "content": "Greet the caller warmly by name if possible, introduce yourself as CityCare Compass Voice, and let them know you can help with clinic info like hours, fees, services, and general health questions. Keep it to two sentences max, friendly and natural.",
        })
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_, __) -> None:
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)
    await runner.run()


async def bot(runner_args) -> None:
    from pipecat.transports.base_transport import TransportParams
    from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

    transport = SmallWebRTCTransport(
        webrtc_connection=runner_args.webrtc_connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    require_configuration()
    try:
        from pipecat.runner.run import main
    except ImportError as exc:
        raise RuntimeError("Install backend/voice_requirements.txt before running the voice service.") from exc
    main()
