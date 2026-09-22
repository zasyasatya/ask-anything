"""Penjagaan penyimpanan persisten (anti "data hilang setelah redeploy").

Semua state aplikasi tinggal di SATU direktori data (`ASK_DATA_DIR`, default
`/app/data` di container): SQLite, artifact, arsip RAG, model offline, backup.
Kalau direktori itu ternyata cuma lapisan tulis container (bukan volume /
bind mount ke disk server), maka setiap redeploy membuang seluruh database —
termasuk hasil reset password admin — tanpa satu pun pesan error.

Modul ini membuat kondisi itu **terlihat**:

* :func:`report` memeriksa apakah direktori data benar-benar mount point,
  bisa ditulis, berapa sisa disk, dan berapa kali container sudah boot di
  atas direktori yang sama (bukti persistensi lintas redeploy);
* :func:`touch_marker` mencatat jejak boot di `<data>/.persistence.json`;
* hasilnya diteruskan ke `/api/health` dan `/api/admin/storage`, serta
  dicatat ke `app.startup` supaya muncul di log & UI.

Penegakan keras (menolak start saat direktori data bukan mount) dilakukan
`docker/entrypoint.sh` — di sana kegagalan masih terbaca di log deploy,
sedangkan backend sengaja tetap hidup agar pesannya bisa dibaca dari UI.

Modul ini tidak pernah melempar ke pemanggil: semua probe dibungkus.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

from . import startup
from .config import settings

#: Nama berkas penanda di dalam direktori data.
MARKER_NAME = ".persistence.json"

#: Set ke "1"/"true" bila deploy memang sengaja ephemeral (uji coba/CI).
_ALLOW_EPHEMERAL_ENV = "ASK_ALLOW_EPHEMERAL_DATA"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def allow_ephemeral() -> bool:
    return _truthy(os.environ.get(_ALLOW_EPHEMERAL_ENV))


def data_dir() -> Path:
    """Direktori yang HARUS persisten (induk dari berkas SQLite)."""
    return settings.resolved_data_dir()


def in_container() -> bool:
    """True bila proses jalan di dalam container Docker/Kubernetes."""
    if Path("/.dockerenv").exists():
        return True
    try:
        cgroup = Path("/proc/1/cgroup").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return any(tag in cgroup for tag in ("docker", "containerd", "kubepods", "lxc"))


def _mount_source(path: Path) -> str:
    """Sumber mount (device/host path) untuk `path`, "" bila tidak diketahui.

    Dibaca dari `/proc/self/mountinfo`: kolom 5 = mount point, kolom 4 = root
    di dalam device sumber. Bind mount dari disk server muncul dengan root
    berupa path host (mis. `/opt/ask-anything/data`), named volume Docker
    sebagai `/var/lib/docker/volumes/<nama>/_data`.
    """
    target = str(path)
    try:
        lines = Path("/proc/self/mountinfo").read_text(
            encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    for line in lines:
        fields = line.split(" ")
        if len(fields) >= 5 and fields[4] == target:
            return fields[3]
    return ""


def is_mounted(path: Path) -> bool | None:
    """True bila `path` mount point tersendiri; None bila tak bisa dipastikan.

    Dipakai dua bukti yang saling menguatkan: entri di `/proc/self/mountinfo`,
    dan `st_dev` yang berbeda dari root filesystem (volume/bind mount selalu
    device lain dari overlayfs container).
    """
    if platform.system() != "Linux":
        return None
    try:
        if _mount_source(path):
            return True
        return os.stat(path).st_dev != os.stat("/").st_dev
    except OSError:
        return None


def _free_bytes(path: Path) -> int | None:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


def _writable(path: Path) -> bool:
    probe = path / ".write-probe"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        return True
    except OSError:
        return False
    finally:
        try:
            probe.unlink()
        except OSError:
            pass


def read_marker() -> dict[str, Any]:
    """Isi `<data>/.persistence.json` (kosong bila belum ada/tak terbaca)."""
    try:
        raw = (data_dir() / MARKER_NAME).read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def touch_marker() -> dict[str, Any]:
    """Catat boot ini di berkas penanda dan kembalikan isinya.

    `boots` yang naik di direktori data yang sama = bukti langsung bahwa
    redeploy TIDAK menghapus data. `boots` yang selalu 1 = direktori data
    baru setiap deploy (volume belum ter-mount).
    """
    marker = read_marker()
    now = time.time()
    marker.setdefault("created_at", now)
    marker["boots"] = int(marker.get("boots") or 0) + 1
    marker["last_boot"] = now
    marker["db_path"] = str(settings.resolved_db_path())
    try:
        path = data_dir() / MARKER_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    except OSError as exc:
        startup.add("storage",
                    f"Penanda persistensi tidak bisa ditulis di {data_dir()}.",
                    hint="Pastikan direktori data writable oleh uid proses.",
                    detail=f"{type(exc).__name__}: {exc}")
    return marker


def report(*, marker: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ringkasan lengkap kondisi penyimpanan (health & konsol admin)."""
    path = data_dir()
    db = settings.resolved_db_path()
    container = in_container()
    mounted = is_mounted(path)
    mark = read_marker() if marker is None else marker
    try:
        db_bytes = db.stat().st_size
    except OSError:
        db_bytes = 0
    # Di luar container (dev lokal) disk mesin memang sudah persisten; di
    # dalam container hanya mount tersendiri yang selamat dari redeploy.
    persistent: bool | None = True if not container else mounted
    out: dict[str, Any] = {
        "data_dir": str(path),
        "db_path": str(db),
        "db_bytes": db_bytes,
        "artifacts_dir": str(settings.resolved_artifacts_dir()),
        "rag_dir": str(settings.resolved_rag_dir()),
        "models_dir": str(settings.resolved_models_dir()),
        "backups_dir": str(path / "backups"),
        "in_container": container,
        "mounted": mounted,
        "mount_source": _mount_source(path),
        "persistent": persistent,
        "writable": _writable(path),
        "free_bytes": _free_bytes(path),
        "boots": int(mark.get("boots") or 0),
        "first_boot": mark.get("created_at"),
        "last_boot": mark.get("last_boot"),
        "allow_ephemeral": allow_ephemeral(),
    }
    out["warning"] = _warning_for(out)
    return out


def _warning_for(rep: dict[str, Any]) -> str:
    if not rep["writable"]:
        return (f"Direktori data '{rep['data_dir']}' tidak bisa ditulis — "
                "database & artifact tidak akan tersimpan.")
    if rep["in_container"] and rep["persistent"] is False:
        return (f"'{rep['data_dir']}' bukan volume/bind mount: isinya hanya "
                "ada di lapisan tulis container dan HILANG setiap redeploy "
                "(termasuk hasil reset password). Mount direktori disk server "
                f"ke {rep['data_dir']}.")
    if rep["in_container"] and rep["persistent"] is None:
        return (f"Status mount '{rep['data_dir']}' tidak bisa dipastikan — "
                "verifikasi manual bahwa direktori itu volume/bind mount.")
    return ""


def summary() -> dict[str, Any]:
    """Versi ringkas untuk `/api/health`."""
    rep = report()
    return {
        "data_dir": rep["data_dir"],
        "persistent": rep["persistent"],
        "writable": rep["writable"],
        "db_bytes": rep["db_bytes"],
        "boots": rep["boots"],
        "warning": rep["warning"],
    }


def backups_dir() -> Path:
    return settings.resolved_backups_dir()


def list_backups(limit: int = 20) -> list[dict[str, Any]]:
    """Salinan SQLite yang tersedia, terbaru dulu."""
    out: list[dict[str, Any]] = []
    try:
        entries = sorted(backups_dir().glob("ask_anything-*.db"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return out
    for path in entries[:limit]:
        try:
            st = path.stat()
        except OSError:
            continue
        out.append({"name": path.name, "path": str(path),
                    "bytes": st.st_size, "mtime": st.st_mtime})
    return out


def backup_now(keep: int = 7) -> Path:
    """Salin database dengan API backup SQLite (aman walau ada penulis lain).

    `cp` biasa bisa menangkap berkas di tengah transaksi; `Connection.backup`
    menghasilkan salinan yang konsisten tanpa menghentikan aplikasi.
    """
    src = settings.resolved_db_path()
    target_dir = backups_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = target_dir / f"ask_anything-{stamp}.db"
    source = sqlite3.connect(str(src))
    try:
        dest = sqlite3.connect(str(target))
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()
    _prune_backups(keep)
    return target


def _prune_backups(keep: int) -> None:
    for item in list_backups(limit=1000)[keep:]:
        try:
            Path(item["path"]).unlink()
        except OSError:
            pass


def check_at_startup() -> dict[str, Any]:
    """Probe + catat penanda saat backend start; keluhkan lewat `app.startup`."""
    try:
        mark = touch_marker()
        rep = report(marker=mark)
    except Exception as exc:  # noqa: BLE001 - diagnosa tidak boleh mematikan app
        startup.add("storage", "Pemeriksaan persistensi gagal.",
                    detail=f"{type(exc).__name__}: {exc}")
        return {}

    if not rep["warning"]:
        src = rep["mount_source"] or ("disk lokal" if not rep["in_container"] else "?")
        print(f"[storage] data persisten di {rep['data_dir']} "
              f"(sumber: {src}, boot ke-{rep['boots']}, "
              f"db {rep['db_bytes'] // 1024} KB)", flush=True)
    elif rep["persistent"] is False and allow_ephemeral():
        print(f"[storage] EPHEMERAL disengaja ({_ALLOW_EPHEMERAL_ENV}=1): "
              f"{rep['warning']}", flush=True)
    else:
        startup.add(
            "storage", rep["warning"],
            hint="Coolify: Persistent Storage -> Source = direktori disk "
                 "server (mis. /opt/ask-anything/data), Destination = "
                 f"{rep['data_dir']}, lalu chown 1000:1000 direktori itu.",
            detail=f"mounted={rep['mounted']} "
                   f"source={rep['mount_source'] or '-'} boots={rep['boots']}")
    return rep
