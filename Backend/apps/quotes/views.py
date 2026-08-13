from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from apps.authentication.visibility import COMMERCIAL_VISIBLE, require_visibility

from .models import Order
from .serializers import order_to_dict


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({'error': message}, status=status)


def _owned_orders(request: HttpRequest):
    company_id = getattr(request.user, 'company_id', None)
    if not company_id:
        return Order.objects.none()
    return (
        Order.objects.filter(company_id=company_id)
        .select_related('quote', 'company')
        .prefetch_related('lines')
    )


@require_GET
def order_list(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return _json_error('Authentication required.', status=401)

    denied = require_visibility(
        request,
        COMMERCIAL_VISIBLE,
        domain='orders',
    )
    if denied is not None:
        return denied

    orders = _owned_orders(request)
    return JsonResponse({
        'orders': [order_to_dict(order) for order in orders],
    })
