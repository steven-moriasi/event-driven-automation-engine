# Threat Model

## Assets

- webhook source secrets;
- outbound signing secret and provider token;
- canonical event payloads;
- subscription destinations;
- delivery and checkpoint state;
- audit history;
- operator replay capability.

## Trust boundaries

1. External producer to public webhook ingress.
2. Operator to subscription, inspection, and replay endpoints.
3. Worker to arbitrary configured integration endpoint.
4. Application processes to PostgreSQL.
5. Metrics scraper and log pipeline to each process.

## Controls present

| Threat | Control |
|---|---|
| Forged webhook | Source-specific HMAC-SHA256 over exact bytes and constant-time comparison |
| Replay with altered content | Unique source identity plus canonical payload hash conflict |
| Oversized request exhaustion | Configurable byte limit before JSON parsing |
| Duplicate downstream side effect | Stable outbound idempotency key |
| Stale worker corruption | Finite lease, worker identity, and fencing token |
| Unauthorized replay | Operator role requirement and audit record |
| Provider secret leakage | Secret types, generic errors, no provider response persistence |
| High-cardinality metric abuse | Labels limited to fixed outcomes and adapter enums |
| Production use of development headers | Non-development environments fail closed with 503 |
| Silent unaudited mutation | Subscription creation, ingestion, delivery outcomes, recovery, and replay are audited |

## Open risks before production

### Operator identity

Development actor headers are intentionally not a production identity system. Deployments must
replace them with validated OIDC access tokens, issuer/audience checks, role or scope mapping, and
centralized authorization policy.

### Server-side request forgery

An operator can currently register any syntactically valid HTTP(S) endpoint. Production must enforce
destination allowlists, block loopback/link-local/private metadata ranges where inappropriate,
resolve DNS safely, restrict redirects, and apply egress network policy.

### Webhook freshness

Signatures prove possession of a secret but do not enforce timestamp freshness. Producer-specific
timestamp and nonce rules should be added where replay windows matter.

### Payload confidentiality

Canonical payloads are stored in the database. Production requires data classification, field
minimization, encryption controls, retention/deletion policy, and access logging appropriate to the
payload domain.

### Secret lifecycle

Environment configuration is suitable for the lab. Production should use a managed secret store,
rotation, versioned webhook keys, and least-privilege provider credentials.

### Abuse controls

Ingress currently lacks rate limiting and source quotas. Apply gateway limits and monitor conflict,
signature failure, payload rejection, retry, and dead-letter rates.
