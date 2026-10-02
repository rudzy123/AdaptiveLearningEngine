"""API endpoint tests (envelope + session persistence)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_session_db, monkeypatch):
    """TestClient with isolated DBs and fresh LearningSession singleton."""
    from app.services import learning_session as ls_mod

    monkeypatch.setattr(ls_mod, "_session", tmp_session_db)
    from app.api import routes

    monkeypatch.setattr(routes, "_session", tmp_session_db)
    return TestClient(app)


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200


def test_full_loop_envelope(client: TestClient) -> None:
    uid = "pytest_user_1"

    r = client.post(
        "/start_topic",
        json={"user_id": uid, "topic": "linear algebra", "level": "beginner"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "success"
    assert body["data"]["current_concept"]

    r = client.get(f"/lesson/{uid}")
    assert r.status_code == 200
    lesson = r.json()["data"]
    assert "lesson" in lesson and "chunks" in lesson

    r = client.get(f"/problem/{uid}")
    assert r.status_code == 200
    assert "problem" in r.json()["data"]

    r = client.post(
        "/submit_answer",
        json={"user_id": uid, "answer": "test response"},
    )
    assert r.status_code == 200
    ev = r.json()["data"]
    assert "learning_signal" in ev
    assert "is_correct" in ev

    r = client.post(f"/next_step/{uid}")
    assert r.status_code == 200
    assert r.json()["data"]["next_concept"]

    r = client.get(f"/progress/{uid}")
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_submit_without_problem(client: TestClient) -> None:
    uid = "pytest_user_2"
    client.post(
        "/start_topic",
        json={"user_id": uid, "topic": "math", "level": "beginner"},
    )
    r = client.post(
        "/submit_answer",
        json={"user_id": uid, "answer": "hello"},
    )
    assert r.status_code == 400
    assert r.json()["status"] == "error"


def test_empty_answer_rejected(client: TestClient) -> None:
    uid = "pytest_user_3"
    client.post("/start_topic", json={"user_id": uid, "topic": "math"})
    client.get(f"/problem/{uid}")
    r = client.post("/submit_answer", json={"user_id": uid, "answer": "  "})
    assert r.status_code == 400
