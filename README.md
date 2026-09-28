# Event-Driven Automation Engine

A focused reference implementation for durable, at-least-once event delivery:

```text
signed webhook
→ canonical event envelope
→ transactional persistence and fan-out
→ leased asynchronous delivery
→ ordering, retries, dead letters, and replay
```

The project emphasizes failure semantics and operational evidence rather than a broad workflow
feature set. It is an engineering lab, not evidence of production throughput or availability.

## Engineering decisions

- A relational inbox and delivery queue remove the accept-then-enqueue failure window.
- `(source, external_id)` plus a canonical payload hash separates duplicates from conflicts.
- Every outbound request receives a stable idempotency key.
- Worker claims use finite leases and fencing tokens.
- Sequenced events maintain a checkpoint per subscription and subject.
- Retryable failures use bounded exponential backoff with deterministic jitter.
- Permanent failures and exhausted retries become operator-replayable dead letters.
- Provider bodies and raw connection errors are not persisted.

See [Architecture](docs/ARCHITECTURE.md), [Delivery Semantics](docs/DELIVERY_SEMANTICS.md),
[Runtime Sequences](docs/SEQUENCES.md), and the [ADRs](docs/adr/).

## API surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Process liveness |
| `GET` | `/ready` | Database readiness |
| `GET` | `/metrics` | API-process Prometheus metrics |
| `POST` | `/subscriptions` | Create an audited adapter subscription |
| `POST` | `/webhooks/{source}` | Authenticate and persist an event |
| `GET` | `/deliveries/{id}` | Inspect delivery state |
| `POST` | `/deliveries/{id}/replay` | Replay an unchanged dead letter |

Development operator endpoints require `X-Actor-ID` and an `operator` value in `X-Actor-Roles`.
Non-development environments fail closed until real operator authentication is implemented.

## Integration adapters

- generic signed webhook;
- GitHub Issues-shaped API;
- Slack webhook-shaped API.

The GitHub and Slack implementations exercise public API contracts without claiming affiliation,
production tenancy, or certified integration status.

## Run with Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
curl --fail http://localhost:8002/ready
```

Compose starts PostgreSQL, a migration job, the API, a delivery worker, and a lease reaper. The
example credentials are for local development only.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Configuration uses the `EVENT_ENGINE_` prefix. Important environment variables include:

- `EVENT_ENGINE_DATABASE_URL`
- `EVENT_ENGINE_WEBHOOK_SECRETS`
- `EVENT_ENGINE_DELIVERY_SIGNING_SECRET`
- `EVENT_ENGINE_GITHUB_TOKEN`
- `EVENT_ENGINE_DELIVERY_LEASE_SECONDS`
- `EVENT_ENGINE_DELIVERY_MAX_ATTEMPTS`
- `EVENT_ENGINE_RETRY_BASE_SECONDS`
- `EVENT_ENGINE_RETRY_MAX_SECONDS`
- `EVENT_ENGINE_PROCESS_METRICS_PORT`

## Verification

```bash
ruff check app tests alembic
mypy app tests
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
docker compose config --quiet
docker build .
```

CI repeats quality, PostgreSQL migration round-trip, and container build checks.

## Operations and review

- [Failure Model](docs/FAILURE_MODEL.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [Operations Runbook](docs/OPERATIONS.md)
- [Roadmap](docs/ROADMAP.md)

## Limits

- The repository does not establish production throughput, latency, availability, or recovery
  objectives.
- It does not guarantee zero event loss, exactly-once side effects, or strict concurrent ordering
  for the same subject under every failure.
- It does not establish provider certification, production account operation, regulatory
  compliance, penetration testing, or complete threat coverage.
- It makes no claim about client work, historical deployment, savings, adoption, or business
  outcomes.
