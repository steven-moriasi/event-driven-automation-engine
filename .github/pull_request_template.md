## Summary

<!-- What changed and why? -->

## Delivery semantics and risk

<!-- How do retries, ordering, idempotency, and failure states change? -->

## Verification

- [ ] Ruff
- [ ] mypy
- [ ] affected tests
- [ ] full test suite with coverage gate
- [ ] migration round trip, if persistence changed
- [ ] container build or Compose validation, if runtime packaging changed

## Security and operations review

- [ ] Webhook and outbound authentication boundaries remain explicit
- [ ] Logs, errors, and fixtures contain no credentials or provider responses
- [ ] Replay remains operator-authorized and audited
- [ ] Metrics use bounded labels
- [ ] Architecture, failure model, runbook, or ADRs were updated where needed
