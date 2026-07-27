from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import Machine
from .serializers import machine_summary_to_dict, machine_to_dict


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({'error': message}, status=status)


def _owned_queryset(request: HttpRequest):
    return Machine.objects.filter(owner=request.user).prefetch_related('main_units')


@require_GET
def machine_list(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return _json_error('Authentication required.', status=401)

    machines = _owned_queryset(request)
    return JsonResponse({
        'machines': [machine_summary_to_dict(m) for m in machines],
    })


@require_GET
def machine_detail(request: HttpRequest, serial_number: str) -> JsonResponse:
    if not request.user.is_authenticated:
        return _json_error('Authentication required.', status=401)

    machine = get_object_or_404(_owned_queryset(request), serial_number=serial_number)
    return JsonResponse({'machine': machine_to_dict(machine)})


@require_GET
def machine_default(request: HttpRequest) -> JsonResponse:
    """
    Return the first machine owned by the current user.
    Used by the frontend Machine / Manual pages until multi-machine pickers exist.
    """
    if not request.user.is_authenticated:
        return _json_error('Authentication required.', status=401)

    machine = _owned_queryset(request).first()
    if machine is None:
        return _json_error('No machines assigned to this account.', status=404)

    return JsonResponse({'machine': machine_to_dict(machine)})
