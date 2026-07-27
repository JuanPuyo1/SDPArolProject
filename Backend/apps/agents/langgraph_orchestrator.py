"""Thin adapter to the partner LangGraph graph (not yet integrated)."""

from __future__ import annotations

from collections.abc import Iterator

from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk, OrchestratorPort


class LangGraphOrchestrator:
    """Placeholder until the partner graph package is wired in."""

    def run(
        self,
        *,
        customer_id: str,
        machine_serial: str,
        message: str,
        attachments: list[ChatAttachmentRef] | None = None,
    ) -> Iterator[OrchestratorChunk]:
        raise NotImplementedError(
            'LangGraph orchestrator is not integrated yet. '
            'Set ORCHESTRATOR_BACKEND=stub for local development.',
        )


def __getattr__(name: str):
    if name == 'LangGraphOrchestrator':
        return LangGraphOrchestrator
    raise AttributeError(name)
