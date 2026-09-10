# Portfolio Evidence Map

This document maps engineering claims to inspectable implementation and tests. It does not turn a
reference repository into evidence of production operation.

| Claim | Implementation evidence | Verification evidence |
|---|---|---|
| Signed webhook ingress | `app/api/routes/webhooks.py`, `app/infrastructure/signing.py` | `tests/test_ingestion_api.py` |
| Strict canonical envelope | `app/domain/schemas.py`, `app/services/ingestion.py` | duplicate, conflict, and invalid-envelope tests |
| Durable inbox before acknowledgement | `app/services/ingestion.py`, `app/domain/models.py` | transactional ingestion test |
| Transactional delivery fan-out | `app/services/ingestion.py` | event/delivery count assertions |
| Inbound idempotency | unique source identity and payload hash | duplicate and conflicting-payload tests |
| At-least-once delivery | lease recovery and retry state machine | retry/recovery workflow tests |
| Stale-worker protection | worker identity, lease, fencing token, conditional completion | stale-worker test verifies no adapter call |
| Retry and dead-letter handling | `retry_delay`, delivery result classification, attempt budget | transient retry and dead-letter test |
| Operator replay | replay route and conditional state reset | role rejection, replay state, and audit assertions |
| Sequence handling | consumer checkpoints and block/skip rules | gap, checkpoint advance, and repeated-sequence test |
| Generic signed delivery | generic webhook adapter | signature and idempotency-header test |
| Public API-shaped integrations | GitHub Issues and Slack mappings | bounded payload contract tests |
| Failure classification | HTTP/transport adapter rules | parameterized status and redaction tests |
| Auditability | `audit_events` and append-only service calls | service paths plus ingestion and replay assertions |
| Metrics | API, worker, and reaper Prometheus endpoints | Compose readiness/health smoke verification |
| Database evolution | two reversible Alembic revisions | SQLite and PostgreSQL upgrade/downgrade/upgrade |
| Runtime packaging | non-root multi-stage image and Compose topology | image build and Compose smoke test |
| Software delivery controls | pinned CI actions, coverage gate, Dependabot, PR checklist | `.github/` configuration |

## Verified locally

- Ruff across application, tests, and migrations.
- Strict mypy across application and tests.
- Seventeen deterministic tests.
- Branch coverage above the 80% gate.
- SQLite and PostgreSQL migration round trips.
- Docker image build and Compose configuration.
- Compose startup with healthy API, PostgreSQL, worker, and reaper.
- Signed ingress through PostgreSQL to asynchronous worker classification.

These checks describe the local revision when the review was written. The CI result remains a
separate GitHub signal after publication.

## Not proved by this repository

- production throughput, latency, availability, or recovery objectives;
- zero event loss under every infrastructure failure;
- exactly-once side effects;
- strict concurrent ordering for the same subject;
- provider certification or production account operation;
- regulatory compliance;
- security review, penetration test, or threat-model completeness;
- realized savings, business outcomes, client work, or historical deployment experience.
