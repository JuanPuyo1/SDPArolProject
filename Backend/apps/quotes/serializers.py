from .models import Order, OrderLine


def order_line_to_dict(line: OrderLine) -> dict:
    return {
        'orderLineId': line.order_line_id,
        'fulfillmentStatus': line.fulfillment_status,
    }


def order_to_dict(order: Order) -> dict:
    return {
        'orderId': order.order_id,
        'quoteId': order.quote_id,
        'companyId': order.company_id,
        'orderStatus': order.order_status,
        'orderDate': order.order_date.isoformat(),
        'expectedDeliveryDate': order.expected_delivery_date.isoformat(),
        'shipmentStatus': order.shipment_status,
        'currency': order.currency,
        'notes': order.notes,
        'lines': [order_line_to_dict(line) for line in order.lines.all()],
    }
