"""search_manual — RAG over the manuals Qdrant collection (Manuals Agent)."""

from __future__ import annotations

import logging

from apps.mcp_server.rag_engine import search as rag_search
from apps.mcp_server.schemas.manual import ManualHit, SearchManualInput, SearchManualOutput
from apps.mcp_server.scoping import get_owned_machine

log = logging.getLogger(__name__)


def search_manual(params: SearchManualInput) -> SearchManualOutput:
    machine = get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )

    raw_hits = rag_search.search_manuals(
        query=params.query,
        machine_serial=machine.serial_number,
        machine_model=machine.model,
        top_k=params.top_k,
    )

    hits = [
        ManualHit(
            title=h.get('title') or f'{machine.model} Use and Maintenance Manual',
            excerpt=h.get('excerpt') or '',
            page_number=h.get('page_number'),
            page=h.get('page_number'),
            score=h.get('score'),
            source=h.get('source') or machine.manual_url or None,
        )
        for h in raw_hits
    ]
    log.info(
        'search_manual serial=%s model=%s query=%r hits=%d',
        machine.serial_number,
        machine.model,
        params.query,
        len(hits),
    )
    return SearchManualOutput(query=params.query, hits=hits)
