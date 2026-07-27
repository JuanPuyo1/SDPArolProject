"""OrchestratorPort — shared interface for Stub and LangGraph backends."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable


ChunkType = Literal['token', 'tool', 'step', 'done', 'error']


@dataclass(frozen=True)
class OrchestratorChunk:
    """Single event emitted while an orchestrator run is streaming."""

    type: ChunkType
    content: str = ''
    tool: str | None = None
    data: dict[str, Any] | None = None
    message: str | None = None


@dataclass(frozen=True)
class ChatAttachmentRef:
    """Lightweight attachment reference passed into the orchestrator."""

    filename: str
    content_type: str
    size: int


@runtime_checkable
class OrchestratorPort(Protocol):
    def run(
        self,
        *,
        customer_id: str,
        machine_serial: str,
        message: str,
        attachments: list[ChatAttachmentRef] | None = None,
    ) -> Iterator[OrchestratorChunk]:
        """Stream orchestrator output chunks for SSE adaptation in views."""
        ...
