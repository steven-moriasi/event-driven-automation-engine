# Roadmap

## Priority 1: production boundaries

- Replace development actor headers with issuer- and audience-validated OIDC.
- Add destination policy enforcement, DNS/IP validation, and egress network controls.
- Add webhook timestamp/nonce verification and signing-key rotation.
- Add event-schema versioning and compatibility policy.

## Priority 2: ordering and throughput

- Partition execution by `(subscription, subject)` to serialize remote calls per ordering key.
- Use PostgreSQL `FOR UPDATE SKIP LOCKED` or a broker fed from a transactional outbox.
- Add batched claims, lease heartbeats, graceful shutdown, and connection-pool tuning.
- Run fault-injection and workload tests before selecting worker counts or service objectives.

## Priority 3: observability and operations

- Export delivery depth, oldest delivery age, dead-letter count, and blocked-sequence age.
- Add OpenTelemetry traces across ingress, claim, adapter call, and replay.
- Publish example dashboards and alerts with workload-calibrated thresholds.
- Add retention, archive, and audited data-repair tooling.

## Priority 4: integration maturity

- Add provider-specific rate-limit parsing and retry hints.
- Support versioned adapter mappings and contract tests against provider sandboxes.
- Add per-subscription credentials from a managed secret reference rather than process-wide values.
- Add circuit breaking and tenant/source quotas.
