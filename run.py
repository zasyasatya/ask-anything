#!/usr/bin/env python3
"""Ask Anything — one-command launcher (backend + frontend + model offline).

Checks every dependency (python, node, npm, pip packages, node modules),
installs what is missing, then starts everything and health-checks it.

Examples:
    python run.py                          # provider huggingface, inference lokal
    python run.py --search qwen3           # cari model di HuggingFace
    python run.py --model Qwen/Qwen3-1.7B  # unduh ke ./models + jadikan aktif
    python run.py --install-local          # pasang PyTorch + transformers
    python run.py --demo                   # server OpenAI-compatible tiruan
    python run.py --provider openai        # OpenAI / gateway (ASK_OPENAI_API_KEY)
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
    return ROOT / ".venv" / (
        "Scripts" if IS_WIN else "bin") / ("python.exe" if IS_WIN else "python")


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


#: Smoke test stack inference lokal. Import saja tidak cukup: operasi kecil
#: memastikan DLL torch benar-benar bisa di-*initialize*. Ini menangkap kasus
#: khas Windows — paket ada di pip tapi `import torch` jatuh dengan
#: `OSError: [WinError 1114] A dynamic link library (DLL) initialization
#: routine failed. Error loading ...torch\lib\c10.dll` (instalasi rusak /
#: setengah jadi, build campuran, file korup, atau VC++ Runtime hilang).
LOCAL_PROBE_CODE = (
    "import torch, transformers\n"
    "_ = torch.randn(2, 2).sum()\n"
    "print(torch.__version__ + ' / ' + transformers.__version__)\n"
)


def probe_local_stack(py: Path) -> subprocess.CompletedProcess:
    """Jalankan smoke test torch + transformers; inspeksi hasil via returncode."""
    return subprocess.run([str(py), "-c", LOCAL_PROBE_CODE],
                          capture_output=True, text=True)


def _last_error(proc: subprocess.CompletedProcess) -> str:
    for line in reversed((proc.stderr or proc.stdout or "").strip()
                         .splitlines()):
        line = line.strip()
        if line:
            return line[:300]
    return "error tidak dikenal"


def _torch_broken_help(py: Path, last_err: str) -> str:
    """Panduan manual bila torch rusak dan pasang ulang otomatis tak berkesudahan."""
    return (
        "torch ada di pip tapi rusak, dan pasang ulang otomatis tidak "
        "membuahkan hasil.\n"
        f"  Error terakhir: {last_err}\n\n"
        "Coba manual, berurutan:\n"
        "  1. Pasang Visual C++ Redistributable 2015-2022 (x64) bila belum ada:\n"
        "     https://aka.ms/vs/17/release/vc_redist.x64.exe\n"
        "  2. Matikan sementara antivirus / OneDrive yang memindai folder proyek,\n"
        "     lalu pasang ulang PyTorch CPU:\n"
        f"     {py} -m pip uninstall -y torch torchvision torchaudio\n"
        f"     {py} -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch\n"
        f"  3. Uji: {py} -c \"import torch; print(torch.__version__)\"\n"
        "  4. Masih gagal? Buat venv baru: hapus folder .venv, lalu jalankan lagi:\n"
        "     python run.py --install-local\n\n"
        "Sementara itu app tetap bisa jalan:  python run.py --demo  "
        "atau  python run.py --provider openai"
    )


def _clean_reinstall_torch(py: Path) -> None:
    """Pasang ulang bersih PyTorch dari CPU wheels (instalasi terdeteksi rusak)."""
    print("  torch ter-install di pip tapi tidak bisa dijalankan — "
          "pasang ulang bersih (CPU wheels, tanpa cache) …")
    subprocess.run([str(py), "-m", "pip", "uninstall", "-y",
                    "torch", "torchvision", "torchaudio"], check=False)
    subprocess.run([str(py), "-m", "pip", "install", "--no-cache-dir",
                    "--index-url", "https://download.pytorch.org/whl/cpu",
                    "torch"], check=False)
    subprocess.run([str(py), "-m", "pip", "install", "--no-cache-dir",
                    "-r", str(BACKEND / "requirements-local.txt")],
                   check=False)


def install_local_stack(py: Path) -> bool:
    """PyTorch + transformers: hanya dibutuhkan untuk inference model lokal.

    Kembalikan True bila torch benar-benar *bisa dijalankan* (bukan sekadar
    ada di pip). Urutan: probe → install biasa (bila belum ada) → pasang
    ulang bersih CPU wheels (bila ada tapi rusak) → panduan manual.
    """
    print("== Local inference stack (torch + transformers) ==")
    probe = probe_local_stack(py)
    if probe.returncode == 0:
        ok(f"torch/transformers siap ({probe.stdout.strip()})")
        return True

    err = _last_error(probe)
    torch_present = subprocess.run(
        [str(py), "-m", "pip", "show", "torch"],
        capture_output=True).returncode == 0

    if not torch_present:
        print(f"  (belum ter-install; detail: {err})")
        print("  installing backend/requirements-local.txt (±1–2 GB, bisa lama) …")
        subprocess.run([str(py), "-m", "pip", "install", "-r",
                        str(BACKEND / "requirements-local.txt")], check=True)
        probe = probe_local_stack(py)
        if probe.returncode == 0:
            ok(f"torch/transformers siap ({probe.stdout.strip()})")
            return True
        err = _last_error(probe)

    print(f"  (ter-install tapi rusak; detail: {err})")
    _clean_reinstall_torch(py)
    probe = probe_local_stack(py)
    if probe.returncode == 0:
        ok(f"torch/transformers siap setelah pasang ulang "
           f"({probe.stdout.strip()})")
        return True

    fail(_torch_broken_help(py, _last_error(probe)))
    return False  # tak tercapai: fail() di atas keluar lebih dulu


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


def model_cli(py: Path, args: list[str], capture: bool = False
              ) -> subprocess.CompletedProcess:
    return subprocess.run([str(py), str(ROOT / "scripts" / "download_model.py"),
                           *args], cwd=ROOT, capture_output=capture,
                          text=capture)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=["huggingface", "openai", "mock"],
                    default=os.environ.get("ASK_PROVIDER", "huggingface"))
    ap.add_argument("--hf-mode", choices=["local", "server"], default="local",
                    help="local = inference di proses backend (transformers); "
                         "server = URL OpenAI-compatible")
    ap.add_argument("--backend-port", type=int, default=8000)
    ap.add_argument("--frontend-port", type=int, default=3000)
    ap.add_argument("--llm-port", type=int, default=8081,
                    help="port server OpenAI-compatible untuk --demo")
    ap.add_argument("--demo", action="store_true",
                    help="jalankan server OpenAI-compatible tiruan "
                         "(scripts/fake_llama_server.py) lalu pakai hf_mode=server")
    ap.add_argument("--model", type=str, default="",
                    help="repo HuggingFace, mis. Qwen/Qwen3-1.7B — diunduh ke "
                         "./models lalu dijadikan model aktif")
    ap.add_argument("--search", type=str, default="",
                    help="cari model di HuggingFace lalu keluar")
    ap.add_argument("--list-models", action="store_true",
                    help="tampilkan model yang sudah terunduh di ./models")
    ap.add_argument("--install-local", action="store_true",
                    help="install PyTorch + transformers (butuh untuk model "
                         "lokal); memverifikasi torch benar-benar bisa dijalankan "
                         "dan memperbaiki otomatis bila instalasinya rusak")
    ap.add_argument("--no-thinking", action="store_true",
                    help="matikan reasoning (<think>) pada model lokal")
    ap.add_argument("--skip-frontend", action="store_true")
    ap.add_argument("--install-only", action="store_true")
    args = ap.parse_args()

    (ROOT / "data").mkdir(exist_ok=True)

    check_core_deps()
    py = ensure_backend_deps()

    # ---- CLI model offline (tidak menjalankan server) ----
    if args.search:
        raise SystemExit(model_cli(py, ["--search", args.search]).returncode)
    if args.list_models:
        raise SystemExit(model_cli(py, ["--list"]).returncode)
    if args.install_local:
        install_local_stack(py)
        if args.install_only:
            return

    ensure_frontend_deps()
    if args.install_only:
        print("All dependencies installed. Re-run without --install-only.")
        return

    # ---- model offline: unduh ke ./models, jadikan aktif ----
    hf_mode = args.hf_mode
    if args.model:
        print(f"== Model offline: {args.model} ==")
        proc = model_cli(py, [args.model], capture=True)
        sys.stdout.write(proc.stdout)
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr or "")
            fail(f"download model gagal (code {proc.returncode})")
        model_dir = ""
        for line in proc.stdout.splitlines():
            if line.startswith("MODEL_DIR="):
                model_dir = line.split("=", 1)[1]
        if not model_dir or not Path(model_dir).is_dir():
            fail("folder model tidak ditemukan setelah download")
        install_local_stack(py)      # inference lokal butuh torch
        hf_mode = "local"
        ok(f"model siap di {model_dir}")

    env = os.environ.copy()
    env["ASK_PROVIDER"] = args.provider
    env["ASK_DB_PATH"] = str(ROOT / "data" / "ask_anything.db")
    env["ASK_MODELS_DIR"] = str(ROOT / "models")
    env["ASK_HF_MODE"] = "server" if args.demo else hf_mode
    if args.model:
        env["ASK_HF_MODEL"] = args.model
    if args.no_thinking:
        env["ASK_THINKING"] = "0"
    env["BACKEND_URL"] = f"http://127.0.0.1:{args.backend_port}"

    procs: list[tuple[str, subprocess.Popen]] = []
    try:
        # ---- server OpenAI-compatible (hanya untuk --demo / hf_mode=server) ----
        if args.demo:
            llm_url = f"http://127.0.0.1:{args.llm_port}/v1"
            env["ASK_HF_BASE_URL"] = llm_url
            env["ASK_HF_MODEL"] = "fake-local-model"
            if url_alive(f"{llm_url}/models"):
                ok(f"server OpenAI-compatible sudah hidup di {llm_url}")
            else:
                print("  --demo: menjalankan server tiruan (fake_llama_server) …")
                p = start("fakellm", [str(py), str(ROOT / "scripts" /
                                                   "fake_llama_server.py")],
                          ROOT, env)
                procs.append(("fake-server", p))
                if not wait_url(f"{llm_url}/models", 20):
                    fail("server tiruan tidak hidup; lihat data/fakellm.log")
                ok(f"server tiruan di {llm_url}")
        elif args.provider == "huggingface" and hf_mode == "local":
            probe = probe_local_stack(py)
            if probe.returncode != 0:
                warn("PyTorch/transformers belum siap — model lokal belum bisa "
                     "dijalankan.\n"
                     f"         {_last_error(probe)}\n"
                     "         Perbaiki: python run.py --install-local\n"
                     "         (mendeteksi torch rusak & pasang ulang otomatis)\n"
                     "         (atau pakai --provider openai / --demo)")

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
        print(f"  provider: {args.provider}"
              + (f" ({'server' if args.demo else hf_mode})"
                 if args.provider == "huggingface" else ""))
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
