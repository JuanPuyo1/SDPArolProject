# syntax=docker/dockerfile:1
#
# Multi-target image for the Arol SDP stack:
#   docker build --target backend ...
#   docker build --target frontend ...
#
# Size notes:
# - python:3.13-slim + a copied venv (no gcc in the final backend image)
# - node build discarded; frontend runtime is nginx:alpine + dist/
# - FastEmbed ONNX models are downloaded at first RAG call, not baked in
# - Data/ markdown manuals are not copied (mount them if you need ingest)

############################
# Backend dependency layer
############################
FROM python:3.13-slim-bookworm AS backend-deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY Backend/requirements.txt /tmp/requirements.txt

# Cache pip downloads across builds; the cache never lands in the final image.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -U pip \
    && pip install -r /tmp/requirements.txt


############################
# Backend runtime
############################
FROM python:3.13-slim-bookworm AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings \
    FASTEMBED_CACHE_PATH=/home/appuser/.cache/fastembed \
    HF_HOME=/home/appuser/.cache/huggingface

# libgomp1: required by ONNX Runtime (fastembed). No compilers in this stage.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --uid 1000 appuser

COPY --from=backend-deps /opt/venv /opt/venv

WORKDIR /app
COPY --chown=appuser:appuser Backend/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /home/appuser/.cache/fastembed \
    && chown -R appuser:appuser /home/appuser/.cache

COPY --chown=appuser:appuser Backend/ /app/

USER appuser
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]


############################
# Frontend build
############################
FROM node:22-alpine AS frontend-build

WORKDIR /src

COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


############################
# Frontend runtime (nginx)
############################
FROM nginx:1.27-alpine AS frontend

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /src/dist /usr/share/nginx/html

EXPOSE 80
