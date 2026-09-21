"""Resolusi konflik merge "ambil keduanya", aman UTF-8.

Di Windows, menulis ulang berkas dengan `Set-Content` PowerShell 5.1 merusak
karakter non-ASCII (ANSI in, UTF-8 out → mojibake + BOM). Skrip ini membaca dan
menulis eksplisit sebagai UTF-8 tanpa BOM, dan tidak menyentuh akhir baris.

Pemakaian:
    python scripts/resolve_keep_both.py <file> [<file> ...]

Tiap hunk `<<<<<<< / ======= / >>>>>>>` menjadi: sisi HEAD, lalu `joiner`
(argumen `--joiner`, default satu baris kosong), lalu sisi remote. Hunk yang
butuh perlakuan khusus diurus manual — skrip hanya untuk kasus "dua blok
independen yang keduanya harus ada".
"""
from __future__ import annotations

import argparse


def resolve(text: str, joiner: list[str]) -> tuple[str, int]:
    lines = text.split("\n")
    out: list[str] = []
    hunks = 0
    i = 0
    while i < len(lines):
        if lines[i].startswith("<<<<<<< "):
            hunks += 1
            i += 1
            ours: list[str] = []
            while not lines[i].startswith("======="):
                ours.append(lines[i])
                i += 1
            i += 1
            theirs: list[str] = []
            while not lines[i].startswith(">>>>>>> "):
                theirs.append(lines[i])
                i += 1
            i += 1
            out.extend(ours)
            out.extend(joiner)
            out.extend(theirs)
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out), hunks


def strip_markers(text: str) -> tuple[str, int]:
    """Buang baris penanda konflik yang tersisa setelah resolusi manual.

    Dipakai bila kedua sisi sudah dirapikan lewat edit biasa sehingga hunk-nya
    tidak lagi berpasangan (`<<<<<<<` tanpa `=======`).
    """
    kept: list[str] = []
    removed = 0
    for line in text.split("\n"):
        if line.startswith(("<<<<<<< ", ">>>>>>> ")) or line == "=======":
            removed += 1
            continue
        kept.append(line)
    return "\n".join(kept), removed


def dominant_newline(text: str) -> str:
    """Akhir baris yang dipakai mayoritas berkas.

    Dengan `core.autocrlf=true` (default Git for Windows) working tree berisi
    CRLF sementara blob-nya LF. Baris yang kita sisipkan harus mengikuti
    berkasnya, bukan platform, supaya tidak muncul akhir baris campur.
    """
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    return "\r\n" if crlf > lf else "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--joiner", default="",
                    help="baris pemisah antar sisi; '\\n' = beberapa baris")
    ap.add_argument("--strip-markers", action="store_true",
                    help="hanya buang penanda sisa (hunk sudah dirapikan manual)")
    ap.add_argument("--normalise-eol", action="store_true",
                    help="samakan akhir baris ke gaya dominan berkas")
    args = ap.parse_args()

    joiner = args.joiner.split("\\n")
    for path in args.files:
        with open(path, encoding="utf-8", newline="") as fh:
            raw = fh.read()
        eol = dominant_newline(raw)
        text = raw.replace("\r\n", "\n")
        if args.strip_markers:
            fixed, n = strip_markers(text)
            note = f"{n} baris penanda dibuang"
        elif args.normalise_eol:
            fixed, n = text, 0
            note = "akhir baris disamakan"
        else:
            fixed, n = resolve(text, joiner)
            note = f"{n} hunk diselesaikan (ambil keduanya)"
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(fixed.replace("\n", eol))
        print(f"{path}: {note}, akhir baris {eol!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
