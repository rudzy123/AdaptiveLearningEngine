"""HTTP API: envelope, validation, error hygiene and the full loop on the fixture corpus."""

import json

import pytest

from ale.engine.curriculum import load_curriculum
from ale.interfaces.api import create_app
from ale.research.simulate import correct_answer


def ok(resp, status=200):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"status", "data"} and body["status"] == "success"
    return body["data"]


def err(resp, status, code):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"status", "error"} and body["status"] == "error"
    assert set(body["error"]) == {"message", "code"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    return body["error"]


# ---- envelope + validation -------------------------------------------------------

def test_success_envelope_on_every_read_endpoint(client):
    assert ok(client.get("/health"))["external_apis"] is False
    assert ok(client.get("/health"))["chunks_indexed"] == 28
    assert len(ok(client.get("/api/topics"))["topics"]) == 2
    assert ok(client.get("/api/search", params={"q": "binary search sorted"}))["results"]


@pytest.mark.parametrize(
    "method,path,kwargs,status,code",
    [
        ("post", "/api/sessions", {"json": {}}, 422, "validation_error"),
        ("post", "/api/sessions", {"json": {"user_id": "bad id!", "topic": "algorithms"}}, 422, "validation_error"),
        ("post", "/api/sessions", {"json": {"user_id": "ada", "topic": ""}}, 422, "validation_error"),
        ("post", "/api/sessions", {"json": {"user_id": "ada", "topic": "underwater basket weaving"}}, 404, "unknown_topic"),
        ("get", "/api/users/bad id/lesson", {}, 422, "validation_error"),
        ("get", "/api/users/ghost/lesson", {}, 404, "no_session"),
        ("get", "/api/users/ghost/problem", {}, 404, "no_session"),
        ("get", "/api/users/ghost/session", {}, 404, "no_session"),
        ("get", "/api/search", {}, 422, "validation_error"),
        ("get", "/api/search", {"params": {"q": "x", "k": 99}}, 422, "validation_error"),
        ("get", "/nope", {}, 404, "not_found"),
        ("delete", "/health", {}, 405, "method_not_allowed"),
    ],
)
def test_error_envelope(client, method, path, kwargs, status, code):
    err(getattr(client, method)(path, **kwargs), status, code)


def test_answer_validation_and_conflicts(client):
    ok(client.post("/api/sessions", json={"user_id": "ada", "topic": "linear algebra"}), 201)
    # no open problem yet
    err(client.post("/api/users/ada/answers", json={"problem_id": "p_x", "answer": "4"}), 409, "no_active_problem")
    problem = ok(client.get("/api/users/ada/problem"))
    err(client.post("/api/users/ada/answers", json={"problem_id": problem["problem_id"]}), 422, "validation_error")
    err(client.post("/api/users/ada/answers", json={"problem_id": problem["problem_id"], "answer": ""}), 422, "validation_error")
    err(client.post("/api/users/ada/answers", json={"problem_id": problem["problem_id"], "answer": "x" * 5000}), 422, "validation_error")
    err(client.post("/api/users/ada/answers", json={"problem_id": "p_wrong", "answer": "4"}), 409, "problem_mismatch")
    err(client.post("/api/users/ada/answers", content=b"{not json", headers={"content-type": "application/json"}), 422, "validation_error")
    # whitespace-only is rejected by the service
    err(client.post("/api/users/ada/answers", json={"problem_id": problem["problem_id"], "answer": "   "}), 422, "validation_error")
    # a valid answer still works after all those rejections, then cannot be replayed
    ok(client.post("/api/users/ada/answers", json={"problem_id": problem["problem_id"], "answer": "4, 7"}))
    err(client.post("/api/users/ada/answers", json={"problem_id": problem["problem_id"], "answer": "4, 7"}), 409, "no_active_problem")


def test_internal_errors_do_not_leak_stack_traces(db_path):
    from fastapi.testclient import TestClient

    app = create_app(db_path)

    def boom(*a, **k):
        raise RuntimeError("secret-internal-detail /home/user/file.py line 42")

    app.state.tutor.topics = boom
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/topics")
    error = err(resp, 500, "internal_error")
    text = resp.text
    assert error["message"] == "Internal server error"
    assert "secret-internal-detail" not in text and "Traceback" not in text and ".py" not in text


# ---- the full loop over HTTP ---------------------------------------------------------

LAYERS = ["exact_match", "partial_credit", "reasoning_alignment", "error_typing", "confidence_delta"]


def test_full_loop_over_http_and_state_survives_a_new_app(db_path):
    from fastapi.testclient import TestClient

    client = TestClient(create_app(db_path))

    # 1. start
    session = ok(client.post("/api/sessions", json={"user_id": "ada", "topic": "Linear Algebra"}), 201)
    assert session["concept"] == "vectors" and session["resumed"] is False

    # 2. lesson with citations
    lesson = ok(client.get("/api/users/ada/lesson"))
    assert lesson["citations"], "lesson must be grounded"
    for c in lesson["citations"]:
        assert {"source", "section", "chunk_id", "score"} <= set(c)

    # 3. problem (answer key is never exposed)
    problem = ok(client.get("/api/users/ada/problem"))
    assert problem["concept"] == "vectors"
    assert "answer" not in problem and "signatures" not in problem
    assert ok(client.get("/api/users/ada/problem"))["problem_id"] == problem["problem_id"]  # persisted

    # 4. wrong answer: conceptual error -> reteach
    r = ok(client.post("/api/users/ada/answers", json={"problem_id": problem["problem_id"], "answer": "3, 10"}))
    assert [l["name"] for l in r["evaluation"]["layers"]] == LAYERS
    assert r["error_type"] == "conceptual_error" and r["correct"] is False
    assert r["learning_signal"]["weak_concept"] is True and r["learning_signal"]["retry_recommended"] is True
    assert r["memory"]["confidence_after"] < r["memory"]["confidence_before"]
    assert r["next_step"]["action"] == "reteach" and r["next_step"]["lesson_level"] == "easy"

    # 5. reteach lesson differs and is easier
    easy = ok(client.get("/api/users/ada/lesson"))
    assert easy["level"] == "easy" and easy["citations"]
    assert {c["chunk_id"] for c in easy["citations"]} != {c["chunk_id"] for c in lesson["citations"]}

    # keep going with correct answers until the learner advances
    action, rounds = None, 0
    while action != "advance" and rounds < 6:
        p = ok(client.get("/api/users/ada/problem"))
        bank = load_curriculum().problem(p["bank_id"])
        answer, reasoning = correct_answer(bank)
        r = ok(client.post("/api/users/ada/answers", json={"problem_id": p["problem_id"], "answer": answer, "reasoning": reasoning}))
        assert r["correct"] is True and r["error_type"] == "none"
        action = r["next_step"]["action"]
        rounds += 1
        ok(client.get("/api/users/ada/lesson"))
    assert action == "advance"

    # 6. progress, then a brand-new app on the same file
    before = ok(client.get("/api/users/ada/progress"))
    by_concept = {c["concept"]: c for c in before["concepts"]}
    assert by_concept["vectors"]["confidence"] >= 0.8 and by_concept["vectors"]["mastered"]
    assert by_concept["dot_product"]["attempts"] == 0
    assert before["current_concept"] == "dot_product"

    reborn = TestClient(create_app(db_path))
    assert ok(reborn.get("/api/users/ada/progress")) == before
    again = ok(reborn.get("/api/users/ada/session"))
    assert again["concept"] == "dot_product" and again["phase"] in {"needs_lesson", "needs_problem"}
    assert ok(reborn.post("/api/sessions", json={"user_id": "ada", "topic": "linear algebra"}), 201)["resumed"] is True


def test_responses_are_json_serialisable_strings_only_keys(client):
    ok(client.post("/api/sessions", json={"user_id": "ada", "topic": "algorithms"}), 201)
    ok(client.get("/api/users/ada/lesson"))
    json.dumps(ok(client.get("/api/users/ada/progress")))
