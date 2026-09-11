import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from qdrant_client import QdrantClient

from app.config import Settings
from app.embedding import InvalidText, LocalEmbedder
from app.schemas import Document, DocumentResponse, HealthResponse, SearchRequest, SearchResponse
from app.service import DuplicateDocument, RetrievalService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, embedder=None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
        logger.info("Loading embedding model and opening document store")
        model = embedder if embedder is not None else LocalEmbedder()
        client = (
            QdrantClient(url=settings.qdrant_url, timeout=10)
            if settings.qdrant_url
            else QdrantClient(path=settings.qdrant_path)
        )
        try:
            app.state.service = RetrievalService(client, model, settings.collection)
            logger.info("Document search service ready")
            yield
        finally:
            client.close()

    app = FastAPI(title="Local Document Search", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(DuplicateDocument)
    async def duplicate_handler(request: Request, exc: DuplicateDocument):
        return JSONResponse(status_code=409, content={"detail": "Document ID already exists"})

    @app.exception_handler(InvalidText)
    async def value_handler(request: Request, exc: InvalidText):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def error_handler(request: Request, exc: Exception):
        # Avoid logging document text, queries, or upstream exception bodies.
        logger.error(
            "Request failed: method=%s path=%s error_type=%s",
            request.method,
            request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})

    @app.get(
        "/health",
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse, "description": "Qdrant check failed"}},
    )
    def health(request: Request, response: Response):
        qdrant = {
            "mode": "server" if settings.qdrant_url else "embedded",
            "collection": settings.collection,
        }
        started = perf_counter()
        try:
            qdrant.update(request.app.state.service.health())
            qdrant["reachable"] = True
            healthy = qdrant["collection_status"] in {"green", "yellow"}
            qdrant["status"] = "ok" if healthy else "degraded"
        except Exception as exc:  # noqa: BLE001 - health boundary sanitizes all backend failures
            logger.warning("Qdrant health check failed: error_type=%s", type(exc).__name__)
            healthy = False
            qdrant.update(
                status="unavailable",
                reachable=False,
                detail="Could not read the configured Qdrant collection",
            )
        qdrant["check_duration_ms"] = round((perf_counter() - started) * 1000, 2)
        if not healthy:
            response.status_code = 503
        return {"status": "ok" if healthy else "degraded", "qdrant": qdrant}

    @app.post("/documents", status_code=201, response_model=DocumentResponse)
    def add_document(document: Document, request: Request):
        count = request.app.state.service.add(document)
        logger.info("Document indexed: chunks=%d", count)
        return DocumentResponse(document_id=document.id, chunks=count)

    @app.post("/search", response_model=SearchResponse)
    def search(body: SearchRequest, request: Request):
        results = request.app.state.service.search(body.query, body.top_k)
        logger.info("Search completed: results=%d", len(results))
        return SearchResponse(results=results)

    return app


app = create_app()
