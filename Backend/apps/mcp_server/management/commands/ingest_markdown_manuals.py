"""
ingest_markdown_manuals — Ingest extracted Markdown manual documents into Qdrant DB.

Parses all .md files in apps/mcp_server/data/ with structural headers (#, ##, ###),
page comment tags (<!-- Page N -->), and threads complete metadata through child point payloads.

Usage::

    python manage.py ingest_markdown_manuals
"""

from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.mcp_server.rag_engine.collections import clear_manuals_collection
from apps.mcp_server.rag_engine.ingest import IngestMetadata, ingest_markdown_text

log = logging.getLogger(__name__)

# Default mapping for known extracted markdown manual files
DEFAULT_MARKDOWN_MAP = {
    'A3279usomanutenzione-R1-ENG.md': {
        'machine_model': 'CLOSYS EAGLE VP',
        'doc_id': 'A3279-manual',
        'doc_type': 'use_and_maintenance',
    },
    'Original manual 2019 Arol Euro VIP.md': {
        'machine_model': 'AROL_EURO_VIP',
        'doc_id': 'AROL-EURO-VIP-2019',
        'doc_type': 'use_and_maintenance',
    },
    'AROL_GENERAL_CATALOGUE_11.0_EN_20230215.md': {
        'machine_model': 'AROL_GENERAL',
        'doc_id': 'AROL-CATALOGUE-2023',
        'doc_type': 'general_catalogue',
    },
}


class Command(BaseCommand):
    help = 'Ingest extracted Markdown manual documents from apps/mcp_server/data into Qdrant DB.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dir',
            default=None,
            help='Directory containing extracted Markdown manuals (defaults to apps/mcp_server/data).',
        )
        parser.add_argument(
            '--no-clear',
            action='store_false',
            dest='clear',
            default=True,
            help='Do not clear the existing collection before ingestion.',
        )

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR) if hasattr(settings, 'BASE_DIR') else Path.cwd()
        md_dir = Path(options['dir']) if options['dir'] else base_dir / 'apps' / 'mcp_server' / 'data'

        if not md_dir.exists():
            raise CommandError(f'Directory does not exist: {md_dir}')

        md_files = sorted(md_dir.glob('*.md'))
        if not md_files:
            self.stdout.write(self.style.WARNING(f'No .md files found in {md_dir}'))
            return

        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing existing manuals collection in Qdrant DB...'))
            clear_manuals_collection()

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f'Starting Markdown ingestion into Qdrant from {md_dir} ({len(md_files)} files)...'
            )
        )

        total_vectors = 0
        for md_path in md_files:
            file_name = md_path.name
            mapping = DEFAULT_MARKDOWN_MAP.get(
                file_name,
                {
                    'machine_model': md_path.stem.upper().replace(' ', '_'),
                    'doc_id': md_path.stem,
                    'doc_type': 'user_manual',
                },
            )

            text = md_path.read_text(encoding='utf-8')
            meta = IngestMetadata(
                machine_model=mapping['machine_model'],
                doc_id=mapping['doc_id'],
                doc_type=mapping['doc_type'],
                source=str(md_path.relative_to(base_dir) if md_path.is_relative_to(base_dir) else md_path),
            )

            self.stdout.write(f'  -> Ingesting {file_name} for model [{meta.machine_model}]...')
            vectors = ingest_markdown_text(markdown_text=text, metadata=meta)
            total_vectors += vectors
            self.stdout.write(
                self.style.SUCCESS(f'     Ingested {vectors} vectors from {file_name}')
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Markdown ingestion complete! Total child vectors upserted: {total_vectors}'
            )
        )
