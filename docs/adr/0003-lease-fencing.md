# ADR 0003: Fence Delivery Leases

- Status: Accepted
- Date: 2026-09-10

## Context

A paused worker can resume after its lease has expired and another worker has reclaimed the same
delivery. Worker identity alone cannot distinguish the old claim from the new claim.

## Decision

Increment a fencing token on every claim and replay. Require delivery completion to match the
worker identity, fencing token, status, and unexpired lease.

## Consequences

- A stale worker cannot overwrite current delivery state.
- Recovery does not depend on terminating the stale process.
- An already-started remote request cannot be recalled; provider idempotency remains necessary.
- Lease duration must exceed normal adapter latency or be extended in a future heartbeat design.
