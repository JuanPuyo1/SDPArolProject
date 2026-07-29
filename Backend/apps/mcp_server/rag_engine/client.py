"""
Qdrant client singleton.

A single ``QdrantClient`` is created per process. Constructing one per request
re-pays TCP/gRPC setup latency and can exhaust connection pools under load.

When ``QDRANT_URL`` is unset (or ``":memory:"``), falls back to an in-memory
client. This matches the notebook's exploratory workflow and keeps unit tests
deterministic without spinning up a Qdrant container.
"""

from __future__ import annotations

from threading import Lock
from typing import Optional

from django.conf import settings
from qdrant_client import QdrantClient

_client: Optional[QdrantClient] = None
_lock = Lock()


def _is_memory_url(url: str) -> bool:
    return url in ('', ':memory:', 'memory')


def get_client() -> QdrantClient:
    """Return the process-wide Qdrant client, creating it on first call."""
    global _client
    if _client is not None:
        return _client

    with _lock:
        if _client is not None:
            return _client

        url = getattr(settings, 'QDRANT_URL', ':memory:') or ':memory:'
        api_key = getattr(settings, 'QDRANT_API_KEY', None)

        if _is_memory_url(url):
            # In-memory mode is convenient for tests, CI, and local exploration.
            _client = QdrantClient(location=':memory:')
        else:
            _client = QdrantClient(url=url, api_key=api_key)

        return _client


def reset_client() -> None:
    """Drop the cached client. Useful for tests that need a fresh in-memory DB."""
    global _client
    with _lock:
        _client = None
