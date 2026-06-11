# Architecture

## System architecture

```text
Browser / mobile / WhatsApp
          |
   Load balancer / API gateway
          |
  Stateless FastAPI replicas
    |        |          |
Postgres   Redis     Object storage
 +pgvector  queue       (future)
              |
       Celery worker pools
              |
     Agent service / Tool registry
              |
 Gmail / Calendar / WhatsApp / internal APIs / sandboxes
```

Command flow:

1. FastAPI validates the JWT and derives the tenant exclusively from the token.
2. It stores the user message and a queued task, then publishes only the task ID.
3. A worker loads the task and tenant-scoped tool connections from PostgreSQL.
4. The agent selects tools. The executor validates schema, connection, and permissions.
5. Credentials are decrypted only immediately before execution.
6. Structured results, usage, and the assistant message are persisted for polling or streaming.

Concierge preview flow:

1. The API stores the tenant-scoped message and queued task.
2. The API sends a tagged request to the configured Telegram operator and stores the Telegram message-to-task mapping.
3. Telegram calls the secret-protected webhook when the operator replies directly to that request.
4. The API verifies the operator chat, atomically completes the mapped task, and stores the response.
5. The browser receives the completed response through task polling.

Every tenant-owned table includes `user_id`. Application queries always scope by the authenticated user. Production should add PostgreSQL row-level security as a second boundary.

## Technology decisions

- **SmolAgents behind an adapter:** lightweight and straightforward for a controllable tool-calling loop. The included deterministic adapter makes local development work without a model account. Introduce SmolAgents inside `app/services/agent.py` after model credentials are available.
- **CrewAI later:** useful for explicit multi-role workflows, but unnecessary overhead for the initial single-agent command path.
- **Versus LangGraph:** LangGraph is stronger when workflows require durable graph state, interrupts, and complex branching. It also introduces a larger orchestration model. Keep the agent interface stable so it can be adopted for those workflows.
- **FastAPI:** async I/O, typed schemas, OpenAPI, and WebSocket support fit an integration-heavy API.
- **Celery + Redis:** mature retries, worker routing, observability ecosystem, and horizontal worker scaling. Move to a durable broker such as RabbitMQ or managed Redis with persistence before high-stakes workloads.
- **PostgreSQL + pgvector:** transactions and tenant data live together; vector search can be added without operating another database.

## Database schema

| Table | Purpose | Tenant boundary |
|---|---|---|
| `users` | Identity and password hash | Primary identity |
| `tool_connections` | Encrypted credentials and granted permissions | `user_id`, unique tool per user |
| `agent_sessions` | Conversation containers | `user_id` |
| `messages` | Short-term conversation history | `user_id`, `session_id` |
| `agent_tasks` | Durable execution state and result | `user_id`, `session_id` |
| `api_usage` | Billable usage events | `user_id` |
| `memory_chunks` | Long-term memory metadata and embeddings | `user_id` |

The starter stores embeddings as JSON for SQLite-compatible development. Migrate that column to pgvector and add an IVFFlat/HNSW index when semantic retrieval is introduced.

## Repository structure

```text
app/
  api/             HTTP boundary
  services/        Agent and execution use cases
  tools/           Plug-and-play tool contracts and implementations
  static/          Minimal MVP UI
  config.py        Environment configuration
  database.py      Async database setup
  models.py        Durable data model
  security.py      Auth and credential encryption
  worker.py        Background execution
docs/
tests/
```

## Security posture

- Never accept a tenant ID from the client; derive it from the JWT.
- Store OAuth refresh tokens and API keys encrypted. In production, wrap data keys with AWS KMS, GCP KMS, or Vault and rotate them.
- Treat tool output as untrusted. Validate output limits and redact secrets from logs.
- Run filesystem, scraping, and code tools in isolated ephemeral containers with egress allowlists.
- Add gateway and per-user rate limits, audit logs, OAuth state/PKCE, JWT key rotation, and PostgreSQL RLS before production.
- Require explicit high-risk permissions and user confirmation for destructive or financial actions.

## MVP phases

1. **Days 1-2:** single deterministic/SmolAgents adapter, calculator and echo tools, basic chat UI.
2. **Multi-user:** JWT auth, PostgreSQL tenant data, encrypted tool connections.
3. **Execution platform:** Celery queue, retries, task state, tool marketplace contract.
4. **Voice:** upload endpoint, speech-to-text worker, streaming responses, optional TTS.
5. **Scale:** API/worker autoscaling, pgvector memory, managed broker, tracing, RLS, quotas.

## Scaling from 1 to 10,000+ users

FastAPI remains stateless and scales behind a load balancer. Celery queues split by workload and risk class, such as `fast`, `integrations`, and `sandbox`. Autoscale workers from queue depth and task latency. Use connection pooling, indexes on all tenant access paths, read replicas for history, and object storage for large payloads. Idempotency keys and outbox publishing prevent duplicated external actions.

## Roadmap

- Add real SmolAgents tool adapters and model routing with budget limits.
- Add pgvector long-term memory with tenant-filtered retrieval.
- Add OAuth connectors, webhook ingestion, and a reviewed marketplace manifest.
- Add WebSocket/SSE event streaming and voice transcription.
- Add Stripe subscriptions, usage aggregation, quotas, and invoicing.
- Add CrewAI or LangGraph only for workflows that genuinely need multiple roles or durable branching.
- Productize WhatsApp through Meta Cloud API/BSP webhooks, templates, consent, and conversation-window enforcement.
