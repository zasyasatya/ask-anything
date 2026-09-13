#!/usr/bin/env python3
"""Cari / unduh model HuggingFace ke folder `models/` — CLI di balik `run.py`.

Memakai downloader yang sama persis dengan yang dipanggil web UI
(`app.hf_hub`), jadi hasilnya identik: folder `models/<organisasi>/<nama>`
berisi config + tokenizer + `*.safetensors`, siap di-load `transformers`
tanpa llama.cpp.

    python scripts/download_model.py --search qwen3
    python scripts/download_model.py --search deepseek-ai/DeepSeek-V4.1-Flash
    python scripts/download_model.py Qwen/Qwen3-1.7B
    python scripts/download_model.py --list          # yang sudah terunduh
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import hf_hub  # noqa: E402
from app.local_inference import dependencies  # noqa: E402


def _fmt_gib(n: float) -> str:
    return f"{n / 1024**3:.2f} GiB"


async def search(query: str) -> int:
    out = await hf_hub.search_models(query)
    if not out["ok"]:
        print(f"gagal mencari: {out['error']}")
        return 2
    if not out["models"]:
        print(f"tidak ada hasil untuk “{query}”")
        return 1
    print(f"Hasil HuggingFace untuk “{query}”:")
    print(f"  {'repo id':52} {'params':>10} {'≈size':>10}  lokal")
    for m in out["models"]:
        params = f"{m['params'] / 1e9:.1f}B" if m["params"] else "—"
        size = _fmt_gib(m["size_bytes"]) if m["size_bytes"] else "—"
        local = "terunduh" if m["local"]["ready"] else (
            "sebagian" if m["local"]["exists"] else "")
        print(f"  {m['repo_id']:52} {params:>10} {size:>10}  {local}")
    print("\nUnduh:  python scripts/download_model.py <repo id>")
    return 0


def list_local() -> int:
    root = hf_hub.models_dir()
    models = hf_hub.list_local()
    print(f"Folder model: {root}")
    if not models:
        print("  (kosong — cari dulu: --search <nama>)")
        return 0
    print(f"  {'repo id':52} {'size':>10}  status")
    for m in models:
        status = "siap" if m["ready"] else "belum lengkap"
        print(f"  {m['repo_id']:52} {_fmt_gib(m['size_bytes']):>10}  {status}")
    return 0


async def download(repo_id: str) -> int:
    try:
        hf_hub.start_download(repo_id)
    except ValueError as exc:
        print(f"repo id tidak valid: {exc}")
        return 2

    last = 0.0
    while True:
        state = hf_hub.download_state(repo_id) or {}
        now = time.time()
        if state.get("status") == "downloading" and now - last >= 1.0:
            last = now
            print(f"  … {state.get('percent', 0):5.1f}%  "
                  f"{state.get('downloaded', 0) / 1024**2:9.1f} MiB / "
                  f"{state.get('total', 0) / 1024**2:.1f} MiB  "
                  f"{state.get('speed_bps', 0) / 1024**2:5.1f} MiB/s  "
                  f"{state.get('file', '')}")
            await asyncio.sleep(0.25)
            continue
        if state.get("status") == "downloading":
            await asyncio.sleep(0.25)
            continue
        break

    state = hf_hub.download_state(repo_id) or {}
    if state.get("status") == "ready":
        path = hf_hub.resolve_local(repo_id)
        print(f"  tersimpan: {path}")
        deps = dependencies()
        if not deps["available"]:
            print("\n  [ !! ] PyTorch/transformers belum ter-install — inference "
                  "lokal belum bisa jalan.\n"
                  "         python run.py --install-local")
        print(f"MODEL_DIR={path}")
        return 0
    print(f"  gagal: {state.get('error')}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo_id", nargs="?", default="",
                    help="repo HuggingFace, mis. Qwen/Qwen3-1.7B")
    ap.add_argument("--search", "-s", default="", help="cari model di HuggingFace")
    ap.add_argument("--list", "-l", action="store_true",
                    help="tampilkan model yang sudah terunduh")
    args = ap.parse_args()

    os.environ.setdefault("ASK_MODELS_DIR",
                          str(Path(__file__).resolve().parents[1] / "models"))

    if args.search:
        return asyncio.run(search(args.search))
    if args.list:
        return list_local()
    if args.repo_id:
        return asyncio.run(download(args.repo_id))
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
