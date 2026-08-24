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
    """Query the manuals collection, scoped to this machine (or AROL_GENERAL /
    general_catalogue docs) when a machine_serial is given.

    Deliberately does NOT retry without the filter on zero hits: that used to
    fall back to an unrestricted search that could surface another specific
    machine's own manual content mislabeled as this machine's answer. The
    should-filter already covers the legitimate fallback universe (this
    machine, plus shared/general docs) -- if nothing matches there, the
    honest answer is no hits, not a different machine's manual.
    """
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
        log.info("no hits for serial=%r within machine/general scope", machine_serial)

    return hits


def _is_machine_specific(payload: dict[str, Any], machine_serial: str | None) -> bool:
    """True when a hit is this exact machine's own manual content, as
    opposed to a shared/general-catalogue passage returned because nothing
    specific to this machine matched."""
    if not machine_serial:
        return True
    return payload.get("machine_serial") == machine_serial


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
                "machine_specific": _is_machine_specific(payload, machine_serial),
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
                "machine_specific": _is_machine_specific(payload, machine_serial),
            },
        )
    log.info(
        "search_error_codes q=%r serial=%r hits=%d",
        query,
        machine_serial,
        len(results),
    )
    return results
