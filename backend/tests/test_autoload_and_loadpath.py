"""Model offline "apapun modelnya diload, pasti jalan".

Dua jaminan yang diuji di sini:

1. **Auto-load saat (re)start** — backend memilihkan sendiri model di
   `models/` (atau model terakhir yang dipakai lewat `models/.active.json`)
   dan memuatnya, tanpa user harus mengklik apa pun lagi.
2. **Muat dari folder mana pun** — `POST /api/hf/models/load` menerima
   SEMANGKAH folder di disk yang memuat `config.json` (termasuk di luar
   `models/`, mis. hasil `huggingface-cli download --local-dir ~/…`).
"""
import json
import time
from pathlib import Path

import pytest

from app import hf_hub
from app.config import settings
from app.local_inference import dependencies, engine
from tests.test_local_inference import tiny_model

needs_torch = pytest.mark.skipif(
    not dependencies()["available"],
    reason="torch/transformers tidak ter-install (backend/requirements-local.txt)")


def _fake_model_folder(root, name="org/TinyModel", complete=True,
                       downloaded_at=1_700_000_000):
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.json").write_text(
        json.dumps({"architectures": ["LlamaForCausalLM"]}), encoding="utf-8")
    if complete:
        (path / hf_hub.MANIFEST_NAME).write_text(json.dumps({
            "repo_id": name, "complete": True,
            "downloaded_at": downloaded_at}), encoding="utf-8")
    return path


@pytest.fixture()
def torch_ready(monkeypatch):
    """Autoload diuji tanpa memerlukan torch sungguhan di mesin ini.

    Produksi: `_deps()` melaporkan ketersediaan torch/transformers. Di sini
    dilaporkan "siap" supaya logika pemilihan model (prioritas folder, model
    terakhir dipakai, `.active.json`) tetap teruji walau torch tak ter-install.
    """
    import app.main as main

    monkeypatch.setattr(main, "_deps", lambda: {
        "available": True, "torch": "test", "transformers": "test",
        "device": "cpu", "install_hint": None})


class _RecordingEngine:
    def __init__(self):
        self.calls = []

    def start_load(self, path, **kw):
        self.calls.append(str(path))


class _BoomEngine:
    def start_load(self, *a, **k):
        raise AssertionError("engine tidak boleh disentuh untuk konfigurasi ini")


# ---------------------------------------------------------------------------
# auto-load di startup (app.main._autoload_local_model)
# ---------------------------------------------------------------------------
def test_autoload_picks_newest_model_in_models_dir(monkeypatch, tmp_path,
                                                   torch_ready):
    monkeypatch.setattr(settings, "provider", "huggingface")
    monkeypatch.setattr(settings, "hf_mode", "local")
    monkeypatch.setattr(settings, "hf_model", "")
    monkeypatch.setattr(settings, "models_dir", str(tmp_path / "models"))

    _fake_model_folder(tmp_path / "models", "org/Old",
                       downloaded_at=1_700_000_000)
    _fake_model_folder(tmp_path / "models", "org/New",
                       downloaded_at=1_800_000_000)  # lebih baru → dipilih

    import app.main as main

    rec = _RecordingEngine()
    monkeypatch.setattr(main, "llm_engine", rec)
    main._autoload_local_model()

    assert len(rec.calls) == 1
    # Windows memakai `\` sebagai pemisah path, jadi bandingkan sebagai Path
    # (bukan `endswith("org/New")` yang hanya benar di POSIX).
    assert Path(rec.calls[0]).parts[-2:] == ("org", "New")
    assert settings.hf_model == "org/New"


def test_autoload_restores_active_model_outside_models_dir(monkeypatch,
                                                           tmp_path, torch_ready):
    """Model dari folder DI LUAR models/ (via /api/hf/models/load) tetap
    di-muat-ulang otomatis setelah restart — lewat models/.active.json."""
    monkeypatch.setattr(settings, "provider", "huggingface")
    monkeypatch.setattr(settings, "hf_mode", "local")
    monkeypatch.setattr(settings, "hf_model", "")
    outside = tmp_path / "elsewhere" / "MyModel"
    outside.mkdir(parents=True)
    (outside / "config.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(settings, "models_dir", str(tmp_path / "models"))
    hf_hub.set_active("org/MyModel", str(outside))

    import app.main as main

    rec = _RecordingEngine()
    monkeypatch.setattr(main, "llm_engine", rec)
    main._autoload_local_model()

    assert rec.calls == [str(outside)]
    assert settings.hf_model == "org/MyModel"


def test_autoload_does_nothing_for_other_providers(monkeypatch, tmp_path,
                                                   torch_ready):
    monkeypatch.setattr(settings, "provider", "mock")
    monkeypatch.setattr(settings, "hf_mode", "local")
    monkeypatch.setattr(settings, "models_dir", str(tmp_path / "models"))
    _fake_model_folder(tmp_path / "models")

    import app.main as main

    monkeypatch.setattr(main, "llm_engine", _BoomEngine())
    main._autoload_local_model()  # harus return tanpa menyentuh engine


# ---------------------------------------------------------------------------
# POST /api/hf/models/load — folder model di SEMANGKAH lokasi
# ---------------------------------------------------------------------------
@needs_torch
async def test_load_endpoint_registers_and_loads_any_folder(client, tiny_model,
                                                            tmp_path,
                                                            monkeypatch):
    """Model asli (fixture `tiny_model`) dipindah ke luar `models/` lalu
    di-load lewat endpoint — folder terdaftar, settings diarahkan, engine siap."""
    import shutil

    dest = tmp_path / "outside" / "TinyLlama-Test"
    shutil.copytree(tiny_model, dest)

    # isolasi: models_dir + models/.active.json tidak boleh menyentuh folder
    # project sungguhan selama test
    monkeypatch.setattr(settings, "models_dir", str(tmp_path / "models"))
    (tmp_path / "models").mkdir(parents=True, exist_ok=True)

    # endpoint mengubah singleton settings — kembalikan setelah test
    saved = (settings.provider, settings.hf_mode, settings.hf_model)
    try:
        r = client.post("/api/hf/models/load", json={"path": str(dest)})
        assert r.status_code == 200
        out = r.json()
        assert out.get("ok") is True, out
        assert out["repo_id"] == "ask-anything/TinyLlama-Test"
        assert out["settings"]["provider"] == "huggingface"
        assert out["settings"]["hf_mode"] == "local"
        assert out["settings"]["local_model_path"] == str(dest.resolve())
        # manifest ada (dibaca, bukan ditulis ulang) → folder 'lengkap'
        assert (dest / hf_hub.MANIFEST_NAME).is_file()

        # engine beralih ke folder di luar models/ — load berjalan di
        # background, jadi tunggu sampai siap (model kecil → beberapa detik).
        deadline = time.time() + 30
        st = {}
        while time.time() < deadline:
            st = client.get("/api/hf/runtime").json()
            if st["state"] in ("ready", "error"):
                break
            time.sleep(0.2)
        assert st["state"] == "ready", st
        assert Path(st["model_path"]).parts[-2:] == ("outside", "TinyLlama-Test")
    finally:
        settings.provider, settings.hf_mode, settings.hf_model = saved
        await engine.unload()  # bersihkan engine untuk test berikutnya


@needs_torch
async def test_provider_waits_for_model_still_loading(tiny_model, monkeypatch):
    """Chat yang dikirim SEMENTARA model masih di-load tidak boleh gagal:
    provider memberi tahu (note) lalu menunggu sampai engine siap."""
    from app.config import update_settings
    from app.providers import HFLocalProvider

    saved = (settings.provider, settings.hf_mode, settings.hf_model,
             settings.max_tokens)
    try:
        update_settings(provider="huggingface", hf_mode="local",
                        hf_model="ask-anything/TinyLlama-Test")
        monkeypatch.setattr(settings, "max_tokens", 8)
        await engine.unload()
        # paksa kondisi "lagi di-load", wait_load = load sungguhan
        engine.state = "loading"

        async def fake_wait(timeout=None):
            await engine.load(tiny_model)
            return engine.status()

        monkeypatch.setattr(engine, "wait_load", fake_wait)
        provider = HFLocalProvider(settings)
        events = [e async for e in provider.stream(
            [{"role": "user", "content": "halo"}], [], max_tokens=8)]
        types = [e.type for e in events]
        assert events[0].type == "note"
        assert events[0].data["status"] == "loading"
        assert "delta" in types, types
        assert "error" not in types
    finally:
        settings.provider, settings.hf_mode, settings.hf_model = saved[:3]
        settings.max_tokens = saved[3]
        await engine.unload()


def test_load_endpoint_rejects_non_model_folder(client, tmp_path):
    bad = tmp_path / "bukan-model"
    bad.mkdir()
    r = client.post("/api/hf/models/load", json={"path": str(bad)})
    assert r.status_code == 200
    assert "config.json" in r.json()["error"]


def test_load_endpoint_rejects_empty_path(client):
    r = client.post("/api/hf/models/load", json={"path": "   "})
    assert r.status_code == 200
    assert "error" in r.json()
