# CityCare Pipecat voice service

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
