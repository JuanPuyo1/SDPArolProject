#!/bin/sh
set -eu

python - <<'PY'
import os
import sys
import time

import psycopg

host = os.environ.get("POSTGRES_HOST", "db")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
user = os.environ.get("POSTGRES_USER", "arol")
password = os.environ.get("POSTGRES_PASSWORD", "arol")
dbname = os.environ.get("POSTGRES_DB", "arol")

for attempt in range(1, 61):
    try:
        with psycopg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
            connect_timeout=3,
        ) as conn:
            conn.execute("SELECT 1")
        print("PostgreSQL is ready.", flush=True)
        sys.exit(0)
    except Exception as exc:
        print(f"Waiting for PostgreSQL ({attempt}/60): {exc}", flush=True)
        time.sleep(1)

print("PostgreSQL did not become ready in time.", file=sys.stderr)
sys.exit(1)
PY

python manage.py migrate --noinput
python manage.py collectstatic --noinput --ignore "*.pdf"

if [ "${RUN_DB_INIT:-1}" = "1" ]; then
    if python - <<'PY'
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.core.models import Company

sys.exit(0 if Company.objects.exists() else 1)
PY
    then
        echo "Fleet dataset already present; skipping init."
    else
        echo "Loading fleet dataset from Excel..."
        python initiliaze_database.py
    fi
fi

exec uvicorn config.asgi:application \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-1}"
