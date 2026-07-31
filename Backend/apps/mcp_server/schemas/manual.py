"""Schemas for manual / RAG search (Manuals Agent)."""

from pydantic import BaseModel, Field

from .common import ScopedContext


class SearchManualInput(ScopedContext):
    query: str = Field(..., min_length=1, description='Natural-language or keyword query.')
    top_k: int = Field(default=5, ge=1, le=20, description='Max passages to return.')


class ManualHit(BaseModel):
    title: str
    excerpt: str
    page_number: int | None = None
    page: int | None = None
    score: float | None = None
    source: str | None = None


class SearchManualOutput(BaseModel):
    query: str
    hits: list[ManualHit]
