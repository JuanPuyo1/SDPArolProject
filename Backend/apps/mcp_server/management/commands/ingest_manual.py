"""
ingest_manual — extract text from a PDF and push it into the manuals Qdrant collection.

Usage::

    python manage.py ingest_manual \
        --pdf windows_sdp/manuals/AROL-EURO-VP.pdf \
        --model AROL_EURO_VP \
        --chapter "Chapter 5" \
        --section "Section 5.2" \
        --doc-type maintenance_guide

The command reuses the parent/child splitting strategy from
``apps.mcp_server.rag_engine.ingest`` so ingested documents are immediately
queryable via the ``search_manual`` MCP tool.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.mcp_server.rag_engine.ingest import IngestMetadata, ingest_pdf


class Command(BaseCommand):
    help = 'Extract text from a PDF and ingest it into the manuals Qdrant collection.'

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument('--pdf', required=True, help='Path to the source PDF.')
        parser.add_argument('--model', required=True, help='Machine model identifier (e.g. AROL_EURO_VP).')
        parser.add_argument('--chapter', required=True, help='Chapter heading stored as payload.')
        parser.add_argument('--section', required=True, help='Section heading stored as payload.')
        parser.add_argument(
            '--doc-type',
            default='user_manual',
            choices=['user_manual', 'maintenance_guide', 'service_manual', 'safety_datasheet'],
            help='Document type stored as payload.',
        )
        parser.add_argument(
            '--doc-id',
            default=None,
            help='Stable identifier for this document (defaults to the PDF stem).',
        )

    def handle(self, *args, **opts):
        pdf_path = Path(opts['pdf'])
        if not pdf_path.exists():
            raise CommandError(f'PDF not found: {pdf_path}')

        meta = IngestMetadata(
            machine_model=opts['model'],
            chapter=opts['chapter'],
            section=opts['section'],
            doc_type=opts['doc_type'],
            source=str(pdf_path),
            doc_id=opts['doc_id'],
        )
        n = ingest_pdf(pdf_path=pdf_path, metadata=meta)
        self.stdout.write(
            self.style.SUCCESS(
                f'Ingested {n} child vectors from {pdf_path.name} into the manuals collection.',
            ),
        )
