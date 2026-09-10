# Event-Driven Automation Engine

A focused reference implementation for durable, at-least-once event delivery. The system accepts
signed webhooks, normalizes event envelopes, persists work before acknowledgement, and delivers to
integration adapters with idempotency, retries, dead-letter handling, and replay.

This repository is an engineering lab, not evidence of production throughput or availability.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check app tests
mypy app
pytest
uvicorn app.main:app --reload
```
