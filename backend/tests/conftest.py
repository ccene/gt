import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import db  # noqa: E402
from config import settings  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    db.reset_for_tests(db_file)
    settings.mistral_api_key = ""
    settings.ollama_base_url = "http://127.0.0.1:1"  # unreachable -> exercises fallback
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as c:
        yield c
    db.reset_for_tests(db_file)


@pytest.fixture()
def session(client):
    resp = client.post("/api/sessions", json={"story_id": None})
    assert resp.status_code == 200, resp.text
    return resp.json()
