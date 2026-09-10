# ADR 0002: Provide At-Least-Once Delivery

- Status: Accepted
- Date: 2026-09-10

## Context

No atomic transaction spans this service and an arbitrary remote HTTP provider. A timeout can leave
the provider result unknown.

## Decision

Retry ambiguous and transient outcomes, attach a stable idempotency key to every request, and state
the contract as at-least-once delivery.

## Consequences

- Work is recoverable after worker or network failure.
- Consumers must deduplicate by idempotency key.
- Exactly-once side effects are explicitly not promised.
- Dead-letter state and operator replay are required operational controls.
