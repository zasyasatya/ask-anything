#!/usr/bin/env python3
"""Download (or list) offline catalog models — the CLI behind `run.py`.

Reuses the exact same downloader the web UI calls (`app.hf_models`), so the
GGUF lands in the project's `models/` folder either way. Prints progress while
downloading and, on success, a final `GGUF_PATH=<abs path>` line that
`run.py --offline-model` parses to start `llama-server`.

    python scripts/download_model.py --list
    python scripts/download_model.py qwen3-4b-instruct-2507-q4_k_m
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import hf_models  # noqa: E402


def print_catalog() -> None:
    print("Model offline untuk laptop 8 GB (GGUF → folder ./models):")
    print(f"{'id':36} {'quant':8} {'size':>9} {'RAM':10} thinking")
    for m in hf_models.CATALOG:
        print(f"{m.id:36} {m.quant:8} {m.size_bytes / 1024**3:8.2f}G "
              f"{m.ram:10} {'ya' if m.thinking else '-'}"
              f"{'  ← rekomendasi' if m.recommended else ''}")


async def download(model_id: str) -> int:
    try:
        hf_models.start_download(model_id)
    except KeyError:
        print(f"model tidak dikenal: {model_id} (lihat --list)")
        return 2

    last = -10.0
    while True:
        state = hf_models.download_state(model_id) or {}
        if state.get("status") == "downloading":
            import time
            now = time.time()
            if now - last >= 1.0:
                last = now
                print(f"  … {state.get('percent', 0):5.1f}%  "
                      f"{state.get('downloaded', 0) / 1024**2:8.1f} MiB / "
                      f"{state.get('total', 0) / 1024**2:.1f} MiB  "
                      f"{state.get('speed_bps', 0) / 1024**2:.1f} MiB/s")
            await asyncio.sleep(0.25)
            continue
        break

    state = hf_models.download_state(model_id) or {}
    if state.get("status") == "ready":
        path = hf_models.resolve_local(model_id)
        print(f"  tersimpan: {path}")
        print(f"GGUF_PATH={path}")
        return 0
    print(f"  gagal: {state.get('error')}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("model_id", nargs="?", default="")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list or not args.model_id:
        print_catalog()
        return 0
    return asyncio.run(download(args.model_id))


if __name__ == "__main__":
    raise SystemExit(main())
