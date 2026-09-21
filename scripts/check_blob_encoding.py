"""Cek encoding blob git apa adanya (byte-level), tanpa lewat shell redirect."""
from __future__ import annotations

import subprocess
import sys

sys.path.insert(0, "scripts")
from check_encoding import MOJIBAKE  # noqa: E402


def main(revs: list[str]) -> None:
    for rev in revs:
        raw = subprocess.run(["git", "show", rev], capture_output=True,
                             check=True).stdout
        bom = raw.startswith(b"\xef\xbb\xbf")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            print(f"{rev}: BUKAN UTF-8 ({exc})")
            continue
        hits = [m for m in MOJIBAKE if m in text]
        print(f"{rev}: utf8=OK bom={bom} mojibake={hits or 'tidak ada'} "
              f"bytes={len(raw)}")


if __name__ == "__main__":
    main(sys.argv[1:])
