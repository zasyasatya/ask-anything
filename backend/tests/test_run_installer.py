"""`run.py --install-local` harus *memverifikasi* torch, bukan sekadar
mem-pip-install — dan memperbaiki otomatis instalasi torch yang rusak
(Windows: `OSError [WinError 1114] … c10.dll`), di mana pip membalas
"Requirement already satisfied" tanpa mengerjakan apa-apa."""
import importlib.util
import subprocess
from pathlib import Path

import pytest

RUN_PY = Path(__file__).resolve().parents[2] / "run.py"
PY = Path("/tmp/fake/.venv/bin/python")

DLL_ERROR = ("OSError: [WinError 1114] A dynamic link library (DLL) "
             "initialization routine failed. Error loading "
             "\"torch\\lib\\c10.dll\" or one of its dependencies.")


def _load_run_module():
    spec = importlib.util.spec_from_file_location("run_launcher", RUN_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeCP:
    def __init__(self, rc, out="", err=""):
        self.returncode = rc
        self.stdout = out
        self.stderr = err


def _make_fake(state):
    def fake_run(cmd, *args, **kwargs):
        calls = state["calls"]
        calls.append(list(cmd))
        if len(cmd) >= 3 and cmd[1] == "-c":          # smoke test probe
            if state["working"]:
                return _FakeCP(0, out="2.14.0+cpu / 5.17.0\n")
            return _FakeCP(1, err=f"{DLL_ERROR}\n")
        if "show" in cmd:                              # pip show torch
            return _FakeCP(0, out="Name: torch\n") \
                if state["torch_present"] else _FakeCP(1)
        if "uninstall" in cmd:
            return _FakeCP(0)
        if "install" in cmd and state["repairable"]:
            state["working"] = True                    # install memperbaiki
        return _FakeCP(0)

    return fake_run


@pytest.fixture()
def fake_pip(monkeypatch):
    """Stateful fake subprocess.run: simulasi torch belum ada / rusak / siap.

    ``repairable=False`` mensimulasikan instalasi yang tak bisa diperbaiki
    (mis. VC++ Runtime hilang) — tiap pip install tetap 'sukses' tapi torch
    tetap tidak bisa dijalankan.
    """
    state = {"working": False, "torch_present": False,
             "repairable": True, "calls": []}
    monkeypatch.setattr(subprocess, "run", _make_fake(state))
    return state


def _cmds(state, *musts):
    """Perintah yang memuat semua `musts` (substring pada string perintah)."""
    return [c for c in state["calls"]
            if all(m in " ".join(str(x) for x in c) for m in musts)]


def test_healthy_torch_no_installs(fake_pip, capsys):
    run = _load_run_module()
    fake_pip["working"] = True
    assert run.install_local_stack(PY) is True
    assert _cmds(fake_pip, "-m") == []               # tanpa satu pun perintah pip
    assert "siap" in capsys.readouterr().out


def test_missing_torch_fresh_install(fake_pip, capsys):
    run = _load_run_module()
    assert run.install_local_stack(PY) is True
    assert _cmds(fake_pip, "uninstall") == []        # tak perlu uninstall
    fresh = _cmds(fake_pip, "install", "requirements-local.txt")
    assert len(fresh) == 1                           # sekali saja
    assert "requirements-local.txt" in str(fresh[0])
    assert "siap" in capsys.readouterr().out


def test_broken_torch_triggers_clean_cpu_reinstall(fake_pip, capsys):
    """Kasus nyata: torch 'already satisfied' di pip tapi c10.dll gagal dimuat."""
    run = _load_run_module()
    fake_pip["torch_present"] = True
    assert run.install_local_stack(PY) is True

    uninst = _cmds(fake_pip, "uninstall")
    assert len(uninst) == 1
    assert {"torch", "torchvision", "torchaudio"} <= set(uninst[0])

    cpu = _cmds(fake_pip, "install", "whl/cpu", "torch")
    assert len(cpu) == 1                             # torch dari CPU wheels
    assert "--no-cache-dir" in cpu[0]
    assert "--index-url" in cpu[0]

    assert len(_cmds(fake_pip, "install", "requirements-local.txt")) == 1
    out = capsys.readouterr().out
    assert "pasang ulang" in out
    assert "siap" in out


def test_unrepairable_torch_fails_with_actionable_help(fake_pip, capsys):
    run = _load_run_module()
    fake_pip["torch_present"] = True
    fake_pip["repairable"] = False

    with pytest.raises(SystemExit) as exc:
        run.install_local_stack(PY)
    assert exc.value.code == 1

    out = capsys.readouterr().out
    assert "WinError 1114" in out          # error asli ditunjukkan
    assert "Visual C++" in out or "vc_redist" in out
    assert "whl/cpu" in out                # perintah manual diberikan
    assert ".venv" in out                  # opsi venv baru disebutkan
