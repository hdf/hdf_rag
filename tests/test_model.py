import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.mark.model
@pytest.mark.skipif(os.environ.get("HDF_TEST_MODEL") != "1", reason="Set HDF_TEST_MODEL=1")
def test_real_multilingual_retrieval(tmp_path):
    settings = Settings(qdrant_path=str(tmp_path / "qdrant"), qdrant_url=None, _env_file=None)
    documents = json.loads((Path(__file__).parents[1] / "examples/documents.json").read_text())
    with TestClient(create_app(settings)) as api:
        embedder = api.app.state.service.embedder
        assert embedder.dimension == 1024
        long_text = "A projektvezető jóváhagyja a következő mérföldkövet. " * 100
        chunks = embedder.chunks(long_text)
        assert len(chunks) > 1
        assert all(long_text[c.start : c.end] == c.text for c in chunks)
        assert chunks[-1].end == len(long_text.rstrip())
        vectors = embedder.encode([c.text for c in chunks])
        assert len(vectors) == len(chunks)
        assert all(len(vector) == 1024 for vector in vectors)
        for document in documents:
            assert api.post("/documents", json=document).status_code == 201
        for query, expected in [
            ("Hogyan indul el egy új projekt?", "DOC-001"),
            ("Ki hagyja jóvá a szabadságomat?", "DOC-002"),
            ("Who coordinates a production incident?", "DOC-003"),
        ]:
            response = api.post("/search", json={"query": query, "top_k": 1})
            assert response.status_code == 200
            assert response.json()["results"][0]["document_id"] == expected
