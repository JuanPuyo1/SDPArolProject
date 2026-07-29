"""
Ingestion pipeline for the manuals collection.

Mirrors the notebook's parent/child hierarchical strategy:

* ``RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)`` for parents
* ``RecursiveCharacterTextSplitter(chunk_size=250,  chunk_overlap=40)``  for children

Each child chunk gets its own vector + payload. The payload carries the full
parent text so the LLM sees surrounding context when the child is retrieved.

Usage from a management command or a one-off script::

    from apps.mcp_server.rag_engine.ingest import ingest_text
    ingest_text(
        text=open('manual.txt').read(),
        metadata={
            'machine_model': 'AROL_EURO_VP',
            'chapter': 'Chapter 5',
            'section': 'Section 5.2',
            'doc_type': 'maintenance_guide',
        },
    )

For PDF inputs, see ``apps/mcp_server/management/commands/ingest_manual.py``.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import models

from .client import get_client
from .collections import ensure_manuals_collection
from .embeddings import embed_batch

log = logging.getLogger(__name__)

_PARENT_CHUNK_SIZE = 1200
_PARENT_CHUNK_OVERLAP = 150
_CHILD_CHUNK_SIZE = 250
_CHILD_CHUNK_OVERLAP = 40


@dataclass(frozen=True)
class IngestMetadata:
    """Per-document metadata threaded through parent/child ingestion."""

    machine_model: str
    chapter: str
    section: str
    doc_type: str = 'user_manual'
    source: str | None = None
    doc_id: str | None = None

    def as_payload(self) -> dict:
        return {
            'machine_model': self.machine_model,
            'chapter': self.chapter,
            'section': self.section,
            'doc_type': self.doc_type,
            'source': self.source,
            'doc_id': self.doc_id,
        }


def _splitters() -> tuple[RecursiveCharacterTextSplitter, RecursiveCharacterTextSplitter]:
    parent = RecursiveCharacterTextSplitter(
        chunk_size=_PARENT_CHUNK_SIZE,
        chunk_overlap=_PARENT_CHUNK_OVERLAP,
    )
    child = RecursiveCharacterTextSplitter(
        chunk_size=_CHILD_CHUNK_SIZE,
        chunk_overlap=_CHILD_CHUNK_OVERLAP,
    )
    return parent, child


def _build_points(
    *,
    doc_text: str,
    meta: IngestMetadata,
    parent_splitter: RecursiveCharacterTextSplitter,
    child_splitter: RecursiveCharacterTextSplitter,
) -> list[models.PointStruct]:
    parent_chunks = parent_splitter.split_text(doc_text)
    all_child_texts: list[str] = []
    all_payloads: list[dict] = []

    base_payload = meta.as_payload()
    for p_idx, parent_text in enumerate(parent_chunks):
        parent_id = f"{meta.machine_model}_p{p_idx}"
        child_chunks = child_splitter.split_text(parent_text)
        for child_text in child_chunks:
            payload = {
                **base_payload,
                'child_content': child_text,
                'parent_id': parent_id,
                'parent_content': parent_text,
            }
            all_child_texts.append(child_text)
            all_payloads.append(payload)

    if not all_child_texts:
        return []

    vectors = embed_batch(all_child_texts)
    return [
        models.PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload=payload,
        )
        for vector, payload in zip(vectors, all_payloads)
    ]


def ingest_text(
    *,
    doc_text: str,
    metadata: dict | IngestMetadata,
) -> int:
    """Ingest a single plain-text document. Returns the number of child points upserted."""
    if not doc_text or not doc_text.strip():
        return 0

    meta = metadata if isinstance(metadata, IngestMetadata) else IngestMetadata(**metadata)
    parent_splitter, child_splitter = _splitters()
    points = _build_points(
        doc_text=doc_text,
        meta=meta,
        parent_splitter=parent_splitter,
        child_splitter=child_splitter,
    )
    if not points:
        return 0

    client = get_client()
    collection = ensure_manuals_collection(client)
    client.upsert(collection_name=collection, points=points)

    log.info(
        'Ingested %d child vectors for model %s (%s / %s)',
        len(points),
        meta.machine_model,
        meta.chapter,
        meta.section,
    )
    return len(points)


def ingest_many(documents: Iterable[tuple[str, dict | IngestMetadata]]) -> int:
    """Ingest multiple documents. Returns total child points upserted."""
    total = 0
    for doc_text, metadata in documents:
        total += ingest_text(doc_text=doc_text, metadata=metadata)
    return total


def ingest_pdf(*, pdf_path: str | Path, metadata: dict | IngestMetadata) -> int:
    """Extract text from a PDF and ingest it. ``pypdf`` is used per requirements."""
    from pypdf import PdfReader

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    reader = PdfReader(str(pdf_path))
    pages_text = [(p.extract_text() or '') for p in reader.pages]
    doc_text = '\n\n'.join(t for t in pages_text if t.strip())
    if not doc_text.strip():
        log.warning('PDF %s produced no extractable text.', pdf_path)
        return 0

    meta = metadata if isinstance(metadata, IngestMetadata) else IngestMetadata(**metadata)
    full_meta = IngestMetadata(
        machine_model=meta.machine_model,
        chapter=meta.chapter,
        section=meta.section,
        doc_type=meta.doc_type,
        source=meta.source or str(pdf_path),
        doc_id=meta.doc_id or pdf_path.stem,
    )
    return ingest_text(doc_text=doc_text, metadata=full_meta)
