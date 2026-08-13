"""Tenant + machine ownership checks used by MCP tools."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser

from apps.machines.models import Machine


class ScopeError(Exception):
    """Raised when customer_id / machine_serial cannot be resolved or authorized."""

    def __init__(self, message: str, *, code: str = 'FORBIDDEN') -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def resolve_customer(customer_id: str) -> AbstractBaseUser:
    """
    Resolve ``customer_id`` to a Django user.

    Accepts user_id (USR-001), username, email, or numeric primary key.
    """
    User = get_user_model()
    cid = customer_id.strip()
    if not cid:
        raise ScopeError('customer_id is required.', code='VALIDATION_ERROR')

    for lookup in ('user_id', 'username', 'email'):
        user = User.objects.filter(**{lookup: cid}).first()
        if user is not None:
            return user

    if cid.isdigit():
        user = User.objects.filter(pk=int(cid)).first()
        if user is not None:
            return user

    raise ScopeError(f'Unknown customer_id: {customer_id!r}.', code='NOT_FOUND')


def get_owned_machine(*, customer_id: str, machine_serial: str) -> Machine:
    """Return the machine if it belongs to the customer's company; otherwise raise ScopeError."""
    user = resolve_customer(customer_id)
    serial = machine_serial.strip()
    if not serial:
        raise ScopeError('machine_serial is required.', code='VALIDATION_ERROR')

    if user.company_id is None:
        raise ScopeError(
            'User is not assigned to a company.',
            code='FORBIDDEN',
        )

    machine = (
        Machine.objects.filter(company_id=user.company_id, serial_number=serial)
        .select_related('model', 'company')
        .prefetch_related('main_units')
        .first()
    )
    if machine is None:
        if Machine.objects.filter(serial_number=serial).exists():
            raise ScopeError(
                'Machine is not assigned to this customer.',
                code='FORBIDDEN',
            )
        raise ScopeError(
            f'Machine serial {serial!r} not found for this customer.',
            code='NOT_FOUND',
        )
    return machine
