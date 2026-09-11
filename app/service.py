from threading import RLock
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from app.schemas import Document, SearchResult


class DuplicateDocument(Exception):
    pass


class RetrievalService:
    """Single-process prototype; serialize access to embedded Qdrant and the model."""

    def __init__(self, client: QdrantClient, embedder, collection: str):
        self.client = client
        self.embedder = embedder
        self.collection = collection
        self.lock = RLock()
        if not client.collection_exists(collection):
            client.create_collection(
                collection,
                vectors_config=models.VectorParams(
                    size=embedder.dimension, distance=models.Distance.COSINE
                ),
            )
        info = client.get_collection(collection)
        params = info.config.params.vectors
        if (
            not isinstance(params, models.VectorParams)
            or params.size != embedder.dimension
            or params.distance != models.Distance.COSINE
        ):
            raise ValueError("Collection vector configuration does not match the model")

    def health(self):
        with self.lock:
            self.client.get_collection(self.collection)

    def add(self, document: Document) -> int:
        with self.lock:
            existing = self.client.count(
                self.collection,
                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", match=models.MatchValue(value=document.id)
                        )
                    ]
                ),
                exact=True,
            )
            if existing.count:
                raise DuplicateDocument
            chunks = self.embedder.chunks(document.text)
            vectors = self.embedder.encode([chunk.text for chunk in chunks])
            points = [
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, f"hdf-rag:{document.id}:{index}")),
                    vector=vector,
                    payload={
                        "document_id": document.id,
                        "title": document.title,
                        "chunk": chunk.text,
                        "chunk_index": index,
                        "start_char": chunk.start,
                        "end_char": chunk.end,
                    },
                )
                for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
            ]
            self.client.upsert(self.collection, points=points, wait=True)
            return len(points)

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        with self.lock:
            vector = self.embedder.encode([query], query=True)[0]
            hits = self.client.query_points(
                self.collection, query=vector, limit=top_k, with_payload=True
            ).points
            return [
                SearchResult(
                    **{
                        key: hit.payload[key]
                        for key in ("document_id", "title", "chunk", "chunk_index")
                    },
                    score=hit.score,
                )
                for hit in hits
            ]
