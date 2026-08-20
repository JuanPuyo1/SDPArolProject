from django.db.models import Q
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from apps.authentication.visibility import OPERATIONAL_VISIBLE, require_visibility

from .models import Machine, MaintenanceTicket
from .serializers import (
    machine_summary_to_dict,
    machine_to_dict,
    maintenance_ticket_to_dict,
)


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({'error': message}, status=status)


def _owned_queryset(request: HttpRequest):
    company_id = getattr(request.user, 'company_id', None)
    if not company_id:
        return Machine.objects.none()
    return (
        Machine.objects.filter(company_id=company_id)
        .select_related('model', 'company')
        .prefetch_related('main_units')
    )


def _owned_tickets(request: HttpRequest):
    company_id = getattr(request.user, 'company_id', None)
    if not company_id:
        return MaintenanceTicket.objects.none()
    return (
        MaintenanceTicket.objects.filter(machine__company_id=company_id)
        .select_related('machine', 'alarm')
    )


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
    """Look up an owned machine by serial number or machineId."""
    if not request.user.is_authenticated:
        return _json_error('Authentication required.', status=401)

    identifier = serial_number.strip()
    qs = _owned_queryset(request)
    machine = qs.filter(serial_number=identifier).first()
    if machine is None:
        machine = qs.filter(machine_id=identifier).first()
    if machine is None:
        exists = Machine.objects.filter(
            Q(serial_number=identifier) | Q(machine_id=identifier),
        ).exists()
        if exists:
            return _json_error(
                'This machine is not assigned to your account.',
                status=403,
            )
        return _json_error('Machine not found.', status=404)

    return JsonResponse({'machine': machine_to_dict(machine)})


@require_GET
def machine_default(request: HttpRequest) -> JsonResponse:
    """
    Return the first machine owned by the current user's company.
    Used by the frontend Machine / Manual pages until multi-machine pickers exist.
    """
    if not request.user.is_authenticated:
        return _json_error('Authentication required.', status=401)

    machine = _owned_queryset(request).first()
    if machine is None:
        return _json_error('No machines assigned to this account.', status=404)

    return JsonResponse({'machine': machine_to_dict(machine)})


@require_GET
def maintenance_ticket_list(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return _json_error('Authentication required.', status=401)

    denied = require_visibility(
        request,
        OPERATIONAL_VISIBLE,
        domain='maintenance tickets',
    )
    if denied is not None:
        return denied

    tickets = _owned_tickets(request)
    return JsonResponse({
        'tickets': [maintenance_ticket_to_dict(ticket) for ticket in tickets],
    })
