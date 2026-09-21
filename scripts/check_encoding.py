"""Periksa integritas UTF-8 berkas: BOM, mojibake, dan CRLF campur.

Dipakai setelah resolusi merge di Windows — `Set-Content` PowerShell 5.1
menulis ANSI/UTF-16 dan merusak karakter non-ASCII tanpa error apa pun.
"""
from __future__ import annotations

import sys

# Pola khas UTF-8 yang sudah dibaca ulang sebagai cp1252 ("mojibake").
MOJIBAKE = ("â€”", "â€™", "â€œ", "â€\x9d", "Ã©", "â†’", "ðŸ", "Â·", "â€¢")


def check(path: str) -> list[str]:
    raw = open(path, "rb").read()
    problems: list[str] = []
    if raw.startswith(b"\xef\xbb\xbf"):
        problems.append("ada BOM UTF-8 di awal berkas")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return problems + [f"bukan UTF-8 valid: {exc}"]
    for marker in MOJIBAKE:
        if marker in text:
            line = next(i + 1 for i, l in enumerate(text.split("\n"))
                        if marker in l)
            problems.append(f"mojibake {marker!r} pertama di baris {line}")
    if b"\r\n" in raw and raw.count(b"\r\n") != raw.count(b"\n"):
        problems.append("akhir baris campur CRLF/LF")
    return problems


def main(paths: list[str]) -> int:
    bad = 0
    for path in paths:
        problems = check(path)
        if problems:
            bad += 1
            print(f"FAIL {path}")
            for p in problems:
                print(f"     - {p}")
        else:
            print(f"OK   {path}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
