# Principal Engineer Review

## Verdict

The repository is credible as a focused event-delivery engineering lab. The strongest evidence is
the explicit treatment of ambiguous distributed outcomes: durable acceptance, at-least-once
delivery, consumer idempotency, leases, fencing, bounded retries, ordering checkpoints, dead-letter
state, and audited replay. It should not be presented as production-ready.

## Review rubric

| Area | Assessment | Evidence |
|---|---|---|
| Problem framing | Strong | Scope excludes a general workflow product and states non-goals |
| Architecture | Strong | Clear durability boundary, adapter boundary, and consistency model |
| Reliability | Strong for a lab | Recovery, retry, fencing, dead letters, replay, failure tests |
| Security | Moderate | HMAC ingress and fail-closed operator boundary; production identity and egress controls absent |
| Data model | Strong | Explicit uniqueness, checkpoints, attempts, leases, replay and audit state |
| Observability | Moderate | Structured worker logs and per-process metrics; backlog/age metrics and tracing absent |
| Testing | Strong | Workflow failure paths, adapter contracts, strict types, coverage gate, migration round trips |
| Operability | Strong for a lab | Runbook, health/readiness, migrations, non-root image, process topology |
| Scalability | Moderate | Conditional claims are safe but intentionally simple and polling-based |
| Documentation | Strong | Architecture, sequences, semantics, threat/failure models, ADRs, evidence limits |

## Material strengths

1. The webhook transaction closes the common gap between acknowledging an event and recording its
   delivery work.
2. Duplicate content and conflicting identity reuse are distinguished rather than silently merged.
3. Fencing protects local state from stale workers, and the test verifies a stale worker does not
   invoke its adapter after losing ownership.
4. Successful sequenced delivery and checkpoint advancement share one local commit.
5. Remote response bodies and transport details are excluded from persisted errors.
6. Documentation states exactly-once and production claims that the implementation cannot support.

## Production blockers

### P1: serialize each ordering key

Two distinct events for the same `(subscription, subject)` can be claimed concurrently before either
advances the checkpoint. Partitioned execution or a database lock per ordering key is required for
strict concurrent ordering.

### P1: implement production operator identity

The development header mechanism correctly fails closed outside development, but OIDC validation,
scope mapping, service identities, and authorization policy are not implemented.

### P1: constrain outbound destinations

Subscription URLs require allowlists, safe DNS/IP resolution, redirect policy, and network egress
controls before untrusted or broadly privileged operators can configure them.

### P1: handle long-running attempts

There is no lease heartbeat. Adapter timeouts must remain below the lease, or a new worker can
reclaim work while the original remote request remains in flight.

### P2: improve queue efficiency

The current claim path selects one row and resolves contention with a conditional update. PostgreSQL
`SKIP LOCKED`, partitioned claims, or broker-backed dispatch should be evaluated with measured load.

### P2: complete operational telemetry

Export queue depth, oldest age, blocked age, dead-letter count, and traces. Metrics are process-local,
so production scraping and aggregation must discover every worker and reaper replica.

### P2: add data lifecycle controls

Define event retention, payload minimization, encryption and deletion behavior, audit retention, and
schema compatibility before handling production data.

## Recommendation

Use this repository as portfolio evidence for event-driven architecture, delivery semantics, and
failure-aware integration design. Before production use, complete the P1 boundaries and validate the
result with concurrency, fault-injection, provider sandbox, and workload tests.
