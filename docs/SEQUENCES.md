# Runtime Sequences

## Signed ingestion and fan-out

```mermaid
sequenceDiagram
    participant P as Producer
    participant A as API
    participant D as Database

    P->>A: POST envelope + HMAC signature
    A->>A: Bound body, resolve source, verify signature
    A->>A: Validate envelope and canonical hash
    A->>D: Begin transaction
    A->>D: Insert inbound event
    A->>D: Read matching subscriptions
    A->>D: Insert one delivery per subscription
    A->>D: Insert audit event
    A->>D: Commit
    A-->>P: 202 Accepted
```

If `(source, external_id)` already exists, the API compares the stored canonical hash. Equal content
returns the existing event as a duplicate; changed content returns 409.

## Delivery attempt

```mermaid
sequenceDiagram
    participant W as Worker
    participant D as Database
    participant I as Integration

    W->>D: Select eligible delivery
    W->>D: Conditional claim + worker + lease + fencing token
    D-->>W: Claimed delivery
    W->>D: Verify current, unexpired lease ownership
    W->>D: Read event, subscription, and checkpoint
    alt sequence is next
        W->>I: POST mapped payload + Idempotency-Key
        I-->>W: Response or transport failure
        W->>D: Conditional finalize on worker/token/lease
        opt successful sequenced event
            W->>D: Advance checkpoint in same commit
        end
    else sequence gap
        W->>D: Mark blocked without consuming attempt
    else sequence already processed
        W->>D: Mark skipped without provider call
    end
```

## Lease recovery

```mermaid
sequenceDiagram
    participant O as Old worker
    participant R as Reaper
    participant D as Database
    participant N as New worker

    O->>D: Claim token 7 with finite lease
    Note over O: Worker stalls
    R->>D: Move expired delivery to pending
    N->>D: Claim token 8
    O->>D: Try to process/finalize token 7
    D-->>O: Ownership check fails
    N->>D: Finalize token 8
```

## Dead-letter replay

```mermaid
sequenceDiagram
    participant U as Operator
    participant A as API
    participant D as Database
    participant W as Worker

    U->>A: POST replay + reason + operator identity
    A->>D: Conditional update where status is dead
    A->>D: Reset attempts, increment replay count/token
    A->>D: Insert audit event
    A-->>U: Pending delivery
    W->>D: Claim replayed delivery
```
