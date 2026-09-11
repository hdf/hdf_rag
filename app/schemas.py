from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Document(StrictModel):
    id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100_000)]


class SearchRequest(StrictModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    top_k: Annotated[int, Field(strict=True, ge=1, le=20)] = 3


class DocumentResponse(BaseModel):
    document_id: str
    chunks: int


class SearchResult(BaseModel):
    document_id: str
    title: str
    chunk: str
    chunk_index: int
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]
