"""
rag_engine — vector retrieval layer behind the Manuals / Troubleshooting MCP tools.

Architectural rule: agents call MCP tools, MCP tools call into this engine, and
only this engine talks to Qdrant. Keeping the Qdrant dependency on this side of
the boundary keeps tenant scoping, payload filtering, and the embedding model in
one place.

The design mirrors ``vectorDB_AROL.ipynb``:

* FastEmbed ``BAAI/bge-small-en-v1.5`` (384-dim cosine).
* Parent/child hierarchical chunks via ``langchain-text-splitters``
  (parents 1200 / overlap 150, children 250 / overlap 40).
* Qdrant payload index on ``machine_serial`` for tenant + serial filtering.

Public surface used by MCP tools:

* ``rag_engine.search.search_manuals(query, machine_serial, top_k)``
* ``rag_engine.search.search_error_codes(query, machine_serial, top_k)``
"""

from . import client, collections, embeddings, search

__all__ = ['client', 'collections', 'embeddings', 'search']
