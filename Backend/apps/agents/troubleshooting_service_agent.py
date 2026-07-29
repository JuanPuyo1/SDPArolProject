"""
Troubleshooting & Service dev agent — Option A adapter.

Plans MCP tool calls for alarm/diagnosis and service escalation intents,
streams step + tool + token chunks for the thinking-chain UI, and synthesizes
a reply via Anthropic (when configured) or a canned fallback.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from enum import Enum
from typing import Any

from django.conf import settings

from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk
from apps.mcp_server import registry


class AgentIntent(str, Enum):
    TROUBLESHOOTING = 'troubleshooting'
    SERVICE = 'service'
    GENERAL = 'general'


class TroubleshootingServiceAgent:
    """Dev agent for troubleshooting diagnosis and service ticket escalation."""

    AGENT_ID = 'troubleshooting_service'

    def run(
        self,
        *,
        customer_id: str,
        machine_serial: str,
        message: str,
        attachments: list[ChatAttachmentRef] | None = None,
    ) -> Iterator[OrchestratorChunk]:
        attachments = attachments or []
        intent = classify_intent(message)
        tool_context: list[dict[str, Any]] = []

        yield OrchestratorChunk(
            type='step',
            content=f'Routing to {intent.value} agent…',
        )

        yield from self._invoke_tool(
            tool_name='get_machine_info',
            params={'customer_id': customer_id, 'machine_serial': machine_serial},
            step_label='Loading machine context…',
            tool_context=tool_context,
        )

        machine_entry = tool_context[-1]
        if machine_entry['result'].get('status') != 'ok':
            yield OrchestratorChunk(
                type='error',
                message=machine_entry['result'].get('message', 'Machine lookup failed.'),
            )
            return

        if _mentions_manual_lookup(message):
            yield from self._run_manual_chain(
                customer_id=customer_id,
                machine_serial=machine_serial,
                message=message,
                tool_context=tool_context,
            )
        elif intent is AgentIntent.TROUBLESHOOTING:
            yield from self._run_troubleshooting_chain(
                customer_id=customer_id,
                machine_serial=machine_serial,
                message=message,
                tool_context=tool_context,
            )
        elif intent is AgentIntent.SERVICE:
            yield from self._run_service_chain(
                customer_id=customer_id,
                machine_serial=machine_serial,
                message=message,
                tool_context=tool_context,
            )

        api_key = getattr(settings, 'ANTHROPIC_API_KEY', '') or ''
        if api_key:
            yield from _stream_anthropic(
                intent=intent,
                message=message,
                attachments=attachments,
                tool_context=tool_context,
                machine_serial=machine_serial,
                api_key=api_key,
            )
        else:
            yield from _stream_canned(
                intent=intent,
                message=message,
                attachments=attachments,
                tool_context=tool_context,
                machine_serial=machine_serial,
            )

        yield OrchestratorChunk(type='done')

    def _run_manual_chain(
        self,
        *,
        customer_id: str,
        machine_serial: str,
        message: str,
        tool_context: list[dict[str, Any]],
    ) -> Iterator[OrchestratorChunk]:
        yield from self._invoke_tool(
            tool_name='search_manual',
            params={
                'customer_id': customer_id,
                'machine_serial': machine_serial,
                'query': message,
                'top_k': 5,
            },
            step_label='Searching the machine manual for relevant guidance…',
            tool_context=tool_context,
        )

    def _run_troubleshooting_chain(
        self,
        *,
        customer_id: str,
        machine_serial: str,
        message: str,
        tool_context: list[dict[str, Any]],
    ) -> Iterator[OrchestratorChunk]:
        yield from self._invoke_tool(
            tool_name='search_error_codes',
            params={
                'customer_id': customer_id,
                'machine_serial': machine_serial,
                'query': message,
                'top_k': 5,
            },
            step_label='Searching error codes and recommended actions…',
            tool_context=tool_context,
        )

        yield from self._invoke_tool(
            tool_name='search_manual',
            params={
                'customer_id': customer_id,
                'machine_serial': machine_serial,
                'query': message,
                'top_k': 5,
            },
            step_label='Searching manual for related procedures…',
            tool_context=tool_context,
        )

        if _mentions_telemetry(message):
            metric = _telemetry_metric(message)
            yield from self._invoke_tool(
                tool_name='query_telemetry',
                params={
                    'customer_id': customer_id,
                    'machine_serial': machine_serial,
                    'metric': metric,
                },
                step_label=f'Querying recent {metric.replace("_", " ")} readings…',
                tool_context=tool_context,
            )

    def _run_service_chain(
        self,
        *,
        customer_id: str,
        machine_serial: str,
        message: str,
        tool_context: list[dict[str, Any]],
    ) -> Iterator[OrchestratorChunk]:
        priority = _ticket_priority(message)
        category = _ticket_category(message)

        yield from self._invoke_tool(
            tool_name='create_ticket',
            params={
                'customer_id': customer_id,
                'machine_serial': machine_serial,
                'subject': message[:120] or 'Support request',
                'description': message,
                'priority': priority,
                'category': category,
            },
            step_label='Opening field-support ticket…',
            tool_context=tool_context,
        )

        if _has_troubleshooting_context(message):
            yield from self._invoke_tool(
                tool_name='search_error_codes',
                params={
                    'customer_id': customer_id,
                    'machine_serial': machine_serial,
                    'query': message,
                    'top_k': 3,
                },
                step_label='Attaching troubleshooting context to ticket…',
                tool_context=tool_context,
            )

    def _invoke_tool(
        self,
        *,
        tool_name: str,
        params: dict[str, Any],
        step_label: str,
        tool_context: list[dict[str, Any]],
    ) -> Iterator[OrchestratorChunk]:
        yield OrchestratorChunk(type='step', content=step_label)
        result = registry.invoke(tool_name, params)
        yield OrchestratorChunk(type='tool', tool=tool_name, data=result)
        tool_context.append({'tool': tool_name, 'result': result})


def classify_intent(message: str) -> AgentIntent:
    text = message.lower()
    if re.search(
        r'\b(ticket|technician|technicians|escalate|field service|send support|call support)\b',
        text,
    ):
        return AgentIntent.SERVICE
    if re.search(
        r'\b(e\d{2,4}|alarm|error|fault|troubleshoot|jam|broken|not starting|failure|warning)\b',
        text,
    ):
        return AgentIntent.TROUBLESHOOTING
    return AgentIntent.GENERAL


def _mentions_manual_lookup(message: str) -> bool:
    return bool(
        re.search(
            r'\b(manual|maintenance|procedure|adjust|torque|pressure|settings|guide|how to|how do i|operate|replace|inspect|clean|alignment|alignment|service)\b',
            message.lower(),
        ),
    )


def _mentions_telemetry(message: str) -> bool:
    return bool(
        re.search(r'\b(temperature|cycle|telemetry|metric|pressure|reading)\b', message.lower()),
    )


def _telemetry_metric(message: str) -> str:
    text = message.lower()
    if 'temp' in text:
        return 'temperature'
    if 'pressure' in text:
        return 'pressure'
    return 'cycle_count'


def _ticket_priority(message: str) -> str:
    text = message.lower()
    if re.search(r'\b(critical|urgent|emergency|down|stopped)\b', text):
        return 'critical'
    if re.search(r'\b(asap|high|important)\b', text):
        return 'high'
    return 'medium'


def _ticket_category(message: str) -> str:
    text = message.lower()
    if re.search(r'\b(spare|part|order)\b', text):
        return 'spare_parts'
    if re.search(r'\b(maintenance|pm|preventive)\b', text):
        return 'maintenance'
    return 'support'


def _has_troubleshooting_context(message: str) -> bool:
    return classify_intent(message) is AgentIntent.TROUBLESHOOTING or bool(
        re.search(r'\b(e\d{2,4}|alarm|error|fault|jam)\b', message.lower()),
    )


def _stream_anthropic(
    *,
    intent: AgentIntent,
    message: str,
    attachments: list[ChatAttachmentRef],
    tool_context: list[dict[str, Any]],
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
            'Attachment analysis is not wired yet — acknowledge receipt only.'
        )

    persona = {
        AgentIntent.TROUBLESHOOTING: (
            'You are the Arol Troubleshooting Agent for packaging machinery. '
            'Diagnose alarms and symptoms using MCP tool results. '
            'Give clear recommended actions and safety notes. '
            'If data is stub=true, say the lookup is simulated but still useful.'
        ),
        AgentIntent.SERVICE: (
            'You are the Arol Service Agent for packaging machinery. '
            'Confirm the support ticket details from MCP tool results. '
            'Summarize what was reported and next steps for field support.'
        ),
        AgentIntent.GENERAL: (
            'You are the Arol customer-platform assistant for packaging machinery. '
            'Answer concisely using the MCP tool results provided.'
        ),
    }[intent]

    system_prompt = (
        f'{persona} '
        'Never invent machine serial numbers or cross-tenant data. '
        'Reference specific error codes or ticket IDs when present in tool data.'
    )

    user_content = (
        f'Agent: {TroubleshootingServiceAgent.AGENT_ID}\n'
        f'Intent: {intent.value}\n'
        f'Machine serial: {machine_serial}\n'
        f'User message: {message}{attachment_note}\n\n'
        f'MCP tool results (JSON):\n{tool_context}'
    )

    yield OrchestratorChunk(type='step', content='Synthesizing answer…')

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
    except Exception as exc:  # noqa: BLE001
        yield OrchestratorChunk(
            type='error',
            message=f'Anthropic request failed: {exc}',
        )


def _stream_canned(
    *,
    intent: AgentIntent,
    message: str,
    attachments: list[ChatAttachmentRef],
    tool_context: list[dict[str, Any]],
    machine_serial: str,
) -> Iterator[OrchestratorChunk]:
    machine = {}
    for entry in tool_context:
        if entry['tool'] == 'get_machine_info' and entry['result'].get('status') == 'ok':
            machine = entry['result']['data'].get('machine', {})
            break

    model_name = machine.get('identification', {}).get('model') or machine.get('model') or 'your machine'
    ticket_id = _extract_ticket_id(tool_context)
    error_codes = _extract_error_codes(tool_context)

    lines = [
        f'[{TroubleshootingServiceAgent.AGENT_ID} · {intent.value}]',
        f'Scoped to {machine_serial} ({model_name}).',
        f'You asked: "{message.strip()}"',
    ]

    extra_tools = [e['tool'] for e in tool_context if e['tool'] != 'get_machine_info']
    if extra_tools:
        lines.append(f'MCP tools called: {", ".join(extra_tools)}.')

    if error_codes:
        lines.append(f'Error codes found: {", ".join(error_codes)}.')

    if ticket_id:
        lines.append(f'Support ticket opened: {ticket_id}.')

    if attachments:
        lines.append(
            f'Received {len(attachments)} attachment(s) — processing will arrive with LangGraph.',
        )

    lines.append(
        'Set ANTHROPIC_API_KEY for LLM-backed replies; ORCHESTRATOR_BACKEND=langgraph for production.',
    )

    yield OrchestratorChunk(type='step', content='Synthesizing answer…')

    for token in ' '.join(lines).split(' '):
        yield OrchestratorChunk(type='token', content=token + ' ')


def _extract_ticket_id(tool_context: list[dict[str, Any]]) -> str | None:
    for entry in tool_context:
        if entry['tool'] != 'create_ticket':
            continue
        result = entry['result']
        if result.get('status') == 'ok':
            return result.get('data', {}).get('ticket_id')
    return None


def _extract_error_codes(tool_context: list[dict[str, Any]]) -> list[str]:
    codes: list[str] = []
    for entry in tool_context:
        if entry['tool'] != 'search_error_codes':
            continue
        result = entry['result']
        if result.get('status') != 'ok':
            continue
        for hit in result.get('data', {}).get('hits', []):
            code = hit.get('code')
            if code:
                codes.append(code)
    return codes
