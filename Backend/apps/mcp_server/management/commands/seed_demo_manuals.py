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
from apps.mcp_server.rag_engine.collections import (
    ensure_error_codes_collection,
    ensure_manuals_collection,
)
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


@dataclass(frozen=True)
class ErrorCodeEntry:
    code: str
    machine_model: str
    title: str
    severity: str
    summary: str
    recommended_actions: list[str]


ERROR_CODES: list[ErrorCodeEntry] = [
    ErrorCodeEntry(
        code='E-04',
        machine_model='AROL_EURO_VP',
        title='Low capping torque',
        severity='high',
        summary=(
            'Capping torque dropped below 2.0 Nm. Magnetic clutch wear or spindle '
            'head spring fatigue are the most likely causes.'
        ),
        recommended_actions=[
            'Verify magnetic clutch wear.',
            'Check spindle head springs for mechanical fatigue.',
            'Replace worn grippers using toolkit T-804.',
            'Recalibrate torque to 2.5–3.5 Nm after the repair.',
        ],
    ),
    ErrorCodeEntry(
        code='E-VIB-01',
        machine_model='AROL_EURO_VIP',
        title='Capper spindle vibration above threshold',
        severity='high',
        summary=(
            'Vibration above 3.0 mm/s detected during capping head engagement. '
            'Risk of cap misalignment and capper damage.'
        ),
        recommended_actions=[
            'Trigger capper spindle switch immediately.',
            'Check capping head alignment.',
            'Re-torque spindle mounting bolts per Section 4.4.',
            'Run a 10-cycle test before resuming production.',
        ],
    ),
]


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
            (MANUAL_EURO_VIP, {'machine_model': 'AROL_EURO_VIP', 'chapter': 'Chapter 4', 'section': 'Section 4.4', 'doc_type': 'user_manual'}),
            (MANUAL_EURO_VP,  {'machine_model': 'AROL_EURO_VP',  'chapter': 'Chapter 5', 'section': 'Section 5.2', 'doc_type': 'maintenance_guide'}),
        ):
            for p_idx, parent_text in enumerate(parent_splitter.split_text(doc_text)):
                parent_id = f"{meta['machine_model']}_p{p_idx}"
                for child_text in child_splitter.split_text(parent_text):
                    all_payloads.append(
                        {
                            **meta,
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

        # -- Error codes -------------------------------------------------------
        codes_coll = ensure_error_codes_collection(client)
        code_texts = [f"{e.code} {e.title} {e.summary}" for e in ERROR_CODES]
        code_vectors = embed_batch(code_texts)
        code_points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={
                    'code': e.code,
                    'machine_model': e.machine_model,
                    'title': e.title,
                    'severity': e.severity,
                    'summary': e.summary,
                    'recommended_actions': e.recommended_actions,
                },
            )
            for vec, e in zip(code_vectors, ERROR_CODES)
        ]
        client.upsert(collection_name=codes_coll, points=code_points)
        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded {len(code_points)} error codes into {codes_coll}.',
            ),
        )
