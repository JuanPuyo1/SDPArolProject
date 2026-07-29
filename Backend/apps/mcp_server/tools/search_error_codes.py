"""search_error_codes — troubleshooting knowledge backed by Qdrant."""

from __future__ import annotations

import logging

from apps.mcp_server.rag_engine import search as rag_search
from apps.mcp_server.schemas.troubleshooting import (
    ErrorCodeHit,
    SearchErrorCodesInput,
    SearchErrorCodesOutput,
)
from apps.mcp_server.scoping import get_owned_machine

log = logging.getLogger(__name__)


def search_error_codes(params: SearchErrorCodesInput) -> SearchErrorCodesOutput:
    machine = get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )

    raw_hits = rag_search.search_error_codes(
        query=params.query,
        machine_model=machine.model,
        top_k=params.top_k,
    )

    hits = [
        ErrorCodeHit(
            code=h.get('code') or 'UNKNOWN',
            title=h.get('title') or 'Troubleshooting match',
            severity=h.get('severity'),
            summary=h.get('summary', ''),
            recommended_actions=list(h.get('recommended_actions') or []),
        )
        for h in raw_hits
    ]
    log.info(
        'search_error_codes model=%s query=%r hits=%d',
        machine.model,
        params.query,
        len(hits),
    )
    return SearchErrorCodesOutput(query=params.query, hits=hits)
