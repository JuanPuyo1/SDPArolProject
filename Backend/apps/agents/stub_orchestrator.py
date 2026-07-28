"""Stub orchestrator — delegates to TroubleshootingServiceAgent for local / CI."""

from __future__ import annotations

from collections.abc import Iterator

from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk
from apps.agents.troubleshooting_service_agent import TroubleshootingServiceAgent


class StubOrchestrator:
    """OrchestratorPort adapter that runs the dev Troubleshooting & Service agent."""

    def __init__(self) -> None:
        self._agent = TroubleshootingServiceAgent()

    def run(
        self,
        *,
        customer_id: str,
        machine_serial: str,
        message: str,
        attachments: list[ChatAttachmentRef] | None = None,
    ) -> Iterator[OrchestratorChunk]:
        yield from self._agent.run(
            customer_id=customer_id,
            machine_serial=machine_serial,
            message=message,
            attachments=attachments,
        )
        yield OrchestratorChunk(type='done')
