import re

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.embedding import split_text
from app.main import create_app


class WordTokenizer:
    def __call__(self, text, **kwargs):
        return {"offset_mapping": [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]}


class FakeEmbedder:
    """Deterministic test double; never used by the running application."""

    dimension = 3

    def chunks(self, text):
        return split_text(text, WordTokenizer(), size=8, overlap=2)

    def encode(self, texts, *, query=False):
        return [
            [float("projekt" in text.lower()), float("szabadság" in text.lower()), 0.1]
            for text in texts
        ]


@pytest.fixture
def settings(tmp_path):
    return Settings(
        qdrant_path=str(tmp_path / "qdrant"),
        qdrant_url=None,
        log_file=str(tmp_path / "logs/app.log"),
        _env_file=None,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings, FakeEmbedder()), raise_server_exceptions=False) as api:
        yield api


def test_health_and_empty_search(client):
    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["qdrant"]["reachable"] is True
    assert body["qdrant"]["mode"] == "embedded"
    assert body["qdrant"]["collection_status"] == "green"
    assert body["qdrant"]["points_count"] == 0
    assert body["qdrant"]["check_duration_ms"] >= 0
    response = client.post("/search", json={"query": "projekt"})
    assert response.status_code == 200
    assert response.json() == {"results": []}


def test_upload_search_and_duplicate(client):
    document = {"id": "DOC-1", "title": "Projekt", "text": "A projekt indítása."}
    assert client.post("/documents", json=document).status_code == 201
    assert client.post("/documents", json=document).status_code == 409
    assert (
        client.post(
            "/documents", json={"id": "DOC-2", "title": "HR", "text": "A szabadság igénylése."}
        ).status_code
        == 201
    )
    response = client.post("/search", json={"query": "projekt", "top_k": 1})
    assert response.status_code == 200
    hits = response.json()["results"]
    assert len(hits) == 1
    assert hits[0]["document_id"] == "DOC-1"
    assert hits[0]["chunk"] == document["text"]
    assert hits[0]["score"] > 0.99
    assert client.get("/health").json()["qdrant"]["points_count"] == 2


@pytest.mark.parametrize(
    "path,body",
    [
        ("/documents", {"id": " ", "title": "A", "text": "B"}),
        ("/documents", {"id": "1", "title": "A", "text": "\n\t"}),
        ("/documents", {"id": "1", "title": "A", "text": "x" * 100_001}),
        ("/documents", {"title": "A", "text": "B"}),
        ("/search", {"query": " "}),
        ("/search", {"query": "x", "top_k": 0}),
        ("/search", {"query": "x", "top_k": 21}),
        ("/search", {"query": "x", "top_k": True}),
        ("/search", {"query": "x", "top_k": "3"}),
        ("/search", {"query": "x", "unknown": 1}),
    ],
)
def test_validation(client, path, body):
    assert client.post(path, json=body).status_code == 422


def test_persistence(settings):
    with TestClient(create_app(settings, FakeEmbedder())) as api:
        response = api.post(
            "/documents", json={"id": "saved", "title": "Projekt", "text": "Projekt dokumentum."}
        )
        assert response.status_code == 201
    with TestClient(create_app(settings, FakeEmbedder())) as api:
        hits = api.post("/search", json={"query": "projekt"}).json()["results"]
        assert hits[0]["document_id"] == "saved"


def test_backend_failure_is_sanitized(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("secret internal connection details")

    monkeypatch.setattr(client.app.state.service.client, "get_collection", unavailable)
    response = client.get("/health")
    assert response.status_code == 503
    assert "secret" not in response.text
    assert response.json()["qdrant"]["reachable"] is False
    assert response.json()["qdrant"]["status"] == "unavailable"


@pytest.mark.parametrize("status,expected_code", [("yellow", 200), ("red", 503)])
def test_collection_health_status(client, monkeypatch, status, expected_code):
    monkeypatch.setattr(
        client.app.state.service, "health", lambda: {"collection_status": status, "points_count": 3}
    )
    response = client.get("/health")
    assert response.status_code == expected_code
    assert response.json()["qdrant"]["reachable"] is True
    assert response.json()["qdrant"]["collection_status"] == status


def test_chunk_source_offsets_and_overlap():
    text = "egy  kettő\nhárom négy öt hat hét nyolc kilenc"
    chunks = split_text(text, WordTokenizer(), size=4, overlap=1)
    assert [chunk.text.split() for chunk in chunks] == [
        ["egy", "kettő", "három", "négy"],
        ["négy", "öt", "hat", "hét"],
        ["hét", "nyolc", "kilenc"],
    ]
    assert all(text[c.start : c.end] == c.text for c in chunks)


def test_no_redundant_tail_chunk():
    assert len(split_text("one two three four", WordTokenizer(), size=4, overlap=2)) == 1
