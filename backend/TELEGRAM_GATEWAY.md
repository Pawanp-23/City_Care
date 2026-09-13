# Medihub Telegram Patient Gateway

This gateway adds a patient-only Telegram interface without changing the React
application. Telegram is a transport; the existing Medihub controllers and
MongoDB rules remain the authority for users, doctors, slots, appointments,
doctor acceptance, and prescriptions.

## Patient flow

```text
Telegram patient
  -> Telegram HTTPS webhook (secret verified)
  -> TelegramGateway (identity + bounded per-DM session)
  -> existing Medihub controllers
  -> MongoDB uniqueness/ownership rules
  -> Telegram reply or prescription PDF
```

The bot accepts natural sentences, not only menu selections. Commands are
shortcuts. Examples:

- `Which doctors are available?`
- `Find a general physician`
- `Book an appointment with Dr. Patil`
- `Has my doctor confirmed my appointment?`
- `Show my latest prescription`
- `What hospital facilities are available?`
- A general health question for bounded, non-diagnostic guidance

Booking is a free-text multi-turn workflow: doctor/specialty, date, available
time, reason, and explicit confirmation. It creates a `PENDING` appointment.
State-aware reply buttons make common actions, dates, available times, consent,
and confirmation easier to select. They are optional: patients can type natural
sentences or workflow answers at every step.
`Main Menu` safely exits an unfinished workflow. `New conversation` (also
`/new`, `/clear`, or `/reset`) clears the bounded server-side conversation
history and workflow data without unlinking the verified patient account. It
does not erase message bubbles from Telegram's client UI; only the patient can
clear that visible chat history using Telegram's own controls.
When the assigned doctor accepts it in Medihub, the bot pushes a confirmation.
When the doctor issues a prescription, the bot announces it; the patient can
request the prescription and receive the authorized PDF in Telegram.

## Registration and protected records

Unknown Telegram users may view public doctors/facilities and register a new
patient using `/register`. Temporary registration details are cleared after the
workflow completes or is cancelled. The generated internal credential is not
sent through Telegram; Telegram-created accounts need a future password-reset
flow before they can use password login on the web.

An existing patient must not gain prescription access by merely typing an email
or mobile number. They obtain a 10-minute one-time code from:

```http
POST /api/v1/integrations/telegram/link-code
Authorization: Bearer <patient JWT>
```

Then send `/link ABC12XYZ` to the bot. This pairing rule is intentional: email,
mobile number, Telegram username, and Telegram display name are not proof of
hospital identity.

## Setup

Create a bot with BotFather and configure:

```dotenv
TELEGRAM_BOT_TOKEN=123456789:bot-token
TELEGRAM_WEBHOOK_SECRET=a-long-random-secret-letters-digits_-only
TELEGRAM_PUBLIC_BASE_URL=https://your-public-api.example
TELEGRAM_SESSION_TTL_HOURS=24
TELEGRAM_LINK_CODE_MINUTES=10
```

For local development, run long polling from `backend/`. It does not require a
public URL, but the machine must allow outbound HTTPS access to Telegram:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_telegram_polling
```

Restart this worker after changing bot code. Telegram does not permit polling
and webhook delivery for the same bot at the same time; the polling runner
removes the webhook without discarding pending updates.

The public base URL must terminate HTTPS and route to this FastAPI service.
After starting the API and applying MongoDB indexes through its lifespan, run
from `backend/`:

```powershell
python scripts/configure_telegram_webhook.py
```

Telegram will deliver messages to:

```text
POST /api/v1/integrations/telegram/webhook
X-Telegram-Bot-Api-Secret-Token: <TELEGRAM_WEBHOOK_SECRET>
```

Do not expose the webhook without the secret, commit the token, log full update
payloads, or enable the bot in group chats. Patient operations are DM-only.
Outgoing messages and PDFs set Telegram's `protect_content` flag to discourage
forwarding and saving. That is not equivalent to end-to-end encryption or a
healthcare data-processing agreement; production use still needs a legal and
privacy review of Telegram as a processor.

## Hermes Agent design reference

The implementation applies the relevant Hermes Agent gateway concepts rather
than embedding Hermes' broad Telegram toolset:

- deterministic per-DM routing key: `agent:medihub:telegram:dm:<chat_id>`;
- bounded durable session history and expiring workflow state;
- explicit pairing before protected operations;
- webhook secret verification and duplicate-update receipts;
- a platform-specific least-privilege tool surface;
- visible typing state and replies split to Telegram limits.

References:

- <https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram>
- <https://hermes-agent.nousresearch.com/docs/user-guide/sessions/>
- <https://hermes-agent.nousresearch.com/docs/user-guide/security/>
- <https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/>
- <https://hermes-agent.nousresearch.com/docs/guides/use-mcp-with-hermes/>

Hermes' default Telegram platform toolset can include terminal and file tools.
That surface is inappropriate for a hospital patient channel. The dedicated
gateway exposes only doctor discovery, facilities, patient registration,
booking, status, prescriptions, and bounded patient chat.
