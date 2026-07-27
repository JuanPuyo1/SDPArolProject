"""Schemas for troubleshooting / error-code lookup (Troubleshooting Agent)."""

from pydantic import BaseModel, Field

from .common import ScopedContext


class SearchErrorCodesInput(ScopedContext):
    query: str = Field(
        ...,
        min_length=1,
        description='Error code, alarm text, or symptom description.',
    )
    top_k: int = Field(default=5, ge=1, le=20)


class ErrorCodeHit(BaseModel):
    code: str
    title: str
    severity: str | None = None
    summary: str
    recommended_actions: list[str] = Field(default_factory=list)


class SearchErrorCodesOutput(BaseModel):
    stub: bool = True
    query: str
    hits: list[ErrorCodeHit]
    note: str = 'search_error_codes is a stub until troubleshooting knowledge is ingested.'
