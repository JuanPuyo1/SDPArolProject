"""Role / visibility helpers for HTTP API authorization."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse

# Domains from INFORMATION_FROM_AROL Access Model
COMMERCIAL_VISIBLE = frozenset({'full', 'commercial'})
OPERATIONAL_VISIBLE = frozenset({'full', 'technician'})


def user_visibility(request: HttpRequest) -> str | None:
    return getattr(request.user, 'visibility', None)


def require_visibility(
    request: HttpRequest,
    allowed: frozenset[str],
    *,
    domain: str,
) -> JsonResponse | None:
    """
    Return a 403 JsonResponse when the authenticated user's visibility
    is not in ``allowed``. Call after confirming authentication.
    """
    visibility = user_visibility(request)
    if visibility in allowed:
        return None
    return JsonResponse(
        {
            'error': (
                f'Access denied: your role ({visibility or "unknown"}) '
                f'cannot view {domain}.'
            ),
        },
        status=403,
    )
