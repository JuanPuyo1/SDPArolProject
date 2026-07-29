"""
FastEmbed-backed embedding model singleton.

We use ``BAAI/bge-small-en-v1.5`` (384-dim) because it:

* runs locally via ONNX — no external API key, no PDF chunks leaving the host,
* matches the model the team already validated in ``vectorDB_AROL.ipynb``,
* is small enough to load once per process and embed queries in <50 ms.
"""

from __future__ import annotations

from threading import Lock
from typing import Iterable

from django.conf import settings
from fastembed import TextEmbedding

_model: TextEmbedding | None = None
_lock = Lock()


def get_model() -> TextEmbedding:
    """Return the process-wide FastEmbed model, instantiating on first call."""
    global _model
    if _model is not None:
        return _model

    with _lock:
        if _model is not None:
            return _model
        model_name = getattr(settings, 'EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5')
        _model = TextEmbedding(model_name=model_name)
        return _model


def embed_query(text: str) -> list[float]:
    """Embed a single query string and return a Python list[float]."""
    return list(get_model().embed([text]))[0].tolist()


def embed_batch(texts: Iterable[str]) -> list[list[float]]:
    """Embed an iterable of texts (used during ingestion)."""
    return [v.tolist() for v in get_model().embed(list(texts))]
