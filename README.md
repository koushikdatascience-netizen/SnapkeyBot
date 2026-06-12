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

## Realtime ElevenLabs Agent

The **Talk live** experience is a continuous WebRTC conversation with interruption, live captions, listening/speaking states, and client tools that transform the workspace.

1. Create an ElevenLabs Agent and copy its Agent ID.
2. Add this Railway variable:

```env
ELEVENLABS_AGENT_ID=agent_your_agent_id
```

3. In the ElevenLabs Agent dashboard, add these client tools. Their names must match exactly:

```text
show_workspace
request_confirmation
show_email_workspace
show_product_workspace
show_video_workspace
show_progress_workspace
show_brief_workspace
request_human_operator
```

For the fastest setup, only add `show_workspace` and `request_confirmation`. The other tools remain supported for more specialized configurations.

To use the real integrations from the live agent, also add these three client tools:

```text
run_integration
start_browser
control_browser
```

`run_integration` parameters:

```text
tool_name   Required string, LLM Prompt
arguments   Required string, LLM Prompt containing valid JSON
confirmed   Required boolean, LLM Prompt
```

Allowed `tool_name` values are `gmail_search`, `gmail_read`, `gmail_draft`, `gmail_send`, `calendar_events`, `calendar_create`, `youtube_search`, and `retail_report`.

`start_browser` only needs an optional `title` string. `control_browser` uses `session_id`, `action`, `url`, `selector`, `text`, and `confirmed`. The agent must call `request_confirmation` before Gmail send, Calendar create, or interactive browser actions, then pass `confirmed=true` only when the user approved.

Snapkey also recognizes browsing intent directly from the live user transcript. Requests such as `open Google`, `visit example.com`, `search for supplier software`, or `play jazz on YouTube` automatically start and navigate the Browserbase session even if the voice model does not call `start_browser`.

After automatic browser actions, Snapkey sends the completed page title and URL back into the active ElevenLabs conversation using a contextual update. This keeps the voice agent aware of what the browser actually did.

`show_workspace` parameters:

```text
type     Required string, LLM Prompt
title    Optional string, LLM Prompt
summary  Optional string, LLM Prompt
details  Optional string, LLM Prompt
```

Use `type` values such as `calendar`, `gmail`, `retail`, `inventory`, `video`, or `brief`. Put events, email details, retail metrics, or other display data in `details`, separated with semicolons.

`request_confirmation` parameters:

```text
title    Required string, LLM Prompt
summary  Required string, LLM Prompt
action   Optional string, LLM Prompt
```

The confirmation tool pauses until the user selects **Confirm** or **Cancel**, then reports the decision to the live agent. It does not itself perform the external action. Real Gmail sending, calendar creation, inventory edits, and financial actions require authenticated server tools.

## Real Integrations

Configure these Railway variables:

```env
PUBLIC_URL=https://your-app.up.railway.app
GOOGLE_CLIENT_ID=<Google OAuth web client ID>
GOOGLE_CLIENT_SECRET=<Google OAuth client secret>
YOUTUBE_API_KEY=<YouTube Data API key>
BROWSERBASE_API_KEY=<Browserbase API key>
BROWSERBASE_PROJECT_ID=<Browserbase project ID>
BROWSERBASE_REGION=ap-southeast-1
CREDENTIAL_ENCRYPTION_KEY=<stable Fernet key>
```

Enable Gmail API, Google Calendar API, and YouTube Data API v3 in Google Cloud. Add this exact authorized redirect URI to the Google OAuth web client:

```text
https://your-app.up.railway.app/api/integrations/google/callback
```

After deployment, sign into Snapkey and select **Connect Google**. Refresh tokens are encrypted before storage.

ElevenLabs server tools call the endpoints below with:

```text
Authorization: Bearer {{snapkey_tool_token}}
Content-Type: application/json
```

The realtime client injects `snapkey_tool_token` as a short-lived dynamic variable. Available server-tool endpoints:

```text
POST /api/integrations/execute/gmail_search
POST /api/integrations/execute/gmail_read
POST /api/integrations/execute/gmail_draft
POST /api/integrations/execute/gmail_send
POST /api/integrations/execute/calendar_events
POST /api/integrations/execute/calendar_create
POST /api/integrations/execute/youtube_search
POST /api/integrations/execute/retail_report
POST /api/integrations/browser/session
POST /api/integrations/browser/{session_id}/action
```

Each execute endpoint accepts:

```json
{"arguments": {}, "confirmed": false}
```

`gmail_send` and `calendar_create` require `"confirmed": true`. Browser click, type, and keypress actions require the `confirmed=true` query parameter. Browserbase live-view URLs can be passed to `show_workspace` with `type=browser`; YouTube embed URLs can be passed with `type=youtube`.

Suggested parameters:

- Workspace tools: optional strings `title`, `summary`, `subject`, `from`, `to`, `body`, and `status`.
- `request_human_operator`: required string `request`.

Tell the agent in its system prompt to call the matching workspace tool whenever the topic changes. For any real send/delete/purchase action, it must ask for confirmation and wait for a server tool result before claiming completion.

The browser requests a short-lived conversation token from `/api/voice/conversation-token`. The ElevenLabs API key always remains on the server.

Rebuild the bundled browser client after editing `app/static/live-agent-source.js`:

```powershell
npm install
npm run build:live-agent
```

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
