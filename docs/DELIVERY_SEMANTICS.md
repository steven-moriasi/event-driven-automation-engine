# Delivery Semantics

## At-least-once delivery

The API acknowledges a valid event only after its inbox row, matching delivery rows, and audit row
commit. A worker claim is a renewable concept represented by a finite lease, so abandoned work
becomes eligible again. This prevents silent loss but permits repeated provider calls.

Exactly-once execution is not claimed. If a provider accepts a request and the worker fails before
committing the result, the same delivery can be attempted again.

## Idempotency

There are two independent identities:

1. Inbound identity: `(source, external_id)`.
2. Outbound identity: `source:external_id:subscription_id`.

An identical inbound event returns the original record and creates no new delivery. Reusing the
inbound identity with different canonical content returns a conflict. Every adapter forwards the
outbound identity in `Idempotency-Key`; the receiving integration is responsible for deduplicating
side effects across ambiguous retries.

## Retry strategy

Retryable conditions are connection failures, HTTP 408, HTTP 425, HTTP 429, and HTTP 5xx. Other
non-2xx responses are permanent. Delay is:

```text
min(base * 2^(attempt - 1) + deterministic_jitter, maximum)
```

Jitter is derived from the idempotency key and attempt number, making tests and incident analysis
reproducible while reducing synchronized retry bursts. An attempt that reaches the configured
maximum transitions directly to `dead`.

## Duplicate events

Producer duplicates with unchanged content do not fan out again. A different external event that
reuses an already-processed subject sequence is claimed and finalized as `skipped` without invoking
the provider.

## Out-of-order events

A sequence gap transitions a delivery to `blocked` without consuming an attempt. After the retry
delay, it can be reclaimed. Once preceding events advance the checkpoint, it becomes deliverable.
This is polling-based eventual progress; there is no push notification from checkpoint advancement.

## Transient and permanent failures

Transient failures preserve a stable error code and schedule another attempt. Permanent failures
become dead letters immediately. Error bodies and raw exception messages are discarded to avoid
persisting provider secrets or sensitive payloads.

## Eventual consistency

The API can report an event as dispatched while its deliveries remain pending, blocked, retrying,
or dead. Operators use delivery state, audit events, metrics, and replay rather than interpreting
webhook acknowledgement as completed downstream processing.

## Concurrency limitation

Fencing protects local state from stale workers. It cannot revoke a request already in flight, and
the current checkpoint approach does not serialize concurrent remote calls for distinct events
with the same ordering key. A production partitioned worker should route each
`(subscription, subject)` to one execution lane or lock that key before provider invocation.
