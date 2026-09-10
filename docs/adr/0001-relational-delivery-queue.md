# ADR 0001: Use a Relational Delivery Queue

- Status: Accepted
- Date: 2026-09-10

## Context

Webhook acknowledgement must not race event persistence or delivery creation. Introducing a broker
would require coordinating a database commit with message publication.

## Decision

Store the canonical inbound event and all matching delivery rows in one relational transaction.
Workers poll and conditionally claim delivery rows.

## Consequences

- Acceptance and enqueueing share one atomic durability boundary.
- Local development and failure injection require only a database.
- Claim efficiency and table maintenance become database concerns.
- Higher throughput may justify a broker fed by a transactional outbox, but the database remains
  the source of truth.
