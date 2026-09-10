# Contributing

## Development checks

Use Python 3.12 and install the development dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Before opening a pull request:

```bash
ruff check app tests alembic
mypy app tests
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
EVENT_ENGINE_DATABASE_URL=sqlite:///migration.db alembic upgrade head
EVENT_ENGINE_DATABASE_URL=sqlite:///migration.db alembic downgrade base
EVENT_ENGINE_DATABASE_URL=sqlite:///migration.db alembic upgrade head
docker compose config --quiet
docker build .
```

Do not commit `.env` files, tokens, webhook secrets, provider response bodies, or production event
payloads. Changes to delivery behavior should include tests and updates to the relevant architecture,
failure, security, runbook, or ADR documentation.
