# Legacy optional Pipecat voice service

The supported CityCare voice workflow is now the authenticated `/voice` page
in the main application. It uses Gemini Live with short-lived browser tokens and
does not require Deepgram. Configure `GEMINI_API_KEY` and optionally
`GEMINI_LIVE_MODEL` in `backend/.env`, run the normal API and frontend, then
open `/voice` as a patient or doctor.

The service below remains only as an optional experiment.

This is a separate realtime service so a missing audio provider never brings
down the appointment API. It uses SmallWebRTC, Deepgram STT/TTS, Gemini, and
Silero VAD with streaming, metrics, and interruption-capable turn handling.

1. Add `DEEPGRAM_API_KEY` and `GEMINI_API_KEY` to `backend/.env`.
2. Install `pip install -r voice_requirements.txt` from `backend`.
3. Run `python voice/bot.py` from `backend`. It serves `POST /api/offer` on
   port 7860 for the voice client SDP handshake.

The Pipecat package changes import paths frequently. This service validates
configuration first and gives an actionable error when its optional dependency
is not installed.

## RAG and data boundaries

The voice LLM receives a `search_citycare_handbook` tool for public handbook
information. It must not access patient prescriptions or make appointment
changes: voice transcription is error-prone, and those actions need the normal
signed-in CityCare workflow and confirmation.
