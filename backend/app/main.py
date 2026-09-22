"""Ask Anything — FastAPI application entry point.

Prinsip startup: **server harus selalu hidup**. Model lokal (torch/transformers)
bersifat opsional dan sering rusak di Windows (`OSError WinError 1114` pada
`c10.dll`); kalau itu sampai melempar dari `lifespan`, uvicorn mati sebelum
membuka port dan `run.py` cuma melaporkan "backend did not become healthy".
Karena itu semua langkah opsional dibungkus, dicatat di `app.startup`, dan
dijalankan di background — health check tetap membalas walau model gagal.
"""
from __future__ import annotations

import asyncio
import threading
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__, db, hf_hub, persistence, startup, tasks, users
from .api.admin import router as admin_router
from .api.auth_api import router as auth_router
from .api.internship import router as internship_router
from .api.routes import public_router, router
from .api.tasks import router as tasks_router
from .config import settings
from .local_inference import dependencies as _deps, engine as llm_engine

#: Hasil autoload terakhir (dibaca `/api/health`, bukan sumber kebenaran).
AUTOLOAD_STATE: dict[str, str] = {"state": "idle", "detail": ""}


def _autoload_local_model() -> None:
    """Muat model offline secara otomatis saat backend (re)start.

    Urutan prioritas:
      1. `settings.hf_model` bila foldernya ada di `models/`,
      2. model terakhir yang dipakai (`models/.active.json` — mencakup
         model dari folder di luar `models/`),
      3. model terunduh paling baru yang lengkap di `models/`.

    Load berjalan di background: server langsung sehat & UI menampilkan
    layar "memuat model…"; begitu engine siap, chat langsung bisa dipakai.
    """
    if settings.provider != "huggingface" or (settings.hf_mode or "local") != "local":
        AUTOLOAD_STATE.update(state="skipped", detail="provider bukan huggingface lokal")
        return

    deps = _deps()  # tak pernah melempar, termasuk saat DLL torch rusak
    if not deps["available"]:
        AUTOLOAD_STATE.update(state="unavailable", detail=deps.get("install_hint") or "")
        print("[autoloader] torch/transformers belum siap — model lokal tidak "
              "di-load otomatis. python run.py --install-local", flush=True)
        startup.add(
            "autoloader",
            "PyTorch/transformers belum bisa dijalankan, model lokal tidak dimuat.",
            hint="python run.py --install-local (mendeteksi torch rusak & "
                 "pasang ulang otomatis), atau jalankan dengan "
                 "--provider openai / --demo.",
            detail=deps.get("install_hint") or "",
        )
        return

    target: tuple[str, str] | None = None
    if settings.hf_model:
        path = hf_hub.resolve_local(settings.hf_model)
        if path is not None:
            target = (settings.hf_model, str(path))
        else:
            active = hf_hub.active_model()
            if active and active[0] == settings.hf_model:
                target = active
    if target is None:
        active = hf_hub.active_model()
        if active is not None:
            target = active
    if target is None:
        picked = hf_hub.auto_pick_model()
        if picked is not None:
            target = picked

    if target is None:
        AUTOLOAD_STATE.update(state="no-model", detail="")
        print("[autoloader] belum ada model offline di models/ — "
              "unduh lewat Settings → Model offline (HuggingFace)", flush=True)
        return

    repo_id, path = target
    if settings.hf_model != repo_id:
        settings.hf_model = repo_id
        hf_hub.set_active(repo_id, path)
    try:
        llm_engine.start_load(path)
    except Exception as exc:  # noqa: BLE001 - load model tidak boleh mematikan server
        AUTOLOAD_STATE.update(state="error", detail=f"{type(exc).__name__}: {exc}")
        print(f"[autoloader] gagal memulai load: {exc}", flush=True)
        startup.add("autoloader", f"Gagal memuat model {repo_id}.",
                    hint="Periksa folder model / coba model lebih kecil.",
                    detail=traceback.format_exc())
        return
    AUTOLOAD_STATE.update(state="loading", detail=repo_id)
    print(f"[autoloader] memuat model {repo_id} dari {path} …", flush=True)


def _run_autoload_in_background() -> None:
    """Jalankan autoload di thread daemon (startup tidak pernah tersandera)."""
    def worker() -> None:
        try:
            _autoload_local_model()
        except BaseException as exc:  # noqa: BLE001 - apa pun tak boleh mematikan server
            AUTOLOAD_STATE.update(state="error", detail=f"{type(exc).__name__}: {exc}")
            startup.add("autoloader", f"Autoload gagal: {type(exc).__name__}.",
                        detail=traceback.format_exc())

    threading.Thread(target=worker, name="model-autoload", daemon=True).start()


def _init_storage() -> None:
    """Siapkan SQLite + folder model/artifact/rag. Gagal → pesan yang bisa ditindak."""
    # Cek persistensi SEBELUM database dibuat: kalau direktori data ternyata
    # hanya lapisan tulis container, peringatannya harus sudah tercatat saat
    # SQLite baru (kosong) dibuat — itu justru gejala "data hilang tiap
    # redeploy" yang ingin dijelaskan ke admin.
    persistence.check_at_startup()
    try:
        db.init_db(str(settings.resolved_db_path()))
    except Exception as exc:  # noqa: BLE001 - bungkus jadi pesan jelas
        raise RuntimeError(
            f"Tidak bisa menyiapkan database SQLite di "
            f"'{settings.resolved_db_path()}': "
            f"{type(exc).__name__}: {exc}\n"
            "Periksa apakah foldernya bisa ditulis (OneDrive/antivirus kadang "
            "mengunci file; di Docker/Coolify pastikan volume ter-mount di "
            "/app/data). Set ASK_DB_PATH ke lokasi lain bila perlu."
        ) from exc

    for label, path, env in (
        ("model", settings.resolved_models_dir(), "ASK_MODELS_DIR"),
        ("artifact", settings.resolved_artifacts_dir(), "ASK_ARTIFACTS_DIR"),
        ("arsip RAG", settings.resolved_rag_dir(), "ASK_RAG_DIR"),
    ):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            startup.add("storage",
                        f"Folder {label} '{path}' tidak bisa dibuat.",
                        hint=f"Set {env} ke folder lain yang bisa ditulis.",
                        detail=f"{type(exc).__name__}: {exc}")

    # Task management: isi papan dengan rencana RAG pada boot pertama.
    if settings.tasks_autoseed:
        try:
            created = tasks.seed_if_empty()
            if created:
                print(f"[tasks] {len(created)} task rencana dimuat ke papan "
                      f"(halaman /tasks)", flush=True)
        except Exception as exc:  # noqa: BLE001 - fitur tracker, bukan jalur kritis
            startup.add("tasks", "Gagal memuat task rencana ke papan.",
                        detail=f"{type(exc).__name__}: {exc}")
        # Papan proyek internship (track terpisah, halaman /internship).
        try:
            created_intern = tasks.seed_track_if_empty("internship")
            if created_intern:
                print(f"[tasks] {len(created_intern)} task proyek internship "
                      f"dimuat ke papan /internship", flush=True)
            # Rencana internship yang ditulis ulang (PLAN_REVISION naik) harus
            # ikut turun ke papan yang sudah ter-seed — progres dibawa pindah.
            refreshed = tasks.refresh_plan_if_stale("internship")
            if refreshed.get("changed") and not refreshed.get("first_seed"):
                print(f"[tasks] rencana internship diperbarui ke revisi "
                      f"{refreshed['revision']} "
                      f"({len(refreshed.get('created') or [])} task, "
                      f"{refreshed.get('restored', 0)} progres dipertahankan)",
                      flush=True)
        except Exception as exc:  # noqa: BLE001
            startup.add("tasks", "Gagal memuat task proyek internship.",
                        detail=f"{type(exc).__name__}: {exc}")

    # Login: buat akun awal bila tabel `users` masih kosong.
    try:
        seeded = users.ensure_seed_users(settings)
        if seeded.get("created"):
            names = ", ".join(f"{u['username']} ({u['role']})"
                              for u in seeded["created"])
            # ASCII saja: console Windows (cp1252) melempar UnicodeEncodeError
            # untuk karakter seperti "->" berbentuk panah, dan exception itu
            # dulu membuat seluruh seed akun dilaporkan gagal.
            print(f"[auth] akun awal dibuat: {names} - ganti password di "
                  f"Profil / Admin > Users", flush=True)
    except Exception as exc:  # noqa: BLE001 - login tetap bisa lewat token admin
        startup.add("auth", "Gagal membuat akun awal (login page).",
                    detail=f"{type(exc).__name__}: {exc}")

    # Akun anak internship (dibuat kapan pun belum ada, juga di DB lama).
    try:
        _ensure_intern_account()
    except Exception as exc:  # noqa: BLE001
        startup.add("auth", "Gagal membuat akun internship.",
                    detail=f"{type(exc).__name__}: {exc}")


def _ensure_intern_account() -> None:
    """Buat akun intern; password yang tergenerate dicatat sekali saja.

    Password acak hanya ada di memori sekali (setelahnya cuma hash yang
    tersimpan), jadi ditulis ke log startup **dan** ke
    `<folder data>/intern-credentials.txt` agar pembimbing bisa mengambilnya
    setelah deploy. Hapus berkas itu setelah kredensialnya diserahkan.
    """
    result = users.ensure_intern_account(settings)
    if not result.get("created"):
        return
    who = f"{result['username']} <{result.get('email') or '-'}>"
    if not result.get("generated"):
        print(f"[auth] akun internship dibuat: {who} (password dari "
              f"ASK_INTERN_PASSWORD)", flush=True)
        return

    password = result["password"]
    print(f"[auth] akun internship dibuat: {who} - password sekali-cetak: "
          f"{password} (wajib diganti saat login pertama)", flush=True)
    path = settings.resolved_db_path().parent / "intern-credentials.txt"
    try:
        path.write_text(
            "Akun internship Ask Anything\n"
            f"nama      : {result.get('name', '')}\n"
            f"username  : {result['username']}\n"
            f"email     : {result.get('email', '')}\n"
            f"password  : {password}\n"
            "catatan   : wajib diganti saat login pertama; hapus berkas ini\n"
            "            setelah kredensial diserahkan.\n",
            encoding="utf-8")
        try:  # POSIX: hanya pemilik yang boleh membaca (diabaikan di Windows)
            path.chmod(0o600)
        except OSError:
            pass
        print(f"[auth] kredensial internship juga ditulis ke {path} - "
              f"hapus setelah diserahkan.", flush=True)
    except OSError as exc:
        startup.add("auth", "Kredensial internship tidak bisa ditulis ke berkas.",
                    hint="Ambil password dari log startup di atas.",
                    detail=f"{type(exc).__name__}: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_storage()
    # Autoload berjalan di thread daemon; ikat loop ini dulu supaya thread itu
    # bisa menjadwalkan load model ke event loop aplikasi.
    llm_engine.bind_loop(asyncio.get_running_loop())
    _run_autoload_in_background()
    try:
        yield
    finally:
        # Lepas model lokal (bebaskan RAM/VRAM) saat aplikasi berhenti.
        try:
            await llm_engine.unload()
        except Exception:  # noqa: BLE001 - shutdown tidak boleh melempar
            pass


app = FastAPI(
    title="Ask Anything",
    version=__version__,
    description="Agentic AI chatbot: browsing + diagrams + mechanistic "
                "interpreter. HuggingFace local & OpenAI API providers.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Login/sesi (publik — justru karena itu pengguna bisa masuk).
app.include_router(auth_router)
# Health check: sengaja **tanpa** dependency sesi (run.py & HEALTHCHECK Docker).
app.include_router(public_router)
app.include_router(router)
# Konsol admin: policy pipeline, memori, artifact, feedback, users (/api/admin/*).
app.include_router(admin_router)
# Task management: papan rencana RAG + integrasi branch GitLab (/api/tasks/*).
app.include_router(tasks_router)
# Proyek internship: papan, materi, dan rencana (/api/internship/*).
app.include_router(internship_router)

# Serve docs/ (slides & metodologi) at /slides — frontend proxies /slides/*.
_DOCS = Path(__file__).resolve().parents[2] / "docs"
if _DOCS.is_dir():
    app.mount("/slides", StaticFiles(directory=_DOCS, html=True), name="slides")

# Screenshot dokumentasi (docs/images) — dipakai halaman /panduan & /developer.
_IMAGES = _DOCS / "images"
if _IMAGES.is_dir():
    app.mount("/docs-images", StaticFiles(directory=_IMAGES), name="docs-images")


@app.get("/")
async def root():
    return {
        "name": "Ask Anything",
        "version": __version__,
        "provider": settings.provider,
        "model": settings.active_model_label(),
        "hint": "frontend runs separately; API lives under /api",
    }
