# syntax=docker/dockerfile:1
#
# Ask Anything — image single-container, siap deploy di Coolify (build type: Dockerfile).
#
# Isi container (satu proses supervisor = docker/entrypoint.sh):
#   1. FastAPI backend  → uvicorn, listen 127.0.0.1:8000 (internal saja)
#   2. Next.js 16 prod  → listen 0.0.0.0:$PORT (default 3000, di-proxy Traefik/Coolify)
#
# Next me-rewrite /api, /slides, /docs-images ke backend, jadi browser hanya
# bicara ke satu origin — sama persis seperti `python run.py` di lokal.
#
# Build & run lokal:
#   docker build -t ask-anything .
#   docker run --rm -p 3000:3000 -v ask-anything-data:/app/data ask-anything
#
# Deploy Coolify: lihat docs/DEPLOY-COOLIFY.md
#
ARG NODE_IMAGE=node:22-bookworm-slim

# ---------------------------------------------------------------------------
# Stage 1 — frontend: install deps (npm ci) + `next build`
# ---------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS frontend-builder
WORKDIR /build
ENV NEXT_TELEMETRY_DISABLED=1 \
    CI=1

# package-lock dulu agar layer deps ter-cache selama source belum berubah
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./

# Rewrite Next di-bake ke .next/routes-manifest.json saat BUILD, jadi target
# backend harus diketahui di sini. Backend selalu satu container → loopback.
ARG BACKEND_PORT=8000
ENV BACKEND_URL=http://127.0.0.1:${BACKEND_PORT}

# build → buang .next/cache (tidak dipakai `next start`) → buang devDependencies
# (tailwind/typescript/postcss) supaya image runtime jauh lebih kecil.
RUN npm run build && rm -rf .next/cache && npm prune --omit=dev

# ---------------------------------------------------------------------------
# Stage 2 — backend: venv Python + requirements (compiler cuma ada di sini)
# ---------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS backend-builder
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-dev python3-venv build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
# venv di path tetap supaya bisa di-copy apa adanya ke stage runtime
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

# ---------------------------------------------------------------------------
# Stage 3 — runtime
# ---------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS runtime
# ASK_DB_PATH ditaruh di luar source tree → tinggal mount volume ke /app/data
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    ASK_DB_PATH=/app/data/ask_anything.db

# python3 = interpreter untuk venv hasil stage 2; tini = PID 1 (signal handling);
# curl = dipakai HEALTHCHECK & probe LLM di entrypoint
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 tini curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --chown per-COPY (bukan `chown -R`) supaya tidak menduplikasi layer node_modules
COPY --from=backend-builder --chown=node:node /opt/venv /app/.venv
COPY --from=frontend-builder --chown=node:node /build /app/frontend
COPY --chown=node:node backend/ /app/backend/
COPY --chown=node:node docs/ /app/docs/
COPY --chown=node:node docker/entrypoint.sh /app/docker/entrypoint.sh

RUN chmod +x /app/docker/entrypoint.sh \
    && mkdir -p /app/data \
    && chown node:node /app/data

# PORT & HOST sengaja TIDAK di-set di sini: Coolify meng-inject
# PORT = exposed port pertama dan HOST = 0.0.0.0. Fallback ada di entrypoint.
EXPOSE 3000

USER node

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-3000}/api/health" || exit 1

ENTRYPOINT ["tini", "--", "/app/docker/entrypoint.sh"]
