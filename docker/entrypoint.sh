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
#
# PERSISTENCE: seluruh state live di bawah /app/data (SATU volume):
#   ask_anything.db  SQLite — chat, users, tasks, RAG index, governance
#   artifacts/       file biner artifact (gambar/PPTX/diagram)
#   rag/             arsip PDF mentah mode RAG
#   models/          model offline yang diunduh (HuggingFace Hub)
#   backups/         salinan SQLite tiap start (dipangkas otomatis, 7 terakhir)
# Mount named volume ke /app/data → redeploy TIDAK menghapus data.
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
HOST="${HOST:-0.0.0.0}"                     # Coolify inject HOST=0.0.0.0
PORT="${PORT:-3000}"                        # Coolify inject PORT = exposed port
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-${APP_DIR}/.venv/bin/python}"

# Konfigurasi aplikasi (dibaca pydantic-settings backend, prefix ASK_).
# SATU variabel menentukan letak seluruh state: ASK_DATA_DIR. Sisanya turunan,
# jadi memindahkan storage ke disk lain cukup satu env + satu mount.
export ASK_DATA_DIR="${ASK_DATA_DIR:-${APP_DIR}/data}"
export ASK_DB_PATH="${ASK_DB_PATH:-${ASK_DATA_DIR}/ask_anything.db}"
export ASK_ARTIFACTS_DIR="${ASK_ARTIFACTS_DIR:-${ASK_DATA_DIR}/artifacts}"
export ASK_RAG_DIR="${ASK_RAG_DIR:-${ASK_DATA_DIR}/rag}"
export ASK_MODELS_DIR="${ASK_MODELS_DIR:-${ASK_DATA_DIR}/models}"
# Target rewrite Next. Catatan: nilai ini ikut ter-bake saat `next build`
# (lihat Dockerfile ARG BACKEND_PORT) — default sudah cocok untuk in-container.
export BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:${BACKEND_PORT}}"

log() { printf '[ask-anything] %s\n' "$*"; }

# ---- 0. siapkan + validasi folder persisten --------------------------------
DB_DIR="$(dirname "${ASK_DB_PATH}")"
BACKUP_DIR="${ASK_DATA_DIR}/backups"
mkdir -p "${ASK_DATA_DIR}" "${DB_DIR}" "${ASK_ARTIFACTS_DIR}" "${ASK_RAG_DIR}"          "${ASK_MODELS_DIR}" "${BACKUP_DIR}" 2>/dev/null || true
for d in "${ASK_DATA_DIR}" "${DB_DIR}" "${ASK_ARTIFACTS_DIR}" "${ASK_RAG_DIR}" "${ASK_MODELS_DIR}"; do
    if [ ! -w "${d}" ]; then
        log "ERROR: ${d} tidak bisa ditulis."
        log "       Di Coolify: mount direktori disk server ke ${ASK_DATA_DIR}"
        log "       (Storages), lalu di server jalankan:"
        log "         sudo chown -R 1000:1000 <direktori host tersebut>"
        log "       Atau set ASK_DATA_DIR ke direktori lain yang writable."
        exit 1
    fi
done

# ---- 0a. GERBANG PERSISTENSI ----------------------------------------------
# Direktori data yang BUKAN mount point berarti data hanya hidup di lapisan
# tulis container: tiap redeploy membuat container baru dan seluruh database
# (akun, password hasil reset, transaksi, master data) lenyap tanpa error.
# Itulah gejala "kok data saya ke-reset lagi?". Karena itu container menolak
# start, kecuali deploy memang sengaja ephemeral (ASK_ALLOW_EPHEMERAL_DATA=1).
is_mount_point() {  # <dir> -> 0 bila mount tersendiri
    if command -v mountpoint >/dev/null 2>&1; then
        mountpoint -q "$1" && return 0
    fi
    # mountinfo kolom 5 = mount point; fallback = beda device id dengan root.
    if [ -r /proc/self/mountinfo ]        && awk -v t="$1" '$5 == t { found = 1 } END { exit !found }' /proc/self/mountinfo; then
        return 0
    fi
    DEV_DATA="$(stat -c %d "$1" 2>/dev/null || echo x)"
    DEV_ROOT="$(stat -c %d / 2>/dev/null || echo y)"
    [ "${DEV_DATA}" != "${DEV_ROOT}" ]
}

ALLOW_EPHEMERAL="$(printf '%s' "${ASK_ALLOW_EPHEMERAL_DATA:-}" | tr 'A-Z' 'a-z')"
case "${ALLOW_EPHEMERAL}" in 1|true|yes|on) ALLOW_EPHEMERAL=1 ;; *) ALLOW_EPHEMERAL=0 ;; esac

if is_mount_point "${ASK_DATA_DIR}"; then
    MOUNT_SRC="$(awk -v t="${ASK_DATA_DIR}" '$5 == t { print $4; exit }'                  /proc/self/mountinfo 2>/dev/null)"
    log "persistensi: ${ASK_DATA_DIR} ter-mount (sumber: ${MOUNT_SRC:-?}) - OK"
elif [ "${ALLOW_EPHEMERAL}" = "1" ]; then
    log "persistensi: ${ASK_DATA_DIR} TIDAK ter-mount, tetapi"
    log "             ASK_ALLOW_EPHEMERAL_DATA=1 -> lanjut (data akan hilang)."
else
    log "ERROR: ${ASK_DATA_DIR} bukan volume/bind mount."
    log "       Data hanya tersimpan di dalam container dan HILANG pada"
    log "       redeploy berikutnya (termasuk hasil reset password)."
    log "       Perbaiki di Coolify: Storages -> Add -> Directory Mount,"
    log "         Source (disk server)   : /opt/ask-anything/data"
    log "         Destination (container): ${ASK_DATA_DIR}"
    log "       lalu di server: sudo mkdir -p /opt/ask-anything/data &&"
    log "                       sudo chown -R 1000:1000 /opt/ask-anything/data"
    log "       Docker/Compose: -v /opt/ask-anything/data:${ASK_DATA_DIR}"
    log "       Sengaja ephemeral (uji coba)? set ASK_ALLOW_EPHEMERAL_DATA=1."
    exit 1
fi

# ---- 0b. migrasi sekali-jalan dari lokasi lama (deployment sebelum volume) --
# Kalau volume baru masih kosong tapi ada database/model dari layout lama
# (ephemeral layer image), pindahkan — jangan biarkan user mengira datanya
# hilang ("reset") setelah redeploy pertama dengan volume.
migrate_file() {  # <sumber> <tujuan> <label>
    if [ -f "$1" ] && [ ! -f "$2" ]; then
        if cp -p "$1" "$2" 2>/dev/null; then
            log "migrasi ${3}: $1 → $2"
        else
            log "WARN: gagal memigrasi ${3} dari $1"
        fi
    fi
}
migrate_dir() {  # <sumber> <tujuan> <label>
    if [ -d "$1" ] && [ -z "$(ls -A "$2" 2>/dev/null)" ] && [ -n "$(ls -A "$1" 2>/dev/null)" ]; then
        if cp -rn "$1"/. "$2"/ 2>/dev/null; then
            log "migrasi ${3}: $1/ → $2/"
        else
            log "WARN: gagal memigrasi ${3} dari $1/"
        fi
    fi
}
migrate_file "${APP_DIR}/backend/data/ask_anything.db" "${ASK_DB_PATH}" "database SQLite"
migrate_file "${APP_DIR}/data.ask_anything.db" "${ASK_DB_PATH}" "database SQLite"
migrate_dir "${APP_DIR}/backend/data/artifacts" "${ASK_ARTIFACTS_DIR}" "artifact"
migrate_dir "${APP_DIR}/backend/data/rag" "${ASK_RAG_DIR}" "arsip RAG"
migrate_dir "${APP_DIR}/models" "${ASK_MODELS_DIR}" "model offline"

# ---- 0c. backup SQLite sebelum start (murah, menyelamatkan dari korup) ------
if [ -f "${ASK_DB_PATH}" ]; then
    STAMP="$(date +%Y%m%d-%H%M%S)"
    if cp -p "${ASK_DB_PATH}" "${BACKUP_DIR}/ask_anything-${STAMP}.db" 2>/dev/null; then
        # Pangkas: simpan 7 backup terakhir saja.
        ls -1t "${BACKUP_DIR}"/ask_anything-*.db 2>/dev/null | tail -n +8 | xargs -r rm -f --
    else
        log "WARN: gagal membuat backup database (lanjut tanpa backup)."
    fi
fi

if [ ! -x "${PYTHON_BIN}" ]; then
    log "ERROR: python venv tidak ditemukan di ${PYTHON_BIN}."
    exit 1
fi

log "backend  : http://${BACKEND_HOST}:${BACKEND_PORT} (internal, tidak di-expose)"
log "frontend : http://${HOST}:${PORT} (publik — di-proxy Coolify/Traefik)"
log "database : ${ASK_DB_PATH}"
log "artifacts: ${ASK_ARTIFACTS_DIR}"
log "rag      : ${ASK_RAG_DIR}"
log "models   : ${ASK_MODELS_DIR}"
log "provider : ${ASK_PROVIDER:-huggingface (default app)}"
if [ -f "${ASK_DB_PATH}" ]; then
    DB_SIZE="$(du -h "${ASK_DB_PATH}" 2>/dev/null | cut -f1)"
    log "db size  : ${DB_SIZE:-?} (data lama terdeteksi — redeploy aman, tidak di-reset)"
else
    log "db size  : (baru — database akan dibuat saat backend start)"
fi

# ---- 1. probe LLM server (sekadar peringatan, tidak memblokir start) ------
# Default app = provider "huggingface" mode local (butuh model di models/ +
# torch/transformers, yang tidak ada di image) — di VPS set ASK_PROVIDER=openai.
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
