# CityCare Clinic

CityCare is a single-hospital appointment system for Nagpur with separate patient, doctor, hospital-manager, and superadmin workspaces. It uses React/Vite on the frontend and a layered FastAPI + Motor/ODMantic backend.

## What changed in this version

- Multi-doctor booking: patients select a CityCare doctor before viewing availability. MongoDB prevents concurrent booking of the same doctor's date and slot.
- Four server-enforced roles: `SUPERADMIN` → `HOSPITAL_MANAGER` → `DOCTOR` → `PATIENT`.
- Hospital manager workspace: add doctors and patients, view both lists, and soft-disable/restore accounts.
- Superadmin workspace: includes manager provisioning and the same hospital-wide controls. One CityCare hospital is modelled intentionally; this is not fake multi-tenancy.
- Responsive app shell with a persistent desktop rail and a left-edge swipe drawer on mobile.
- Doctor-only CityCare Compass chatbot. It has a real Gemini function-calling loop and server-enforced tools for the signed-in doctor's schedule, workload statistics, and optional Tavily public-health research.
- The assistant is deliberately read-only for bookings. Letting an LLM create or cancel clinical appointments from unstructured chat would be an audit and consent problem. Booking remains in the normal validated form and database transaction.

## Architecture

```text
backend/
  commons/                         # JWT, bcrypt, central logger
  core/
    apis/routes/                   # HTTP routes only
    controllers/                   # business logic and authorization
    cruds/                         # MongoDB access only
    models/                        # ODMantic documents
    schemas/                       # request validation
    ai/                            # Gemini loop, bounded tools, Tavily transport
  scripts/seed_doctor.py           # trusted doctor provisioning
  scripts/seed_staff.py            # trusted manager/superadmin provisioning
frontend/
  src/components/                  # sidebar, Compass, forms, cards, tables
  src/pages/                       # patient, doctor, manager and admin workspaces
  src/api/client.js                # one fetch wrapper; any protected 401 clears storage
```

## Run locally

Prerequisites: Python 3.11+, Node 20+, pnpm/npm, and MongoDB.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Set a long JWT_SECRET and your MongoDB connection in .env.
python main.py
```

In a second terminal, create initial trusted accounts. These roles cannot be selected through public signup.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python scripts/seed_doctor.py --email doctor@citycareclinic.com --password 'SecurePass123'
python scripts/seed_staff.py --role HOSPITAL_MANAGER --email manager@citycareclinic.com --password 'SecurePass123'
python scripts/seed_staff.py --role SUPERADMIN --email admin@citycareclinic.com --password 'SecurePass123'
```

For the complete local demo hierarchy in one command (one superadmin, one
hospital manager, and three distinct doctors), use this instead. This makes
every account use the password you choose; it is only for a local demo.

```powershell
python scripts/bootstrap_demo_accounts.py --password 'CityCareDemo2026!' --reset-passwords
```

| Role | Login email |
| --- | --- |
| Superadmin | `admin@citycareclinic.com` |
| Hospital manager | `manager@citycareclinic.com` |
| Doctor - General Physician | `doctor.patil@citycareclinic.com` |
| Doctor - Internal Medicine | `doctor.sharma@citycareclinic.com` |
| Doctor - Family Medicine | `doctor.khan@citycareclinic.com` |

The hospital manager can create, deactivate, and restore patient/doctor
accounts. The superadmin can additionally provision hospital managers.

Then start the frontend:

```powershell
cd frontend
Copy-Item .env.example .env
pnpm install
pnpm dev
```

Open `http://localhost:5173`. API documentation is at `http://localhost:8000/docs`.

For a one-port local demo after building the frontend, run this from `backend`:

```powershell
python local_runner.py
```

Then open `http://127.0.0.1:8002`. It serves the already-built frontend and
the API together; it is for local demonstrations, not a production deployment.

## CityCare Compass configuration

The app starts without AI keys, but the doctor assistant returns a clear configuration error until Gemini is configured. Add the following to `backend/.env`; never commit actual values.

```dotenv
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_LIVE_MODEL=gemini-3.1-flash-live-preview
TAVILY_API_KEY=your_tavily_key
```

### Realtime hospital voice agent

Signed-in patients and doctors can open `/voice` from the Compass panel. This
mode uses Gemini Live for full-duplex speech, interruption handling, live
transcripts, and role-scoped CityCare tools. Patients can find doctors, inspect
facilities, review their own appointments and prescriptions, find free slots,
and book only after an explicit spoken confirmation. Doctors can review their
own schedule and clinic workload. Clinical mutations such as accepting an
appointment or issuing a prescription remain outside voice control.

The API exchanges the server-only Gemini key for a single-use, short-lived
session token; the browser never receives `GEMINI_API_KEY`. Microphone access
must be allowed for the CityCare origin, and the Gemini project must have Live
API access and quota. The normal text assistant remains available when realtime
voice is unavailable.

The assistant does not share conversations between users. The browser sends at most 12 prior messages for the current request; the backend does not retain chat history. All tool calls are server-side and role-checked. Tavily receives only generic, non-identifying public-health queries; obvious names, phone numbers, and email addresses are rejected before any web request.

If the Gemini provider is temporarily unreachable, Compass still answers the
doctor's core local questions about today's schedule and visit counts by using
the same protected CityCare tools directly. General AI conversation and public
research require a working Gemini connection (and Tavily for web research).

## Core endpoints

| Method | Path | Access |
| --- | --- | --- |
| POST | `/api/v1/auth/signup` | Public patient registration only |
| POST | `/api/v1/auth/login` | All roles |
| GET | `/api/v1/doctors` | Public care team list |
| GET | `/api/v1/appointments/free-slots?date=...&doctor_id=...` | Public live provider availability |
| POST | `/api/v1/appointments` | Patient booking |
| GET | `/api/v1/doctor/stats` and `/schedule` | Signed-in doctor only |
| GET/POST | `/api/v1/management/*` | Hospital manager or superadmin |
| POST | `/api/v1/assistant/chat` | Signed-in doctor only |
| POST | `/api/v1/doctor/appointments/{id}/accept` | Assigned doctor only |
| POST | `/api/v1/doctor/appointments/{id}/prescriptions` | Assigned doctor, accepted appointment only |
| POST | `/api/v1/doctor/prescriptions/{id}/attachments` | Issuing doctor only |
| GET | `/api/v1/prescriptions/mine` | Owning patient only |
| GET | `/api/v1/prescriptions/{id}/download` | Owning patient only |
| POST | `/api/v1/assistant/patient-chat` | Signed-in patient only |
| GET | `/api/v1/assistant/live-session` | Signed-in patient or doctor |

## Prescription, documents, RAG, and voice input

The implemented clinical flow is: `PENDING booking -> doctor accepts -> ACCEPTED -> one doctor-issued prescription -> PDF -> signed Cloudinary upload -> patient-authorized PDF access`.

Doctors can then attach TXT, MD, CSV, or PDF documents. The upload endpoint
accepts JSON base64 rather than `multipart/form-data` so it does not disappear
when `python-multipart` is not installed. Text is split into bounded chunks,
persisted with the `patient_id`, and the patient assistant retrieves only that
patient's chunks. This is the essential RAG sequence: load -> split -> persist
-> retrieve -> grounded response. It is deliberately a local lexical retriever
when Atlas/embedding infrastructure is not configured; it does **not** pretend
to be semantic vector search.

For semantic RAG, provision an Atlas Vector Search index with `patient_id` as a
filter field, then add a LangChain embedding/vector-store adapter. Never query
a clinic-wide vector store first and filter in the browser: that is a patient
data leak. The CityCare endpoint already enforces the ownership boundary before
retrieval.

The Compass panel supports fast browser speech recognition for one-off
questions. The dedicated `/voice` page is the realtime agent: it streams audio
directly over Gemini Live, supports interruption, and executes only the
role-scoped hospital tools described above. The older optional Pipecat service
under `backend/voice` is kept for experiments but requires a separate Deepgram
account and is not needed for the main CityCare voice workflow.

To issue a real prescription, set these server-only values in `backend/.env`:

```dotenv
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

Cloudinary's returned delivery URL is checked through CityCare before the app
opens it. For a real healthcare deployment, use Cloudinary authenticated/private
delivery or proxy the bytes through CityCare; a normal `secure_url` can still be
shared after it is opened, so it is not sufficient PHI protection by itself.

## Production reality

This is a strong local project build, not a production healthcare system. Before deploying, add HTTPS, rate limiting, audit trails, verified staff onboarding, password reset, encrypted backups, consent/retention rules, data access reviews, and a proper EMR/pharmacy/billing compliance design. Do not claim those domains are solved because a dashboard has an icon for them.

## Telegram patient assistant

The backend now includes a DM-only Telegram gateway for natural-language doctor
search, registration, booking, confirmation status, facilities, patient chat,
and authorized prescription PDF delivery. It uses short-lived pairing codes for
existing patients and sends notifications when the doctor accepts an
appointment or issues a prescription. The existing web app is unchanged.

Deployment, security, BotFather, webhook, and Hermes-inspired session details
are documented in [`backend/TELEGRAM_GATEWAY.md`](backend/TELEGRAM_GATEWAY.md).
# Prescription, RAG, and Voice Assistant

## Run locally

Open PowerShell in this repository and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-local.ps1
```

This opens one persistent window for the API and one for Vite. Keep both open,
then browse to `http://localhost:5173`. Running a server in a short-lived task
or terminal that is closed will always produce `ERR_CONNECTION_REFUSED`.

The prescription flow is deliberately role-scoped:

1. A patient booking is created as `PENDING`.
2. The assigned doctor accepts it from the schedule (`ACCEPTED`).
3. Only that doctor can issue a prescription. CityCare renders a PDF, uploads it to Cloudinary, stores the returned secure URL, and indexes the prescription text.
4. Only the owning patient can list and download that PDF at `/api/v1/prescriptions/mine`.
5. Doctors can add readable PDF/TXT/MD/CSV support documents. They are split with LangChain's `RecursiveCharacterTextSplitter` and stored as patient-scoped chunks. The patient assistant retrieves only chunks with the signed-in patient's id; it cannot search the clinic-wide corpus.

Set `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET` in `backend/.env` before issuing prescriptions. Without these values the API intentionally returns `503`: pretending a PDF was stored would be a data-loss bug.

The copied reference projects are in `work/reference-cliniccare-rag` and `work/reference-clinic-voice-ai`. The first demonstrates load -> split -> embed -> vector-search -> grounded response. Its unfiltered collection must not be used for prescriptions; this app applies the patient filter before retrieval. The voice reference is a separate Pipecat WebRTC service requiring Deepgram and Google credentials. The CityCare client currently includes text chat with browser text-to-speech for returned answers; a production realtime voice deployment should run that Pipecat service separately and authenticate its session against CityCare before it can access prescription data.
