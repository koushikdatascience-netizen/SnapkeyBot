# Snapkey Assistant

A deployable multi-tenant assistant demo with two execution modes:

- **Concierge preview:** client requests are routed to one verified Telegram operator, whose direct replies appear in the web UI.
- **Agent mode:** requests use a configurable Groq, OpenAI, or OpenRouter model with permission-scoped tools.

The concierge UI clearly labels itself as human-assisted. It is intended for prototype validation, not for presenting manual responses as autonomous AI.

## Fastest Demo Deployment

### 1. Create the Telegram operator bot

1. Message `@BotFather` in Telegram, create a bot, and copy its token.
2. Send any message to the new bot from the Telegram account that will operate the demo.
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`.
4. Copy your numeric `message.chat.id`.
5. Generate an alphanumeric webhook secret:

```powershell
py -3.12 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Push to GitHub and deploy on Render

This repository includes `render.yaml`. In Render, create a **Blueprint** from the GitHub repository and set:

```env
TELEGRAM_BOT_TOKEN=<BotFather token>
TELEGRAM_OPERATOR_CHAT_ID=<your numeric chat id>
TELEGRAM_WEBHOOK_SECRET=<generated secret>
```

Render provisions Postgres, generates `JWT_SECRET`, enables concierge mode, and deploys the Docker web service.

### 3. Register the deployed webhook

From this repository, set the same values plus the Render URL:

```powershell
$env:TELEGRAM_BOT_TOKEN="..."
$env:TELEGRAM_WEBHOOK_SECRET="..."
$env:PUBLIC_URL="https://your-service.onrender.com"
py -3.12 scripts/setup_telegram_webhook.py
```

During the demo, each client message appears in Telegram. **Reply directly to that Telegram message** and the response will appear in the matching browser session.

## Local Development

```powershell
Copy-Item .env.example .env
py -3.12 -m pip install -e ".[dev]"
py -3.12 -m uvicorn app.main:app --reload --port 8010
```

Open `http://127.0.0.1:8010`. A public HTTPS tunnel is required for Telegram webhooks during local concierge testing.

Run tests:

```powershell
py -3.12 -m pytest -q -p no:cacheprovider
```

## Agent Mode

Set `CONCIERGE_MODE=false`, then configure one OpenAI-compatible provider:

```env
LLM_PROVIDER=groq
LLM_API_KEY=gsk_...
LLM_MODEL=llama-3.3-70b-versatile
```

Supported `LLM_PROVIDER` values are `groq`, `openai`, `openrouter`, and `deterministic`.

Available tools include calculator, echo, read-only Gmail search, read-only Google Calendar events, system information, and workspace-only file listing. Google tools currently accept encrypted OAuth access tokens; production OAuth refresh and consent flows remain future work.

## Security Notes

- Telegram webhooks require the configured secret header and accept replies only from the configured operator chat.
- Every Telegram dispatch is durably mapped to one tenant-owned task.
- Credentials are encrypted before database storage.
- The local OS connector cannot execute commands or access files outside this project.
- Add migrations, rate limits, managed secret rotation, and a full OAuth flow before broad production use.

See [docs/architecture.md](docs/architecture.md) for the wider architecture.
