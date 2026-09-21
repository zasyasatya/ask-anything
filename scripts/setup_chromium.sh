#!/usr/bin/env bash
# Siapkan Chromium + font untuk `scripts/capture_screenshots.py` di lingkungan
# yang TIDAK bisa menjangkau cdn.playwright.dev (mis. sandbox/CI tertutup),
# tetapi masih bisa memakai registry npm.
#
# Sumber binary: paket npm @sparticuz/chromium (Chromium headless statis).
# Font diambil dari DejaVu (sistem), Inter (@expo-google-fonts/inter), dan
# Noto Emoji (@fontsource/noto-emoji) — tanpa font yang benar, screenshot
# ter-render tetapi SELURUH TEKSNYA HILANG.
#
# Pemakaian:
#   bash scripts/setup_chromium.sh [TARGET_DIR]     # default: ~/.tooling/chrome
#   source "$TARGET_DIR/env.sh"                     # mengekspor CHROME_EXE dkk
#   python3 scripts/capture_screenshots.py roles
set -euo pipefail

TARGET="${1:-$HOME/.tooling/chrome}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PY="${PYTHON:-python3}"
echo "▸ menyiapkan Chromium di $TARGET"
mkdir -p "$TARGET/allfonts"

# --------------------------------------------------------------- 1. Chromium
echo "▸ unduh @sparticuz/chromium dari registry npm"
(cd "$WORK" && npm pack @sparticuz/chromium >/dev/null 2>&1)
tar xzf "$WORK"/sparticuz-chromium-*.tgz -C "$WORK"

echo "▸ ekstrak binary & pustaka (brotli)"
"$PY" - "$WORK" "$TARGET" <<'PYEOF'
import pathlib, sys
try:
    import brotli
except ModuleNotFoundError:
    sys.exit("butuh modul brotli:  pip install brotli")
work, target = (pathlib.Path(p) for p in sys.argv[1:3])
binf = work / "package" / "bin"
for name in ("chromium", "al2023.tar", "fonts.tar", "swiftshader.tar"):
    src = binf / f"{name}.br"
    if src.exists():
        (target / name).write_bytes(brotli.decompress(src.read_bytes()))
PYEOF

chmod +x "$TARGET/chromium"
mkdir -p "$TARGET/lib"
for t in al2023 swiftshader; do
  [ -f "$TARGET/$t.tar" ] && tar xf "$TARGET/$t.tar" -C "$TARGET/lib"
done
# beberapa arsip membungkus isinya dalam lib/ lagi
if [ -d "$TARGET/lib/lib" ]; then
  mv "$TARGET"/lib/lib/* "$TARGET/lib/" 2>/dev/null || true
  rmdir "$TARGET/lib/lib" 2>/dev/null || true
fi
rm -f "$TARGET"/*.tar

# ------------------------------------------------------------------ 2. Font
echo "▸ kumpulkan font (DejaVu + Inter + Noto Emoji)"
cp /usr/share/fonts/truetype/dejavu/*.ttf "$TARGET/allfonts/" 2>/dev/null || true

(cd "$WORK" && npm pack @expo-google-fonts/inter >/dev/null 2>&1) || true
if ls "$WORK"/expo-google-fonts-inter-*.tgz >/dev/null 2>&1; then
  mkdir -p "$WORK/inter" && tar xzf "$WORK"/expo-google-fonts-inter-*.tgz -C "$WORK/inter"
  for w in 400Regular 500Medium 600SemiBold 700Bold; do
    cp "$WORK/inter/package/$w/"*.ttf "$TARGET/allfonts/" 2>/dev/null || true
  done
fi

# Emoji dipakai di seluruh UI & papan task (👍 👎 ⛔ ⟳) — woff2 dikonversi ke ttf
# karena fontconfig tidak membaca woff2.
(cd "$WORK" && npm pack @fontsource/noto-emoji >/dev/null 2>&1) || true
if ls "$WORK"/fontsource-noto-emoji-*.tgz >/dev/null 2>&1; then
  mkdir -p "$WORK/emoji" && tar xzf "$WORK"/fontsource-noto-emoji-*.tgz -C "$WORK/emoji"
  "$PY" - "$WORK/emoji" "$TARGET/allfonts" <<'PYEOF' || echo "  (lewati emoji: butuh fonttools+brotli)"
import glob, os, pathlib, sys
from fontTools.ttLib import TTFont
src, dst = sys.argv[1], pathlib.Path(sys.argv[2])
for f in sorted(glob.glob(f"{src}/package/files/*-400-normal.woff2")):
    try:
        font = TTFont(f); font.flavor = None
        font.save(dst / (os.path.basename(f).replace(".woff2", ".ttf")))
    except Exception:
        pass
PYEOF
fi

cat > "$TARGET/fonts.conf" <<EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>$TARGET/allfonts</dir>
  <cachedir>$TARGET/fonts-cache</cachedir>
  <match target="pattern">
    <test qual="any" name="family"><string>sans-serif</string></test>
    <edit name="family" mode="prepend" binding="same"><string>Inter</string></edit>
  </match>
</fontconfig>
EOF
mkdir -p "$TARGET/fonts-cache"

cat > "$TARGET/env.sh" <<EOF
export CHROME_EXE="$TARGET/chromium"
export CHROME_LIBS="$TARGET/lib"
export CHROME_FONTS="$TARGET/fonts.conf"
export FONTCONFIG_PATH="$TARGET"
EOF

echo "▸ verifikasi"
LD_LIBRARY_PATH="$TARGET/lib" "$TARGET/chromium" --version
echo "  font: $(ls "$TARGET/allfonts" | wc -l) berkas"
echo
echo "✔ selesai. Jalankan:"
echo "    source $TARGET/env.sh"
echo "    python3 scripts/capture_screenshots.py roles"
