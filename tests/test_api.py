import os
from pathlib import Path

os.environ["APP_API_KEY"] = "test-app-key"
os.environ["MISTRAL_API_KEY"] = "test-mistral-key"
os.environ["SKILLS_DIR"] = str(Path(__file__).resolve().parent.parent / "skills")

import pytest
from fastapi.testclient import TestClient

import app.main as main_mod
from app.main import app
from app.mistral_client import MistralError

AUTH = {"X-API-Key": "test-app-key"}
SKILL_ID = "01a0d49d-5ed3-7400-ab29-b86e52df9e9c"


@pytest.fixture()
def client(monkeypatch):
    captured = {}

    async def fake_complete(*, system, user, model, base_url, api_key, **kwargs):
        captured.update(system=system, user=user, model=model)
        return "VERBETERDE TEKST"

    monkeypatch.setattr(main_mod.mistral_client, "complete", fake_complete)
    with TestClient(app) as test_client:
        yield test_client, captured


def test_health_is_open(client):
    test_client, _ = client
    assert test_client.get("/health").status_code == 200


def test_process_requires_api_key(client):
    test_client, _ = client
    payload = {"skill": "support-communication", "text": "Hello world", "target_language": "nl"}
    assert test_client.post("/api/process", json=payload).status_code == 401
    assert test_client.post("/api/process", json=payload, headers={"X-API-Key": "fout"}).status_code == 401


def test_unknown_skill_returns_404(client):
    test_client, _ = client
    resp = test_client.post("/api/process", json={"skill": "bestaat-niet", "text": "hoi"}, headers=AUTH)
    assert resp.status_code == 404
    assert "bestaat-niet" in str(resp.json()["detail"])


def test_invalid_language_returns_422(client):
    test_client, _ = client
    resp = test_client.post(
        "/api/process",
        json={"skill": "support-communication", "text": "hoi", "target_language": "fr"},
        headers=AUTH,
    )
    assert resp.status_code == 422


def test_process_ok_by_name(client):
    test_client, captured = client
    resp = test_client.post(
        "/api/process",
        json={"skill": "support-communication", "text": "Hello world", "target_language": "nl"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] == "VERBETERDE TEKST"
    assert data["target_language"] == "nl"
    assert data["skill"] == "support-communication"
    assert "Nederlands" in captured["system"]
    assert "Hello world" in captured["user"]


def test_process_ok_by_skill_id(client):
    test_client, _ = client
    resp = test_client.post(
        "/api/process",
        json={"skill": SKILL_ID, "text": "Hallo wereld", "target_language": "en", "source_language": "nl"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.json()["target_language"] == "en"


def test_skills_list(client):
    test_client, _ = client
    resp = test_client.get("/api/skills", headers=AUTH)
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()["skills"]]
    assert "support-communication" in names
    assert test_client.get("/api/skills").status_code == 401


def test_reload(client):
    test_client, _ = client
    resp = test_client.post("/api/skills/reload", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["reloaded"] >= 1


def test_log_endpoint(client):
    test_client, _ = client
    test_client.post(
        "/api/process",
        json={"skill": "support-communication", "text": "hoi", "target_language": "nl"},
        headers=AUTH,
    )
    resp = test_client.get("/api/log?limit=50", headers=AUTH)
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert any("process ok" in e["msg"] for e in entries)
    assert test_client.get("/api/log").status_code == 401


def test_mistral_error_returns_502(client, monkeypatch):
    test_client, _ = client

    async def failing_complete(**kwargs):
        raise MistralError("Mistral API fout 500: boom")

    monkeypatch.setattr(main_mod.mistral_client, "complete", failing_complete)
    resp = test_client.post(
        "/api/process",
        json={"skill": "support-communication", "text": "hoi", "target_language": "nl"},
        headers=AUTH,
    )
    assert resp.status_code == 502
    assert "Mistral" in resp.json()["detail"]
