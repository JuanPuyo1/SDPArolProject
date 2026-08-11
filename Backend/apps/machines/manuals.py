"""Resolve use & maintenance manual PDF paths for installed machines."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings


def _static_dir() -> Path:
    return Path(settings.BASE_DIR) / 'static'


def manual_filename_for_serial(serial_number: str) -> str:
    """Expected manual filename for a machine serial (e.g. 17478_manual_EN.pdf)."""
    return f'{serial_number.strip()}_manual_EN.pdf'


def resolve_manual_url(serial_number: str) -> str | None:
    """
    Return a browser-relative URL for the machine manual PDF if it exists
    in Backend/static/, otherwise None.
    """
    filename = manual_filename_for_serial(serial_number)
    if (_static_dir() / filename).is_file():
        base = settings.STATIC_URL.strip('/')
        return f'/{base}/{filename}'
    return None
