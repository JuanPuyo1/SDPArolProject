"""ORM-backed data access for the Orders/Business Agent's MCP tools.

Reads real Quote -> QuoteRevision -> QuoteLine and Order data (apps.quotes.models),
scoped to a company. QuoteLine.price is already net of its QuoteRevision's
discount_rate (see Backend/initiliaze_database.py's importer) -- revision/order
totals are a plain sum of line prices, discount_rate is never reapplied here.
"""

from __future__ import annotations

from apps.core.models import Company
from apps.quotes.models import Order, QuoteRevision


def _revision_amount(revision: QuoteRevision) -> float:
    return float(sum(line.price for line in revision.lines.all()))


def _revision_item_summary(revision: QuoteRevision) -> str:
    descriptions = [line.description for line in revision.lines.all() if line.description]
    return '; '.join(descriptions) if descriptions else revision.change_summary


def quote_history(company: Company, quote_id: str | None = None) -> list[dict]:
    revisions = (
        QuoteRevision.objects.filter(quote__company=company)
        .select_related('quote')
        .prefetch_related('lines')
        .order_by('quote_id', 'revision_number')
    )
    if quote_id:
        revisions = revisions.filter(quote_id=quote_id)
    return [
        {
            'quote_id': revision.quote_id,
            'revision_number': revision.revision_number,
            'quote_date': revision.issued_at.isoformat(),
            'status': revision.revision_status,
            'item_summary': _revision_item_summary(revision),
            'amount_eur': _revision_amount(revision),
        }
        for revision in revisions
    ]


def _order_revision(order: Order) -> QuoteRevision | None:
    """The revision an order's items/total are drawn from: Order has no
    direct FK to the revision it was confirmed from, so this picks the
    quote's 'approved' or 'accepted' revision, falling back to its most recently
    issued revision if none is marked approved."""
    revisions = list(order.quote.revisions.prefetch_related('lines').all())
    if not revisions:
        return None
    approved = [r for r in revisions if r.revision_status.lower() in ('approved', 'accepted')]
    return max(approved or revisions, key=lambda r: r.issued_at)



def order_status(company: Company) -> list[dict]:
    orders = Order.objects.filter(company=company).select_related('quote').prefetch_related('lines')
    records = []
    for order in orders:
        revision = _order_revision(order)
        records.append(
            {
                'order_id': order.order_id,
                'quote_id': order.quote_id,
                'order_date': order.order_date.isoformat(),
                'expected_delivery_date': order.expected_delivery_date.isoformat() if order.expected_delivery_date else None,
                'status': order.order_status,
                'shipment_status': order.shipment_status,
                'currency': order.currency,
                'notes': order.notes,
                'item_summary': _revision_item_summary(revision) if revision else order.notes,
                'amount_eur': _revision_amount(revision) if revision else 0.0,
                'order_lines': [
                    {
                        'order_line_id': line.order_line_id,
                        'fulfillment_status': line.fulfillment_status,
                    }
                    for line in order.lines.all()
                ],
            }
        )
    return records


