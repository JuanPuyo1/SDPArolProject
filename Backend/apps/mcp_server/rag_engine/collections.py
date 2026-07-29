"""
Collection names, payload schema, and idempotent ``ensure_collection`` helpers.

Two collections back the MCP tools:

* ``arol_manuals_fastembed`` — Manuals Agent. Parent/child chunking, payload
  carries ``machine_model``, ``chapter``, ``section``, ``doc_type``, plus the
  parent/child text fields the LLM and Doc-Agent consume.
* ``arol_error_codes``      — Troubleshooting Agent. Flat payload carrying the
  error code, severity, summary, and recommended actions.

The ``machine_model`` payload field is the primary tenant filter; indexing it
prevents full-collection scans on every query.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from qdrant_client import QdrantClient, models

from .client import get_client


# -- Collection identifiers ---------------------------------------------------

MANUALS_COLLECTION: str = 'arol_manuals_fastembed'
ERROR_CODES_COLLECTION: str = 'arol_error_codes'

MANUAL_DOC_TYPES = {
    'user_manual',
    'maintenance_guide',
    'service_manual',
    'safety_datasheet',
}


# -- Payload schemas ----------------------------------------------------------

@dataclass(frozen=True)
class ManualPayload:
    """Fields stored alongside each child vector in the manuals collection."""

    machine_model: str
    chapter: str
    section: str
    doc_type: str
    child_content: str
    parent_id: str
    parent_content: str
    page: int | None = None
    source: str | None = None
    doc_id: str | None = None


@dataclass(frozen=True)
class ErrorCodePayload:
    """Flat payload for the error-code troubleshooting collection."""

    code: str
    machine_model: str
    title: str
    severity: str
    summary: str
    recommended_actions: list[str]
    source: str | None = None


# -- Helpers ------------------------------------------------------------------

def manuals_collection_name() -> str:
    """Allow override via settings (tests use ephemeral names)."""
    return getattr(settings, 'QDRANT_COLLECTION_MANUALS', MANUALS_COLLECTION)


def error_codes_collection_name() -> str:
    return getattr(settings, 'QDRANT_COLLECTION_ERROR_CODES', ERROR_CODES_COLLECTION)


def ensure_manuals_collection(client: QdrantClient | None = None) -> str:
    """Create the manuals collection (if missing) and index ``machine_model``."""
    name = manuals_collection_name()
    client = client or get_client()
    dim = int(getattr(settings, 'EMBEDDING_DIM', 384))

    if not client.collection_exists(collection_name=name):
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=dim,
                distance=models.Distance.COSINE,
            ),
        )

    # Payload index — keep this idempotent so re-runs are safe.
    client.create_payload_index(
        collection_name=name,
        field_name='machine_model',
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    return name


def ensure_error_codes_collection(client: QdrantClient | None = None) -> str:
    name = error_codes_collection_name()
    client = client or get_client()
    dim = int(getattr(settings, 'EMBEDDING_DIM', 384))

    if not client.collection_exists(collection_name=name):
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=dim,
                distance=models.Distance.COSINE,
            ),
        )

    client.create_payload_index(
        collection_name=name,
        field_name='machine_model',
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=name,
        field_name='code',
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    return name
