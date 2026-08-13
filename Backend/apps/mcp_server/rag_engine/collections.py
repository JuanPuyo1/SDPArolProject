"""
Collection names, payload schema, and idempotent ``ensure_collection`` helpers.

The manuals collection backs the MCP tools:

* ``arol_manuals_fastembed`` — Manuals & Troubleshooting Agents. Parent/child chunking,
  payload carries ``machine_serial``, ``doc_type``, ``page_number``, plus the
  parent/child text fields the LLM consumes.

The ``machine_serial`` payload field is the primary tenant filter; indexing it
prevents full-collection scans on every query.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from qdrant_client import QdrantClient, models

from .client import get_client


# -- Collection identifiers ---------------------------------------------------

MANUALS_COLLECTION: str = 'arol_manuals_fastembed'

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

    machine_serial: str
    doc_type: str
    child_content: str
    parent_id: str
    parent_content: str
    page_number: int | None = None
    source: str | None = None
    doc_id: str | None = None


# -- Helpers ------------------------------------------------------------------

def manuals_collection_name() -> str:
    """Allow override via settings (tests use ephemeral names)."""
    return getattr(settings, 'QDRANT_COLLECTION_MANUALS', MANUALS_COLLECTION)


def clear_manuals_collection(client: QdrantClient | None = None) -> str:
    """Re-create/clear the manuals collection to remove all points."""
    name = manuals_collection_name()
    client = client or get_client()
    if client.collection_exists(collection_name=name):
        client.delete_collection(collection_name=name)
    return ensure_manuals_collection(client)


def ensure_manuals_collection(client: QdrantClient | None = None) -> str:
    """Create the manuals collection (if missing) and index ``machine_serial`` and ``doc_type``."""
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

    # Payload indexes — keep these idempotent so re-runs are safe.
    client.create_payload_index(
        collection_name=name,
        field_name='machine_serial',
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=name,
        field_name='doc_type',
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    return name

