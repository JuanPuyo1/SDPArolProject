"""
Ingestion pipeline for the manuals collection in Qdrant DB.

Extracted Markdown documents are parsed using Markdown section headers and embedded
page markers (<!-- Page N -->) combined with hierarchical parent/child text splitting:

* Parent chunks: RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
* Child chunks:  RecursiveCharacterTextSplitter(chunk_size=250,  chunk_overlap=40)

Each child chunk is embedded with FastEmbed and stored as a Qdrant PointStruct.
The payload preserves standard metadata: machine_serial, doc_type, source, doc_id,
page_number, parent_id, parent_content, and child_content.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Iterable

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from qdrant_client import models

from .client import get_client
from .collections import ensure_manuals_collection
from .embeddings import embed_batch

log = logging.getLogger(__name__)

_PARENT_CHUNK_SIZE = 1200
_PARENT_CHUNK_OVERLAP = 150
_CHILD_CHUNK_SIZE = 250
_CHILD_CHUNK_OVERLAP = 40

_PAGE_PATTERN = re.compile(r"<!--\s*Page\s+(\d+)\s*-->", re.IGNORECASE)


@dataclass(frozen=True)
class IngestMetadata:
    """Per-document metadata threaded through parent/child ingestion."""

    machine_serial: str
    doc_type: str = "user_manual"
    source: str | None = None
    doc_id: str | None = None
    page_number: int | None = None

    def as_payload(self) -> dict:
        return {
            "machine_serial": self.machine_serial,
            "doc_type": self.doc_type,
            "source": self.source,
            "doc_id": self.doc_id,
            "page_number": self.page_number,
        }


def _splitters() -> (
    tuple[RecursiveCharacterTextSplitter, RecursiveCharacterTextSplitter]
):
    parent = RecursiveCharacterTextSplitter(
        chunk_size=_PARENT_CHUNK_SIZE,
        chunk_overlap=_PARENT_CHUNK_OVERLAP,
    )
    child = RecursiveCharacterTextSplitter(
        chunk_size=_CHILD_CHUNK_SIZE,
        chunk_overlap=_CHILD_CHUNK_OVERLAP,
    )
    return parent, child


def ingest_markdown_text(
    *,
    markdown_text: str,
    metadata: dict | IngestMetadata,
) -> int:
    """Ingest a Markdown document into Qdrant with page numbers and parent/child payloads."""
    if not markdown_text or not markdown_text.strip():
        return 0

    base_meta = (
        metadata if isinstance(metadata, IngestMetadata) else IngestMetadata(**metadata)
    )

    headers_to_split_on = [
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False,
    )
    section_docs = markdown_splitter.split_text(markdown_text)

    parent_splitter, child_splitter = _splitters()
    all_child_texts: list[str] = []
    all_payloads: list[dict] = []

    active_page: int | None = base_meta.page_number

    for sec_idx, sec_doc in enumerate(section_docs):
        sec_text = sec_doc.page_content

        page_matches = _PAGE_PATTERN.findall(sec_text)
        if page_matches:
            active_page = int(page_matches[-1])

        parent_chunks = parent_splitter.split_text(sec_text)
        for p_idx, parent_text in enumerate(parent_chunks):
            p_pages = _PAGE_PATTERN.findall(parent_text)
            if p_pages:
                active_page = int(p_pages[-1])

            parent_id = f"{base_meta.machine_serial}_s{sec_idx}_p{p_idx}"
            child_chunks = child_splitter.split_text(parent_text)

            for child_text in child_chunks:
                c_pages = _PAGE_PATTERN.findall(child_text)
                chunk_page = int(c_pages[-1]) if c_pages else active_page

                payload = {
                    "machine_serial": base_meta.machine_serial,
                    "doc_type": base_meta.doc_type,
                    "source": base_meta.source,
                    "doc_id": base_meta.doc_id,
                    "page_number": chunk_page,
                    "child_content": child_text,
                    "parent_id": parent_id,
                    "parent_content": parent_text,
                }
                all_child_texts.append(child_text)
                all_payloads.append(payload)

    if not all_child_texts:
        return 0

    vectors = embed_batch(all_child_texts)
    points = [
        models.PointStruct(
            id=str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{payload['machine_serial']}:{payload['parent_id']}:{payload['child_content']}",
                )
            ),
            vector=vector,
            payload=payload,
        )
        for vector, payload in zip(vectors, all_payloads)
    ]

    client = get_client()
    collection = ensure_manuals_collection(client)
    batch_size = 200
    for i in range(0, len(points), batch_size):
        client.upsert(collection_name=collection, points=points[i : i + batch_size])

    log.info(
        "Ingested %d Markdown child vectors for serial %s from %s",
        len(points),
        base_meta.machine_serial,
        base_meta.source or base_meta.doc_id,
    )
    return len(points)


def ingest_text(
    *,
    doc_text: str,
    metadata: dict | IngestMetadata,
) -> int:
    """Ingest a single document string. Dispatches to Markdown parser if headers or page markers exist."""
    if "<!-- Page" in doc_text or "#" in doc_text:
        return ingest_markdown_text(markdown_text=doc_text, metadata=metadata)

    if not doc_text or not doc_text.strip():
        return 0

    meta = (
        metadata if isinstance(metadata, IngestMetadata) else IngestMetadata(**metadata)
    )
    parent_splitter, child_splitter = _splitters()
    parent_chunks = parent_splitter.split_text(doc_text)
    all_child_texts: list[str] = []
    all_payloads: list[dict] = []
    base_payload = meta.as_payload()

    for p_idx, parent_text in enumerate(parent_chunks):
        parent_id = f"{meta.machine_serial}_p{p_idx}"
        child_chunks = child_splitter.split_text(parent_text)
        for child_text in child_chunks:
            payload = {
                **base_payload,
                "child_content": child_text,
                "parent_id": parent_id,
                "parent_content": parent_text,
            }
            all_child_texts.append(child_text)
            all_payloads.append(payload)

    if not all_child_texts:
        return 0

    vectors = embed_batch(all_child_texts)
    points = [
        models.PointStruct(
            id=str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{payload['machine_serial']}:{payload['parent_id']}:{payload['child_content']}",
                )
            ),
            vector=vector,
            payload=payload,
        )
        for vector, payload in zip(vectors, all_payloads)
    ]

    client = get_client()
    collection = ensure_manuals_collection(client)
    batch_size = 200
    for i in range(0, len(points), batch_size):
        client.upsert(collection_name=collection, points=points[i : i + batch_size])
    return len(points)


def ingest_many(documents: Iterable[tuple[str, dict | IngestMetadata]]) -> int:
    """Ingest multiple documents. Returns total child points upserted."""
    total = 0
    for doc_text, metadata in documents:
        total += ingest_text(doc_text=doc_text, metadata=metadata)
    return total
