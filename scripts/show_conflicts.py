"""Cetak setiap hunk konflik merge beserta konteksnya (helper sekali pakai)."""
from __future__ import annotations

import sys


def main(paths: list[str], ctx: int = 5) -> None:
    for path in paths:
        lines = open(path, encoding="utf-8").read().split("\n")
        i = 0
        while i < len(lines):
            if lines[i].startswith("<<<<<<< "):
                j = i
                while j < len(lines) and not lines[j].startswith(">>>>>>> "):
                    j += 1
                lo, hi = max(0, i - ctx), min(len(lines), j + ctx + 1)
                print(f"===== {path}  [{i + 1}..{j + 1}] =====")
                for n in range(lo, hi):
                    print(f"{n + 1:5d}| {lines[n]}")
                print()
                i = j
            i += 1


if __name__ == "__main__":
    main(sys.argv[1:])
