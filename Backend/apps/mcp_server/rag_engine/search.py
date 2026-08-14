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

search_error_codes() queries this SAME manuals collection rather than a
separate error-code database: per README_AROL.md, resolving an alarm means
searching the manual of the specific machine that raised it, not a standalone
code -> remedy lookup table (and no such collection is ingested anywhere).
"""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import models
from qdrant_client.conversions.common_types import ScoredPoint

from .client import get_client
from .collections import ensure_manuals_collection
from .embeddings import embed_query

log = logging.getLogger(__name__)


def _build_machine_serial_filter(machine_serial: str | None) -> models.Filter | None:
    if not machine_serial:
        return None
    return models.Filter(
        should=[
            models.FieldCondition(
                key="machine_serial",
                match=models.MatchValue(value=machine_serial),
            ),
            models.FieldCondition(
                key="machine_serial",
                match=models.MatchValue(value="AROL_GENERAL"),
            ),
            models.FieldCondition(
                key="doc_type",
                match=models.MatchValue(value="general_catalogue"),
            ),
        ],
    )


def _query_manuals(query: str, machine_serial: str | None, top_k: int) -> list[ScoredPoint]:
    client = get_client()
    collection = ensure_manuals_collection(client)
    vector = embed_query(query)
    query_filter = _build_machine_serial_filter(machine_serial)
    hits = client.query_points(
        collection_name=collection,
        query=vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    ).points

    if not hits and query_filter is not None:
        log.info(
            "no filtered hits for serial=%r, retrying without machine filter",
            machine_serial,
        )
        hits = client.query_points(
            collection_name=collection,
            query=vector,
            limit=top_k,
            with_payload=True,
        ).points

    return hits


def search_manuals(
    *,
    query: str,
    machine_serial: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Return ranked manual passages for ``query``, optionally scoped to a machine serial.

    The MCP tool converts each returned dict into a ``ManualHit`` Pydantic model.
    """
    if not query or not query.strip():
        return []

    top_k = max(1, min(int(top_k), 20))
    hits = _query_manuals(query, machine_serial, top_k)

    results: list[dict[str, Any]] = []
    for hit in hits:
        payload = hit.payload or {}
        results.append(
            {
                "title": f"{payload.get('machine_serial', 'AROL')} Manual",
                "excerpt": payload.get("parent_content") or payload.get("child_content", ""),
                "matched_segment": payload.get("child_content"),
                "page_number": payload.get("page_number"),
                "page": payload.get("page_number"),  # Alias for backward compatibility if code calls .get('page')
                "score": float(hit.score) if hit.score is not None else None,
                "source": payload.get("source") or payload.get("doc_id"),
                "doc_type": payload.get("doc_type"),
            },
        )
    log.info(
        "search_manuals q=%r serial=%r hits=%d",
        query,
        machine_serial,
        len(results),
    )
    return results


def search_error_codes(
    *,
    query: str,
    machine_serial: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Return manual passages relevant to an alarm/error-code query, scoped to
    the machine that raised it.

    Same manuals collection and filter as search_manuals() -- see this
    module's docstring for why there's no separate error-code collection.
    The MCP tool converts each dict into an ``ErrorCodeHit``; code/severity/
    recommended_actions are left unset since a manual passage doesn't carry
    that structured metadata, only the descriptive remedy text (``summary``).
    """
    if not query or not query.strip():
        return []

    top_k = max(1, min(int(top_k), 20))
    hits = _query_manuals(query, machine_serial, top_k)

    results: list[dict[str, Any]] = []
    for hit in hits:
        payload = hit.payload or {}
        results.append(
            {
                "code": "",
                "title": f"{payload.get('machine_serial', 'AROL')} Manual",
                "severity": None,
                "summary": payload.get("parent_content") or payload.get("child_content", ""),
                "recommended_actions": [],
                "score": float(hit.score) if hit.score is not None else None,
                "source": payload.get("source") or payload.get("doc_id"),
            },
        )
    log.info(
        "search_error_codes q=%r serial=%r hits=%d",
        query,
        machine_serial,
        len(results),
    )
    return results
