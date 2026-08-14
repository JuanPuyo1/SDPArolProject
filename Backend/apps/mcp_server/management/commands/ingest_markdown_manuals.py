"""
ingest_markdown_manuals — Ingest extracted Markdown manual documents into Qdrant DB.

Parses all .md files in Data/Manuals_md (or Data/Extracted_Markdown) with structural headers (#, ##, ###),
page comment tags (<!-- Page N -->), and threads complete metadata through child point payloads.

Usage::

    python manage.py ingest_markdown_manuals
    python manage.py ingest_markdown_manuals --dir Data/Manuals_md
    python manage.py ingest_markdown_manuals --no-clear
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.mcp_server.rag_engine.client import get_client
from apps.mcp_server.rag_engine.collections import (
    clear_manuals_collection,
    ensure_manuals_collection,
)
from apps.mcp_server.rag_engine.ingest import IngestMetadata, ingest_markdown_text

log = logging.getLogger(__name__)

# Default mapping for known extracted markdown manual files
MODEL_MAPPING_OVERLAY = {
    "A3279usomanutenzione-R1-ENG.md": {
        "machine_serial": "A3279",
        "doc_id": "A3279-manual",
        "doc_type": "use_and_maintenance",
    },
    "Original manual 2019 Arol Euro VIP.md": {
        "machine_serial": "AROL_EURO_VIP",
        "doc_id": "AROL-EURO-VIP-2019",
        "doc_type": "use_and_maintenance",
    },
    "AROL_GENERAL_CATALOGUE_11.0_EN_20230215.md": {
        "machine_serial": "AROL_GENERAL",
        "doc_id": "AROL-CATALOGUE-2023",
        "doc_type": "general_catalogue",
    },
}


def parse_metadata(file_path: Path, base_dir: Path) -> IngestMetadata:
    filename = file_path.name
    rel_path = str(
        file_path.relative_to(base_dir)
        if file_path.is_relative_to(base_dir)
        else file_path
    )

    if filename in MODEL_MAPPING_OVERLAY:
        overlay = MODEL_MAPPING_OVERLAY[filename]
        return IngestMetadata(
            machine_serial=overlay["machine_serial"],
            doc_id=overlay.get("doc_id", file_path.stem),
            doc_type=overlay.get("doc_type", "user_manual"),
            source=rel_path,
        )

    stem = file_path.stem
    if "_manual" in stem:
        serial = stem.split("_manual")[0].strip()
    else:
        serial = stem.upper().replace(" ", "_")

    return IngestMetadata(
        machine_serial=serial,
        doc_id=stem,
        doc_type="user_manual",
        source=rel_path,
    )


class Command(BaseCommand):
    help = "Ingest extracted Markdown manual documents (from Data/Manuals_md) into Qdrant DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default=None,
            help="Directory containing extracted Markdown manuals (defaults to Data/Manuals_md).",
        )
        parser.add_argument(
            "--no-clear",
            action="store_false",
            dest="clear",
            default=True,
            help="Do not clear the existing collection before ingestion.",
        )

    def handle(self, *args, **options):
        base_dir = (
            Path(settings.BASE_DIR).parent
            if hasattr(settings, "BASE_DIR")
            else Path.cwd()
        )

        if options["dir"]:
            md_dir = Path(options["dir"])
        else:
            primary_dir = base_dir / "Data" / "Manuals_md"
            fallback_dir = base_dir / "Data" / "Extracted_Markdown"
            md_dir = primary_dir if primary_dir.exists() else fallback_dir

        if not md_dir.exists():
            raise CommandError(f"Directory does not exist: {md_dir}")

        md_files = sorted(md_dir.glob("*.md"))
        if not md_files:
            self.stdout.write(self.style.WARNING(f"No .md files found in {md_dir}"))
            return

        client = get_client()

        if options["clear"]:
            self.stdout.write(
                self.style.WARNING(
                    "Clearing existing manuals collection in Qdrant DB..."
                )
            )
            clear_manuals_collection(client)
        else:
            ensure_manuals_collection(client)

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Starting Markdown ingestion into Qdrant from {md_dir} ({len(md_files)} files)..."
            )
        )

        total_vectors = 0
        total_start = time.time()
        summary = []

        for md_path in md_files:
            meta = parse_metadata(md_path, base_dir)
            start_time = time.time()

            self.stdout.write(
                f"  -> Ingesting {md_path.name} for serial [{meta.machine_serial}]..."
            )
            text = md_path.read_text(encoding="utf-8")

            num_vectors = ingest_markdown_text(markdown_text=text, metadata=meta)
            elapsed = time.time() - start_time
            total_vectors += num_vectors

            self.stdout.write(
                self.style.SUCCESS(
                    f"     Ingested {num_vectors} vectors from {md_path.name} ({elapsed:.2f}s)"
                )
            )
            summary.append((md_path.name, meta.machine_serial, num_vectors, elapsed))

        total_elapsed = time.time() - total_start
        self.stdout.write("=" * 65)
        self.stdout.write("             FULL EXTRACTION & INGESTION SUMMARY REPORT")
        self.stdout.write("=" * 65)
        self.stdout.write(
            f"Successfully ingested : {len(summary)} / {len(md_files)} manuals"
        )
        self.stdout.write(f"Total vectors upserted : {total_vectors}")
        self.stdout.write(f"Total time elapsed    : {total_elapsed:.2f} seconds")
        self.stdout.write("-" * 65)
        for name, serial, count, elapsed in summary:
            self.stdout.write(
                f" • {name:28s} | Serial: {serial:12s} | Vectors: {count:4d} | {elapsed:.2f}s"
            )
        self.stdout.write("=" * 65)
