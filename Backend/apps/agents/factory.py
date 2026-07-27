"""Orchestrator backend selection via ORCHESTRATOR_BACKEND env."""

from __future__ import annotations

from django.conf import settings

from apps.agents.ports import OrchestratorPort


def get_orchestrator() -> OrchestratorPort:
    backend = getattr(settings, 'ORCHESTRATOR_BACKEND', 'stub').lower()
    if backend == 'langgraph':
        from apps.agents.langgraph_orchestrator import LangGraphOrchestrator

        return LangGraphOrchestrator()
    from apps.agents.stub_orchestrator import StubOrchestrator

    return StubOrchestrator()
