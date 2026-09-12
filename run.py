#!/usr/bin/env python3
"""Ask Anything — one-command launcher (backend + frontend + optional local LLM).

Checks every dependency (python, node, npm, pip packages, node modules),
installs what is missing, then starts everything and health-checks it.

Examples:
    python run.py                      # huggingface default; uses llama-server on :8081 if reachable
    python run.py --demo               # no GPU needed: emulated local HF server (fake_llama_server)
    python run.py --provider openai    # use OpenAI API (set ASK_OPENAI_API_KEY first)
    python run.py --gguf model.gguf    # start llama-server with a GGUF from the HF Hub
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
IS_WIN = os.name == "nt"


def venv_python() -> Path:
    return ROOT / ".venv" / ("Scripts" if IS_WIN else "bin") / (
        "python.exe" if IS_WIN else "python")


def ok(msg: str) -> None:
    print(f"  [ OK ] {msg}")


def warn(msg: str) -> None:
    print(f"  [ !! ] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    sys.exit(1)


def url_alive(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 500
    except Exception:
        return False


def wait_url(url: str, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if url_alive(url):
            return True
        time.sleep(1)
    return False


def check_core_deps() -> None:
    print("== Checking core dependencies ==")
    if sys.version_info < (3, 10):
        fail(f"Python >= 3.10 required (found {sys.version.split()[0]})")
    ok(f"python {sys.version.split()[0]}")

    node = shutil.which("node")
    if not node:
        fail("Node.js not found — install https://nodejs.org (>= 18) and re-run")
    node_v = subprocess.run([node, "--version"], capture_output=True, text=True)
    ok(f"node {node_v.stdout.strip()}")

    npm = shutil.which("npm")
    if not npm:
        fail("npm not found — it ships with Node.js")
    npm_v = subprocess.run([npm, "--version"], capture_output=True, text=True)
    ok(f"npm {npm_v.stdout.strip()}")


def ensure_backend_deps() -> Path:
    print("== Backend (FastAPI) ==")
    py = venv_python()
    if not py.exists():
        print("  creating virtualenv …")
        subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")],
                       check=True)
    probe = subprocess.run(
        [str(py), "-c", "import fastapi, uvicorn, httpx, bs4"],
        capture_output=True)
    if probe.returncode != 0:
        print("  installing backend requirements …")
        subprocess.run(
            [str(py), "-m", "pip", "install", "-r",
             str(BACKEND / "requirements.txt")],
            check=True)
    ok("backend dependencies available (fastapi/uvicorn/httpx/bs4)")
    return py


def ensure_frontend_deps() -> None:
    print("== Frontend (Next.js) ==")
    if not (FRONTEND / "node_modules").exists():
        print("  npm install (first run can take a minute) …")
        subprocess.run(["npm", "install"], cwd=FRONTEND, check=True,
                       shell=IS_WIN)
    if not (FRONTEND / "node_modules" / "next").exists():
        fail("frontend dependencies missing even after npm install")
    ok("frontend dependencies available (next/react/mermaid/tailwind)")


def start(proc_name: str, cmd: list[str], cwd: Path, env: dict) -> subprocess.Popen:
    log = open(ROOT / "data" / f"{proc_name}.log", "w")
    command: str | list[str] = " ".join(cmd) if IS_WIN else cmd
    return subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log,
                            shell=IS_WIN)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--provider", choices=["huggingface", "openai", "mock"],
                    default=os.environ.get("ASK_PROVIDER", "huggingface"))
    ap.add_argument("--backend-port", type=int, default=8000)
    ap.add_argument("--frontend-port", type=int, default=3000)
    ap.add_argument("--llm-port", type=int, default=8081)
    ap.add_argument("--demo", action="store_true",
                    help="run the emulated local HF server (no GPU/GGUF needed)")
    ap.add_argument("--gguf", type=str, default="",
                    help="path to a GGUF file; starts llama-server if installed")
    ap.add_argument("--offline-model", type=str, default="",
                    help="id model offline dari katalog: diunduh ke ./models "
                         "lalu dijalankan dengan llama-server "
                         "(lihat --list-offline-models)")
    ap.add_argument("--list-offline-models", action="store_true",
                    help="tampilkan katalog model offline untuk laptop 8 GB")
    ap.add_argument("--no-thinking", action="store_true",
                    help="matikan reasoning (<think>) pada model lokal")
    ap.add_argument("--skip-frontend", action="store_true")
    ap.add_argument("--install-only", action="store_true")
    args = ap.parse_args()

    (ROOT / "data").mkdir(exist_ok=True)

    check_core_deps()
    py = ensure_backend_deps()
    if args.list_offline_models:
        # katalog berasal dari app.hf_models → butuh interpreter backend (.venv)
        subprocess.run([str(py), str(ROOT / "scripts" / "download_model.py"),
                        "--list"], cwd=ROOT)
        return
    ensure_frontend_deps()
    if args.install_only:
        print("All dependencies installed. Re-run without --install-only.")
        return

    # ---- offline catalog model: download into ./models, then serve it ----
    if args.offline_model:
        print(f"== Model offline: {args.offline_model} ==")
        proc = subprocess.run(
            [str(py), str(ROOT / "scripts" / "download_model.py"),
             args.offline_model], cwd=ROOT, capture_output=True, text=True)
        sys.stdout.write(proc.stdout)
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr)
            fail(f"download model gagal (code {proc.returncode})")
        gguf = ""
        for line in proc.stdout.splitlines():
            if line.startswith("GGUF_PATH="):
                gguf = line.split("=", 1)[1]
        if not gguf or not Path(gguf).is_file():
            fail("GGUF tidak ditemukan setelah download")
        args.gguf = gguf
        if not shutil.which("llama-server"):
            warn("GGUF sudah tersimpan, tetapi `llama-server` belum ter-install "
                 "— pasang llama.cpp lalu jalankan:\n"
                 f"         llama-server -m {gguf} --host 0.0.0.0 "
                 f"--port {args.llm_port} --jinja -c 4096")
        ok(f"model siap di {gguf}")

    env = os.environ.copy()
    env["ASK_PROVIDER"] = args.provider
    env["ASK_DB_PATH"] = str(ROOT / "data" / "ask_anything.db")
    env["ASK_MODELS_DIR"] = str(ROOT / "models")
    if args.no_thinking:
        env["ASK_THINKING"] = "0"
    env["BACKEND_URL"] = f"http://127.0.0.1:{args.backend_port}"

    procs: list[tuple[str, subprocess.Popen]] = []
    try:
        # ---- optional local LLM server ----
        llm_url = f"http://127.0.0.1:{args.llm_port}/v1"
        if args.provider == "huggingface":
            if url_alive(f"{llm_url}/models"):
                ok(f"local HF LLM server already reachable at {llm_url}")
            elif args.gguf and shutil.which("llama-server"):
                print(f"  starting llama-server with {args.gguf} …")
                p = start("llama", ["llama-server", "-m", args.gguf, "--host",
                                    "0.0.0.0", "--port", str(args.llm_port),
                                    "-ngl", "99"], ROOT, env)
                procs.append(("llama-server", p))
            elif args.demo or env.get("ASK_DEMO") == "1":
                print("  --demo: starting emulated local HF server "
                      "(fake_llama_server) …")
                p = start("fakellm", [str(py), str(ROOT / "scripts" /
                          "fake_llama_server.py")], ROOT, env)
                procs.append(("fake-llama", p))
                if not wait_url(f"{llm_url}/models", 20):
                    fail("emulated LLM server did not come up; see "
                         "data/fakellm.log")
                ok(f"emulated HF LLM server at {llm_url}")
            else:
                warn(f"no local LLM server at {llm_url}. "
                     "Start `llama-server` (see README) or re-run with --demo. "
                     "Backend will still run; chats will error until then.")

        # ---- backend ----
        print("== Starting backend ==")
        bp = start("backend", [str(py), "-m", "uvicorn", "app.main:app",
                               "--host", "0.0.0.0", "--port",
                               str(args.backend_port)], BACKEND, env)
        procs.append(("backend", bp))
        if not wait_url(f"http://127.0.0.1:{args.backend_port}/api/health", 30):
            fail("backend did not become healthy; see data/backend.log")
        ok(f"backend healthy at http://127.0.0.1:{args.backend_port}")

        # ---- frontend ----
        if not args.skip_frontend:
            print("== Starting frontend ==")
            fp = start("frontend", ["npm", "run", "dev", "--", "-p",
                                    str(args.frontend_port), "-H", "0.0.0.0"],
                       FRONTEND, env)
            procs.append(("frontend", fp))
            if not wait_url(f"http://127.0.0.1:{args.frontend_port}", 120):
                fail("frontend did not come up; see data/frontend.log")
            ok(f"frontend at http://127.0.0.1:{args.frontend_port}")

        print("\n==============================================")
        print("  Ask Anything is running")
        print(f"  UI      : http://127.0.0.1:{args.frontend_port}")
        print(f"  API     : http://127.0.0.1:{args.backend_port}/api/health")
        print(f"  provider: {args.provider}")
        print("  Ctrl+C stops everything.")
        print("==============================================\n")

        while True:
            for name, p in procs:
                if p.poll() is not None:
                    warn(f"{name} exited with code {p.returncode} "
                         f"— see logs in {ROOT / 'data'}")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nshutting down …")
    finally:
        for _, p in procs:
            p.terminate()
        for _, p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
