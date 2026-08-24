"""Isolated Django settings for the SDP test suite.

Forces the stub orchestrator, in-memory Qdrant, and no live LLM keys so
``manage.py test`` cannot touch production vector DB or Anthropic.

Usage (from Backend/):

    ../.venv/bin/python manage.py test --settings=config.test_settings
"""

from .settings import *

ORCHESTRATOR_BACKEND = "stub"
ANTHROPIC_API_KEY = ""
QDRANT_URL = ":memory:"
QDRANT_API_KEY = None
MCP_HTTP_INVOKE_ENABLED = True

# The local `arol` Postgres role cannot CREATE DATABASE, so the suite uses a
# file-backed SQLite test DB (needed so LangGraph worker threads share state).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_sdp.sqlite3",
        "OPTIONS": {"timeout": 30},
        "TEST": {
            "NAME": BASE_DIR / "test_sdp_worker.sqlite3",
        },
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Docker/prod settings may add WhiteNoise; tests do not require that extra.
MIDDLEWARE = [item for item in MIDDLEWARE if "whitenoise" not in item]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
