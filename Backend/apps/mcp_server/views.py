"""
Optional HTTP debug endpoints for MCP tools.

Intended for local development and partner integration tests.
Do not expose unauthenticated in production.
"""

from __future__ import annotations

import json

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from apps.mcp_server import registry


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({'status': 'error', 'message': message}, status=status)


def _parse_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return {}


@require_GET
def list_tools_view(request: HttpRequest) -> JsonResponse:
    """GET /api/mcp/tools/?agent=manuals — discover tools (+ optional agent filter)."""
    agent = request.GET.get('agent') or None
    return JsonResponse({'tools': registry.list_tools(agent=agent)})


@csrf_exempt
@require_http_methods(['POST'])
def invoke_tool_view(request: HttpRequest, tool_name: str) -> JsonResponse:
    """
    POST /api/mcp/tools/<tool_name>/invoke/

    Body JSON = tool params (must include customer_id / machine_serial when required).
    """
    if not getattr(settings, 'MCP_HTTP_INVOKE_ENABLED', False):
        return _json_error(
            'MCP invoke HTTP endpoint is disabled (MCP_HTTP_INVOKE_ENABLED=False).',
            status=403,
        )

    body = _parse_body(request)
    result = registry.invoke(tool_name, body)
    http_status = 200 if result.get('status') == 'ok' else 400
    if result.get('code') in {'NOT_FOUND', 'UNKNOWN_TOOL'}:
        http_status = 404
    elif result.get('code') == 'FORBIDDEN':
        http_status = 403
    return JsonResponse(result, status=http_status)
