# Operations Runbook

## Process topology

- API: ingress, operator routes, readiness, and API-process metrics on port 8000.
- Worker: delivery polling and adapter metrics on port 9100.
- Reaper: expired-lease recovery metrics on port 9100.
- PostgreSQL: authoritative event, delivery, checkpoint, and audit state.

Prometheus must scrape every process type. Worker counters are process-local and are not aggregated
through the API metrics endpoint.

## Health checks

```bash
curl --fail http://localhost:8002/health
curl --fail http://localhost:8002/ready
curl --fail http://localhost:8002/metrics
```

`/health` checks process liveness. `/ready` executes a database query. Compose also checks each
worker and reaper metrics server.

## Important metrics

- `event_engine_events_ingested_total{outcome=...}`
- `event_engine_delivery_attempts_total{adapter=...,outcome=...}`
- `event_engine_delivery_duration_seconds{adapter=...}`
- `event_engine_deliveries_recovered_total`

Initial alert candidates, to be calibrated with load tests:

- sustained ingestion conflicts or signature failures at the gateway;
- increasing transient-failure ratio;
- any unexpected permanent-failure or dead-letter growth;
- recovered leases above normal deployment noise;
- readiness failures;
- delivery age exceeding the integration objective.

Delivery age and dead-letter depth are not yet exported directly and are roadmap items.

## Triage: delivery backlog

1. Confirm API, workers, reaper, and database are healthy.
2. Compare ingestion rate with successful and failed attempt rates.
3. Inspect database counts by `status`, `adapter_type`, and oldest `available_at`.
4. Check whether the backlog is pending, blocked by ordering, retrying, or dead.
5. Verify provider availability and credential configuration without printing secret values.
6. Scale workers only after checking database claim contention and ordering-key behavior.

## Triage: dead letters

1. Inspect `error_code`, response code, attempt count, adapter type, and correlation ID.
2. Use audit history to reconstruct claims, retries, recovery, and prior replay.
3. Correct the destination, credential, mapping, or provider condition.
4. Replay with an explicit operational reason and correlation ID.
5. Confirm the replayed delivery reaches a terminal expected state.

Repeated blind replay is not a recovery strategy; it can amplify provider load and duplicate side
effects if the consumer ignores idempotency keys.

## Triage: sequence gaps

1. Identify the `(subscription_id, subject)` checkpoint.
2. Find the missing lower sequence.
3. Confirm whether it was never received, is pending/retrying, or is dead.
4. Recover or replay the predecessor.
5. Allow the blocked delivery to become eligible on its next poll.

Do not manually advance checkpoints without a documented data-repair procedure; doing so skips
downstream side effects.

## Database migrations

Before deployment:

```bash
alembic upgrade head
```

CI verifies `upgrade head`, `downgrade base`, and `upgrade head` against PostgreSQL. A production
rollback decision must account for data written under the newer schema; database downgrade is not a
substitute for a tested application rollback plan.

## Local recovery drill

```bash
docker compose up -d --build
docker compose ps
docker compose logs worker reaper
docker compose down
```

The Compose environment uses development-only defaults. Replace every default secret and password
outside local testing.
