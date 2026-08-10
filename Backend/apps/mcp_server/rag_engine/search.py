"""
Vector search for the Manuals and Troubleshooting MCP tools.

These are the only two functions the MCP tool layer needs to call. Anything
deeper (collection management, embeddings, ingest) stays private to this engine.

The query path mirrors the notebook:

1. embed the query with FastEmbed,
2. filter by ``machine_serial`` when supplied (the tenant boundary),
3. return ``parent_content`` so the LLM gets full surrounding context, not just
   the matched child chunk — this is the entire reason for the parent/child
   splitting strategy.
"""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import models

from .client import get_client
from .collections import (
    ensure_error_codes_collection,
    ensure_manuals_collection,
)
from .embeddings import embed_query

log = logging.getLogger(__name__)


def _build_machine_serial_filter(
    machine_serial: str | None = None,
    machine_model: str | None = None,
) -> models.Filter | None:
    if not machine_serial and not machine_model:
        return None
    conditions = []
    if machine_serial:
        conditions.append(models.FieldCondition(key='machine_serial', match=models.MatchValue(value=machine_serial)))
    if machine_model and machine_model != machine_serial:
        conditions.append(models.FieldCondition(key='machine_serial', match=models.MatchValue(value=machine_model)))
    conditions.append(models.FieldCondition(key='machine_serial', match=models.MatchValue(value='AROL_GENERAL')))
    conditions.append(models.FieldCondition(key='doc_type', match=models.MatchValue(value='general_catalogue')))

    return models.Filter(should=conditions)


def search_manuals(
    *,
    query: str,
    machine_serial: str | None = None,
    machine_model: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Return ranked manual passages for ``query``, optionally scoped to a machine serial.

    The MCP tool converts each returned dict into a ``ManualHit`` Pydantic model.
    """
    if not query or not query.strip():
        return []

    target_serial = machine_serial or machine_model
    top_k = max(1, min(int(top_k), 20))
    client = get_client()
    collection = ensure_manuals_collection(client)

    vector = embed_query(query)
    query_filter = _build_machine_serial_filter(target_serial)
    hits = client.query_points(
        collection_name=collection,
        query=vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    ).points

    if not hits and query_filter is not None:
        log.info(
            'search_manuals no filtered hits for serial=%r, retrying without filter',
            target_serial,
        )
        hits = client.query_points(
            collection_name=collection,
            query=vector,
            limit=top_k,
            with_payload=True,
        ).points

    results: list[dict[str, Any]] = []
    for hit in hits:
        payload = hit.payload or {}
        serial_val = payload.get('machine_serial') or payload.get('machine_model', 'AROL')
        results.append(
            {
                'title': f"{serial_val} Manual",
                'excerpt': payload.get('parent_content')
                or payload.get('child_content', ''),
                'matched_segment': payload.get('child_content'),
                'page_number': payload.get('page_number'),
                'page': payload.get('page_number'),  # Alias for backward compatibility if code calls .get('page')
                'score': float(hit.score) if hit.score is not None else None,
                'source': payload.get('source') or payload.get('doc_id'),
                'doc_type': payload.get('doc_type'),
            },
        )
    log.info(
        'search_manuals q=%r serial=%r hits=%d',
        query,
        target_serial,
        len(results),
    )
    return results


def search_error_codes(
    *,
    query: str,
    machine_serial: str | None = None,
    machine_model: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Return ranked error-code entries for ``query``.

    The MCP tool converts each dict into an ``ErrorCodeHit`` Pydantic model.
    """
    if not query or not query.strip():
        return []

    target_serial = machine_serial or machine_model
    top_k = max(1, min(int(top_k), 20))
    client = get_client()
    collection = ensure_error_codes_collection(client)

    vector = embed_query(query)
    query_filter = _build_machine_serial_filter(target_serial)
    hits = client.query_points(
        collection_name=collection,
        query=vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    ).points

    if not hits and query_filter is not None:
        log.info(
            'search_error_codes no filtered hits for serial=%r, retrying without filter',
            target_serial,
        )
        hits = client.query_points(
            collection_name=collection,
            query=vector,
            limit=top_k,
            with_payload=True,
        ).points

    results: list[dict[str, Any]] = []
    for hit in hits:
        payload = hit.payload or {}
        results.append(
            {
                'code': payload.get('code', ''),
                'title': payload.get('title', ''),
                'severity': payload.get('severity'),
                'summary': payload.get('summary', ''),
                'recommended_actions': list(
                    payload.get('recommended_actions') or [],
                ),
                'score': float(hit.score) if hit.score is not None else None,
                'source': payload.get('source'),
            },
        )
    log.info(
        'search_error_codes q=%r serial=%r hits=%d',
        query,
        target_serial,
        len(results),
    )
    return results
