"""
Stub orchestrator — local / CI simulator with real MCP tool calls.

Calls 1–2 MCP tools for tenant-scoped context, then streams a reply via
Anthropic (when ANTHROPIC_API_KEY is set) or a canned fallback for CI.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from django.conf import settings

from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk
from apps.mcp_server import registry


class StubOrchestrator:
    """Rule-based stub that exercises MCP tools and streams SSE-friendly chunks."""

    def run(
        self,
        *,
        customer_id: str,
        machine_serial: str,
        message: str,
        attachments: list[ChatAttachmentRef] | None = None,
    ) -> Iterator[OrchestratorChunk]:
        attachments = attachments or []
        tool_context: list[dict] = []

        machine_result = registry.invoke(
            'get_machine_info',
            {'customer_id': customer_id, 'machine_serial': machine_serial},
        )
        yield OrchestratorChunk(type='tool', tool='get_machine_info', data=machine_result)
        tool_context.append({'tool': 'get_machine_info', 'result': machine_result})

        if machine_result.get('status') != 'ok':
            yield OrchestratorChunk(
                type='error',
                message=machine_result.get('message', 'Machine lookup failed.'),
            )
            return

        second_tool = _pick_follow_up_tool(message)
        if second_tool is not None:
            params = {
                'customer_id': customer_id,
                'machine_serial': machine_serial,
                **_second_tool_args(second_tool, message),
            }
            second_result = registry.invoke(second_tool, params)
            yield OrchestratorChunk(type='tool', tool=second_tool, data=second_result)
            tool_context.append({'tool': second_tool, 'result': second_result})

        api_key = getattr(settings, 'ANTHROPIC_API_KEY', '') or ''
        if api_key:
            yield from _stream_anthropic(
                message=message,
                attachments=attachments,
                tool_context=tool_context,
                machine_serial=machine_serial,
                api_key=api_key,
            )
        else:
            yield from _stream_canned(
                message=message,
                attachments=attachments,
                tool_context=tool_context,
                machine_serial=machine_serial,
            )

        yield OrchestratorChunk(type='done')


def _pick_follow_up_tool(message: str) -> str | None:
    text = message.lower()
    if re.search(r'\b(e\d{2,4}|alarm|error|fault|troubleshoot|jam)\b', text):
        return 'search_error_codes'
    if re.search(r'\b(manual|how to|procedure|maintenance|adjust|torque)\b', text):
        return 'search_manual'
    if re.search(r'\b(temperature|cycle|telemetry|metric|pressure)\b', text):
        return 'query_telemetry'
    if re.search(r'\b(spare|part|order|catalog)\b', text):
        return 'list_spare_parts'
    if re.search(r'\b(ticket|technician|support|service)\b', text):
        return 'create_ticket'
    return None


def _second_tool_args(tool: str, message: str) -> dict:
    if tool == 'query_telemetry':
        metric = 'cycle_count'
        if 'temp' in message.lower():
            metric = 'temperature'
        elif 'pressure' in message.lower():
            metric = 'pressure'
        return {'metric': metric}
    if tool == 'create_ticket':
        return {
            'subject': message[:120] or 'Support request',
            'description': message,
            'priority': 'medium',
            'category': 'support',
        }
    return {'query': message, 'top_k': 5}


def _stream_anthropic(
    *,
    message: str,
    attachments: list[ChatAttachmentRef],
    tool_context: list[dict],
    machine_serial: str,
    api_key: str,
) -> Iterator[OrchestratorChunk]:
    import anthropic

    model = getattr(settings, 'ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')
    client = anthropic.Anthropic(api_key=api_key)

    attachment_note = ''
    if attachments:
        names = ', '.join(a.filename for a in attachments)
        attachment_note = (
            f'\n\nThe user attached {len(attachments)} file(s): {names}. '
            'Attachment analysis is not wired in the stub yet — acknowledge receipt only.'
        )

    system_prompt = (
        'You are the Arol customer-platform assistant for packaging machinery. '
        'Answer concisely using the MCP tool results provided. '
        'If tool data is marked stub=true, say the integration is simulated but still helpful. '
        'Never invent machine serial numbers or cross-tenant data.'
    )

    user_content = (
        f'Machine serial: {machine_serial}\n'
        f'User message: {message}{attachment_note}\n\n'
        f'MCP tool results (JSON):\n{tool_context}'
    )

    try:
        with client.messages.stream(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_content}],
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield OrchestratorChunk(type='token', content=text)
    except Exception as exc:  # noqa: BLE001 — surface as SSE error chunk
        yield OrchestratorChunk(
            type='error',
            message=f'Anthropic request failed: {exc}',
        )


def _stream_canned(
    *,
    message: str,
    attachments: list[ChatAttachmentRef],
    tool_context: list[dict],
    machine_serial: str,
) -> Iterator[OrchestratorChunk]:
    machine = {}
    for entry in tool_context:
        if entry['tool'] == 'get_machine_info' and entry['result'].get('status') == 'ok':
            machine = entry['result']['data'].get('machine', {})
            break

    model_name = machine.get('identification', {}).get('model') or machine.get('model') or 'your machine'
    lines = [
        f'[Stub orchestrator] Scoped to {machine_serial} ({model_name}).',
        f'You asked: "{message.strip()}"',
    ]

    extra_tools = [e['tool'] for e in tool_context if e['tool'] != 'get_machine_info']
    if extra_tools:
        lines.append(f'Also called MCP tool(s): {", ".join(extra_tools)}.')

    if attachments:
        lines.append(
            f'Received {len(attachments)} attachment(s) — processing will arrive with LangGraph.',
        )

    lines.append(
        'Set ANTHROPIC_API_KEY for LLM-backed replies; ORCHESTRATOR_BACKEND=langgraph for production.',
    )

    for token in ' '.join(lines).split(' '):
        yield OrchestratorChunk(type='token', content=token + ' ')
