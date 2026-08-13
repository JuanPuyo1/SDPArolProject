"""
seed_demo_manuals — load the synthetic AROL demo content from the notebook.

Mirrors the two passages used in ``vectorDB_AROL.ipynb`` so a fresh dev install
already has queryable manuals + error-code-like passages without needing real
PDFs. Idempotent: re-running upserts the same content (UUIDs change, but the
text is identical, so search results stay stable).

Usage::

    python manage.py seed_demo_manuals
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.core.management.base import BaseCommand
from qdrant_client import models

from apps.mcp_server.rag_engine.client import get_client
from apps.mcp_server.rag_engine.collections import ensure_manuals_collection
from apps.mcp_server.rag_engine.embeddings import embed_batch
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Mirror the parent/child splitting strategy used by rag_engine.ingest so the
# demo data lives at the same chunk granularity as the real ingestion pipeline.
_PARENT_CHUNK_SIZE = 1200
_PARENT_CHUNK_OVERLAP = 150
_CHILD_CHUNK_SIZE = 250
_CHILD_CHUNK_OVERLAP = 40


MANUAL_EURO_VIP = """
CHAPTER 4: SAFETY DEVICES AND OPERATING MODES
Section 4.4 - Professional Roles & Operating Modes

Before starting up the machine, read the technical instructions and follow the indications shown.
The machinery is configured to allow two primary industrial personnel interactions:

1. Operator: Personnel in charge of running normal production cycles, cleaning, and basic interface validation.
2. Maintenance Man: Authorized technical staff certified to handle electrical/mechanical configurations and deep troubleshooting loops while safety overrides are active.

If vibration exceeds 3.0 mm/s during capping head engagement, trigger capper spindle switch immediately and check capping head alignment.
"""

MANUAL_EURO_VP = """
CHAPTER 5: MAINTENANCE & TORQUE ADJUSTMENT
Section 5.2 - Capping Head Pressure & Torque Settings

To ensure proper sealing of ROPP aluminum caps on bottling lines, capping head pressure must remain within nominal operational boundaries.
Nominal Capping Torque Target: 2.5 Nm to 3.5 Nm.
Top Load Pressure: 200 N to 230 N.

Fault Handling:
If capping torque drops below 2.0 Nm (Fault Code E-04), verify magnetic clutch wear and check spindle head springs for mechanical fatigue. Replace worn grippers using toolkit T-804.
"""


class Command(BaseCommand):
    help = 'Seed the manuals collection with synthetic AROL demo content from the notebook.'

    def handle(self, *args, **opts):
        client = get_client()

        # -- Manuals -----------------------------------------------------------
        manuals = ensure_manuals_collection(client)
        parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=_PARENT_CHUNK_SIZE,
            chunk_overlap=_PARENT_CHUNK_OVERLAP,
        )
        child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=_CHILD_CHUNK_SIZE,
            chunk_overlap=_CHILD_CHUNK_OVERLAP,
        )

        all_child_texts: list[str] = []
        all_payloads: list[dict] = []
        for doc_text, meta in (
            (MANUAL_EURO_VIP, {'machine_serial': 'AROL_EURO_VIP', 'doc_type': 'user_manual'}),
            (MANUAL_EURO_VP,  {'machine_serial': 'AROL_EURO_VP',  'doc_type': 'maintenance_guide'}),
        ):
            for p_idx, parent_text in enumerate(parent_splitter.split_text(doc_text)):
                parent_id = f"{meta['machine_serial']}_p{p_idx}"
                for child_text in child_splitter.split_text(parent_text):
                    all_payloads.append(
                        {
                            **meta,
                            'page_number': None,
                            'child_content': child_text,
                            'parent_id': parent_id,
                            'parent_content': parent_text,
                        },
                    )
                    all_child_texts.append(child_text)

        if all_child_texts:
            vectors = embed_batch(all_child_texts)
            points = [
                models.PointStruct(id=str(uuid.uuid4()), vector=vec, payload=pl)
                for vec, pl in zip(vectors, all_payloads)
            ]
            client.upsert(collection_name=manuals, points=points)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Seeded {len(points)} child vectors across '
                    f'{len({p["parent_id"] for p in all_payloads})} parent blocks '
                    f'into {manuals}.',
                ),
            )

