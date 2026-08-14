"""Chat HTTP/SSE views — auth boundary only; orchestration via OrchestratorPort."""

from __future__ import annotations

import json
import uuid

from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST

from apps.agents.factory import get_orchestrator
from apps.agents.ports import OrchestratorChunk
from apps.machines.models import Machine


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({'error': message}, status=status)


def _parse_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return {}


def _chunk_to_sse(chunk: OrchestratorChunk) -> str:
    payload = {'type': chunk.type}
    if chunk.content:
        payload['content'] = chunk.content
    if chunk.tool:
        payload['tool'] = chunk.tool
    if chunk.data is not None:
        payload['data'] = chunk.data
    if chunk.message:
        payload['message'] = chunk.message
    if chunk.agent:
        payload['agent'] = chunk.agent
    return f'data: {json.dumps(payload, default=str)}\n\n'


def _owned_machines(request: HttpRequest):
    company_id = getattr(request.user, 'company_id', None)
    if not company_id:
        return Machine.objects.none()
    return Machine.objects.filter(company_id=company_id)


def _resolve_machine_serial(request: HttpRequest, body: dict) -> str | None:
    qs = _owned_machines(request)
    serial = (body.get('machine_serial') or '').strip()
    if serial:
        return serial if qs.filter(serial_number=serial).exists() else None

    machine = qs.order_by('serial_number').first()
    return machine.serial_number if machine else None


@require_POST
def chat_view(request: HttpRequest) -> StreamingHttpResponse | JsonResponse:
    """
    POST /api/agents/chat/

    Body: { "message": "...", "machine_serial": "A3279" (optional),
            "session_id": "..." (optional) }
    Response: text/event-stream with JSON data lines (token | tool | done | error).

    `session_id` identifies the conversation thread so the agent keeps
    context across turns. Pass back whatever value the previous response's
    X-Session-Id header returned; omit it to start a new conversation (the
    server mints one and returns it the same way).
    """
    if not request.user.is_authenticated:
        return _json_error('Authentication required.', status=401)

    body = _parse_body(request)
    message = (body.get('message') or '').strip()
    if not message:
        return _json_error('message is required.')

    machine_serial = _resolve_machine_serial(request, body)
    if not machine_serial:
        return _json_error(
            'No owned machine found for this account (or invalid machine_serial).',
            status=404,
        )

    session_id = (body.get('session_id') or '').strip() or str(uuid.uuid4())
    customer_id = request.user.username
    orchestrator = get_orchestrator()

    def event_stream():
        try:
            for chunk in orchestrator.run(
                customer_id=customer_id,
                machine_serial=machine_serial,
                message=message,
                session_id=session_id,
            ):
                yield _chunk_to_sse(chunk)
                if chunk.type in {'error', 'done'}:
                    break
        except NotImplementedError as exc:
            yield _chunk_to_sse(OrchestratorChunk(type='error', message=str(exc)))
            yield _chunk_to_sse(OrchestratorChunk(type='done'))
        except Exception as exc:  # noqa: BLE001
            yield _chunk_to_sse(
                OrchestratorChunk(type='error', message=f'Orchestrator failed: {exc}'),
            )
            yield _chunk_to_sse(OrchestratorChunk(type='done'))

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['X-Session-Id'] = session_id
    response['Access-Control-Expose-Headers'] = 'X-Session-Id'
    return response
