#!/usr/bin/env bash
# Ask Anything — entrypoint container (Coolify / docker run / docker compose).
#
# Menjalankan dua proses dalam satu container dan meneruskan sinyal TERM/INT
# ke keduanya, supaya Coolify bisa stop/restart app dengan bersih:
#
#   uvicorn (FastAPI)   → ${BACKEND_HOST}:${BACKEND_PORT}   default 127.0.0.1:8000 (internal)
#   next start (UI)     → ${HOST}:${PORT}                   default 0.0.0.0:3000   (publik)
#
# Semua variabel bisa dioverride lewat Environment Variables di Coolify.
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
HOST="${HOST:-0.0.0.0}"                     # Coolify inject HOST=0.0.0.0
PORT="${PORT:-3000}"                        # Coolify inject PORT = exposed port
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-${APP_DIR}/.venv/bin/python}"

# Konfigurasi aplikasi (dibaca pydantic-settings backend, prefix ASK_)
export ASK_DB_PATH="${ASK_DB_PATH:-${APP_DIR}/data/ask_anything.db}"
# Target rewrite Next. Catatan: nilai ini ikut ter-bake saat `next build`
# (lihat Dockerfile ARG BACKEND_PORT) — default sudah cocok untuk in-container.
export BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:${BACKEND_PORT}}"

log() { printf '[ask-anything] %s\n' "$*"; }

# ---- 0. sanity check: folder SQLite harus writable -----------------------
DB_DIR="$(dirname "${ASK_DB_PATH}")"
mkdir -p "${DB_DIR}" 2>/dev/null || true
if [ ! -w "${DB_DIR}" ]; then
    log "ERROR: ${DB_DIR} tidak bisa ditulis (ASK_DB_PATH=${ASK_DB_PATH})."
    log "       Di Coolify: mount persistent volume ke /app/data,"
    log "       atau set ASK_DB_PATH ke direktori yang writable."
    exit 1
fi

if [ ! -x "${PYTHON_BIN}" ]; then
    log "ERROR: python venv tidak ditemukan di ${PYTHON_BIN}."
    exit 1
fi

log "backend  : http://${BACKEND_HOST}:${BACKEND_PORT} (internal, tidak di-expose)"
log "frontend : http://${HOST}:${PORT} (publik — di-proxy Coolify/Traefik)"
log "database : ${ASK_DB_PATH}"
log "provider : ${ASK_PROVIDER:-huggingface (default app)}"

# ---- 1. probe LLM server (sekadar peringatan, tidak memblokir start) ------
# Default app = provider "huggingface" yang menunjuk llama-server lokal :8081.
# Di VPS biasanya tidak ada, jadi beri petunjuk konfigurasi yang benar.
if [ "${ASK_PROVIDER:-huggingface}" = "huggingface" ]; then
    HF_URL="${ASK_HF_BASE_URL:-http://127.0.0.1:8081/v1}"
    if ! curl -fsS -m 2 -o /dev/null "${HF_URL}/models" 2>/dev/null; then
        log "WARN: LLM server '${HF_URL}' tidak terjangkau."
        log "      Set env di Coolify: ASK_PROVIDER=openai + ASK_OPENAI_API_KEY=sk-..."
        log "      (atau ASK_PROVIDER=mock untuk demo offline, atau arahkan"
        log "       ASK_HF_BASE_URL ke server OpenAI-compatible yang hidup)."
        log "      UI tetap jalan; banner peringatan + tombol mode mock tersedia."
    fi
fi

# ---- 2. backend: FastAPI -------------------------------------------------
cd "${APP_DIR}/backend" || exit 1
"${PYTHON_BIN}" -m uvicorn app.main:app \
    --host "${BACKEND_HOST}" \
    --port "${BACKEND_PORT}" \
    --proxy-headers \
    --forwarded-allow-ips '*' &
BACKEND_PID=$!

# ---- 3. frontend: Next.js production server ------------------------------
cd "${APP_DIR}/frontend" || exit 1
node_modules/.bin/next start --hostname "${HOST}" --port "${PORT}" &
FRONTEND_PID=$!

SHUTTING_DOWN=0
shutdown() {
    [ "${SHUTTING_DOWN}" = "1" ] && return 0
    SHUTTING_DOWN=1
    trap - TERM INT
    log "shutting down (backend=${BACKEND_PID}, frontend=${FRONTEND_PID})"
    kill -TERM "${BACKEND_PID}" "${FRONTEND_PID}" 2>/dev/null || true
    wait "${BACKEND_PID}" "${FRONTEND_PID}" 2>/dev/null || true
}

# `docker stop` / tombol Stop & Restart di Coolify → matikan keduanya lalu
# keluar dengan 0 (bukan 143) supaya tidak terbaca sebagai crash.
on_terminate() {
    log "menerima sinyal berhenti dari orchestrator"
    shutdown
    exit 0
}
trap on_terminate TERM INT

# ---- 4. kalau salah satu proses mati, matikan container ------------------
# (docker/Coolify akan restart sesuai policy)
EXIT_CODE=0
wait -n || EXIT_CODE=$?
log "proses anak berhenti (exit ${EXIT_CODE}) — mematikan container"
shutdown
exit "${EXIT_CODE}"
