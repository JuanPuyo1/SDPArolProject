import json

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_not_required
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .serializers import user_to_dict


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({'error': message}, status=status)


def _parse_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return {}


@login_not_required
@ensure_csrf_cookie
@require_GET
def csrf_view(request: HttpRequest) -> JsonResponse:
    """Ensure the CSRF cookie is set for SPA clients."""
    return JsonResponse({'detail': 'CSRF cookie set'})


@login_not_required
@require_http_methods(['GET', 'POST'])
def login_view(request: HttpRequest) -> JsonResponse:
    """
    GET: return the current session user if authenticated.
    POST: authenticate credentials and create a session (Django login()).
    """
    if request.method == 'GET':
        if request.user.is_authenticated:
            return JsonResponse({'user': user_to_dict(request.user)})
        return _json_error('Not authenticated', status=401)

    data = _parse_body(request)
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return _json_error('Username and password are required.')

    user = authenticate(request, username=username, password=password)
    if user is None:
        return _json_error('Invalid username or password.', status=401)

    login(request, user)
    return JsonResponse({'user': user_to_dict(user)})


@require_POST
def logout_view(request: HttpRequest) -> JsonResponse:
    logout(request)
    return JsonResponse({'detail': 'Logged out'})


@require_GET
def profile_view(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return _json_error('Authentication required.', status=401)
    return JsonResponse({'user': user_to_dict(request.user)})


@require_http_methods(['GET', 'PATCH'])
def profile_update_view(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return _json_error('Authentication required.', status=401)

    user = request.user

    if request.method == 'GET':
        return JsonResponse({'user': user_to_dict(user)})

    data = _parse_body(request)
    allowed_fields = ('first_name', 'last_name', 'email')
    for field in allowed_fields:
        if field in data:
            setattr(user, field, (data[field] or '').strip())
    user.save()
    return JsonResponse({'user': user_to_dict(user)})
