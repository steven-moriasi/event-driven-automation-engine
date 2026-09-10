from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.infrastructure.database import Base, get_session
from app.main import app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'events.db'}",
        webhook_secrets={"partner": SecretStr("webhook-secret")},
        delivery_signing_secret=SecretStr("delivery-secret"),
        github_token=SecretStr("github-token"),
        delivery_max_attempts=2,
        retry_base_seconds=1,
        retry_max_seconds=2,
    )


@pytest.fixture
def session_factory(
    settings: Settings,
) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def client(
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> Iterator[TestClient]:
    def override_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
