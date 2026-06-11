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

### 2. Push to GitHub and deploy on Railway

This repository includes `railway.json` and a production Dockerfile. Create a Railway project from this GitHub repository, add a Railway PostgreSQL service, and add a volume mounted at `/data`. Set `DATABASE_URL=${{Postgres.DATABASE_URL}}` and `UPLOAD_DIR=/data/uploads`, then add:

```env
APP_ENV=production
TASK_ALWAYS_EAGER=true
CONCIERGE_MODE=true
JWT_SECRET=<at-least-32-random-characters>
TELEGRAM_BOT_TOKEN=<BotFather token>
TELEGRAM_OPERATOR_CHAT_ID=<your numeric chat id>
TELEGRAM_WEBHOOK_SECRET=<generated secret>
ELEVENLABS_API_KEY=<private API key>
ELEVENLABS_VOICE_ID=<selected voice ID>
```

### 3. Register the deployed webhook

From this repository, set the same values plus the Railway URL:

```powershell
$env:TELEGRAM_BOT_TOKEN="..."
$env:TELEGRAM_WEBHOOK_SECRET="..."
$env:PUBLIC_URL="https://your-service.up.railway.app"
py -3.12 scripts/setup_telegram_webhook.py
```

During the demo, each client message appears in Telegram. **Reply directly to that Telegram message** and the response will appear in the matching browser session.

If the live site shows `Setup required` or Telegram receives nothing:

1. Confirm all three Telegram environment variables exist on the Railway app service.
2. Confirm the latest Railway deployment completed successfully.
3. Run `scripts/setup_telegram_webhook.py` again using the live Railway URL.
4. Check the script output for `Last Telegram error`.
5. In Telegram, reply directly to the bot's tagged request rather than sending a new standalone message.

The concierge supports browser text, images, voice recordings, and files. Telegram operator replies may also include text, images, voice, audio, video, or documents. The Railway volume keeps media available across deployments.

## Interactive Operator Workspaces

Normal Telegram replies still appear as chat messages. Start a reply with one of these commands to transform the client UI:

```text
/email
subject: Latest message from the founder
from: founder@example.com
summary: The founder approved the launch plan.
The full email body can go here.
```

```text
/products
title: Top office chairs
summary: I compared the strongest options for comfort and value.
item: Green Soul Jupiter | Rs 8,490 | 4.5 | Best overall value
item: Featherlite Amaze | Rs 11,999 | 4.4 | Best for long sessions
```

```text
/progress
title: Campaign email prepared
summary: The draft is ready for approval.
step: Found the marketing contacts
step: Prepared the message
step: Checked recipients
```

Use `/video` with a Telegram video attachment to open the visual workspace.

## ElevenLabs Voice Mode

Voice mode streams Telegram operator text replies through ElevenLabs Flash v2.5. The client chooses **Text** or **Voice** from the top bar, and can replay any assistant reply.

1. Create an ElevenLabs account and API key.
2. In the ElevenLabs Voices library, choose an Indian female voice and copy its voice ID.
3. Add these variables to the Railway app service:

```env
ELEVENLABS_API_KEY=<private API key>
ELEVENLABS_VOICE_ID=<selected voice ID>
ELEVENLABS_MODEL_ID=eleven_flash_v2_5
ELEVENLABS_OUTPUT_FORMAT=mp3_22050_32
```

Set `ELEVENLABS_LANGUAGE_CODE=hi` only when replies should consistently be Hindi. Leave it empty for English/Hinglish auto-detection. Never expose the ElevenLabs API key in browser code.

After saving the variables, deploy the latest commit and refresh the site. Enable **Live voice** once and every new reply will speak automatically.

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
