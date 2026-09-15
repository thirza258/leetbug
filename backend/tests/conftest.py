import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import seed, tasks
from app.config import settings
from app.db import Base, get_db
from app.main import app


@pytest.fixture
def db_factory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(settings, "testing", True)
    monkeypatch.setattr(settings, "seed_demo_user", False)
    monkeypatch.setattr(settings, "ai_provider", "disabled")
    monkeypatch.setattr(tasks, "SessionLocal", factory)
    monkeypatch.setattr(seed, "SessionLocal", factory)
    seed.seed()
    yield factory
    engine.dispose()


@pytest.fixture
def client(db_factory, monkeypatch):
    def override():
        with db_factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(tasks.evaluate, "delay", lambda *_: None)
    monkeypatch.setattr(tasks.hint_task, "delay", lambda *_: None)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def member(client):
    result = client.post("/api/auth/register", json={"email": "debugger@example.com", "username": "debugger", "password": "StrongPassword123!"})
    assert result.status_code == 201, result.text
    session = result.json()
    client.headers["X-CSRF-Token"] = session["csrf_token"]
    return session["user"]

