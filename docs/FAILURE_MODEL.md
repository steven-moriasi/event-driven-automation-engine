# Failure Model

| Failure | Detection | State transition | Recovery |
|---|---|---|---|
| Invalid or missing webhook signature | Ingress HMAC check | No persistence; 401 | Producer fixes authentication |
| Unknown webhook source | Missing configured source secret | No persistence; 404 | Configure source explicitly |
| Oversized or invalid envelope | Byte bound or schema validation | No persistence; 413/422 | Producer corrects request |
| Duplicate event, same content | Unique identity plus hash comparison | Existing event returned | No operator action |
| Duplicate identity, changed content | Hash mismatch | 409 conflict | Producer resolves identity misuse |
| Database unavailable at ingress | Transaction fails | No 202 acknowledgement | Producer retries |
| Worker exits after claim | Lease expires | `delivering` to `pending` | Reaper recovers claim |
| Stale worker resumes | Lease/token ownership check | No local update or provider call | Current worker continues |
| Connection failure or retryable HTTP | Adapter classification | `delivering` to `pending` | Exponential backoff retry |
| Permanent HTTP response | Adapter classification | `delivering` to `dead` | Operator investigates and replays |
| Retry budget exhausted | Attempt count | `delivering` to `dead` | Operator investigates and replays |
| Sequence gap | Checkpoint comparison | `delivering` to `blocked` | Poll after predecessor progresses |
| Repeated sequence | Checkpoint comparison | `delivering` to `skipped` | No provider call |
| Provider accepts before local failure | Ambiguous distributed outcome | Delivery may retry | Consumer deduplicates idempotency key |
| Missing adapter configuration | Preflight mapping/config check | `delivering` to `dead` | Configure credential, then replay |

## Error storage

Persisted errors are stable service-defined codes and generic messages. Raw provider bodies,
connection exception text, access tokens, signatures, and webhook secrets are not stored.

## Recovery objectives

This repository demonstrates mechanisms, not measured service-level objectives. Lease duration,
retry budget, backoff limits, worker count, and alert thresholds require workload-specific testing.
