#!/usr/bin/env python3
"""Capture screenshot dokumentasi dari aplikasi yang SEDANG BERJALAN.

Semua gambar di `docs/images/` dihasilkan oleh script ini — bukan mockup —
dengan cara men-drive UI asli (Next.js + FastAPI) lewat Playwright/Chromium.

Prasyarat
---------
1. Backend & frontend jalan (mis. `python3 run.py --demo` atau manual):
       ASK_PROVIDER=mock python -m uvicorn backend.app.main:app --port 8000
       cd frontend && npx next dev -p 3000
2. Playwright ter-install:  pip install playwright brotli
   lalu salah satu dari:
     - `playwright install chromium`  (bila jaringan mengizinkan), atau
     - set env CHROME_EXE ke binary Chromium apa pun (mis. hasil ekstrak
       paket npm @sparticuz/chromium untuk lingkungan tanpa akses CDN),
       opsional CHROME_LIBS (LD_LIBRARY_PATH tambahan) dan CHROME_FONTS
       (FONTCONFIG_FILE / dir fontconfig). Tanpa FONTCONFIG_FILE yang benar,
       teks pada tangkapan layar hilang sama sekali.

Pemakaian
---------
    BASE_URL=http://127.0.0.1:3000 python3 scripts/capture_screenshots.py main
    python3 scripts/capture_screenshots.py pages      # halaman /panduan & /developer

Stage `main`  : seluruh flow UI (hero, navbar collapse, chat + sitasi, kanvas
                fullscreen, interpreter log/LLM/sumber, settings, riwayat)
Stage `pages` : screenshot halaman dokumentasi in-app (jalan setelah stage main,
                karena halaman tersebut menampilkan gambar hasil stage main)

Catatan kejujuran data: alur "browser" memakai gateway pencarian demo lokal
(`scripts/fake_search_server.py`, via ASK_SEARCH_DDG_URL) supaya pipeline
sitasi bisa difoto end-to-end di lingkungan tanpa internet. Kontennya fiktif;
caption di dokumentasi mengatakannya. Tanpa gateway itu, tool browser memang
menghasilkan 0 dan UI menampilkannya sebagai status, bukan gelembung kosong.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "images"
BASE = os.environ.get("BASE_URL", "http://127.0.0.1:3000")
API = os.environ.get("API_URL", "http://127.0.0.1:8000")
#: gateway pencarian demo (lihat docstring). Kosongkan untuk mencoba internet asli.
SEARCH_DEMO = os.environ.get("SEARCH_DEMO_URL", "http://127.0.0.1:8099/lite/")

CHROME_EXE = os.environ.get("CHROME_EXE")
CHROME_LIBS = os.environ.get("CHROME_LIBS")
CHROME_FONTS = os.environ.get("CHROME_FONTS")

ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--no-zygote",
    "--disable-dev-shm-usage",
    "--font-render-hinting=none",
    "--hide-scrollbars",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
]

VIEWPORT = {"width": 1440, "height": 900}
WIDE = {"width": 1680, "height": 950}
MOBILE = {"width": 390, "height": 844}


def browser_kwargs() -> dict:
    """Launch options for Playwright.

    Untuk Chromium hasil ekstrak `@sparticuz/chromium` (binary + `lib/` +
    `fonts.conf` dalam satu folder), cukup set CHROME_EXE — lib dan fontconfig
    dicari di sampingnya. Tanpa `lib/` di LD_LIBRARY_PATH binary gagal load
    (mis. `libnspr4.so: cannot open shared object file`); tanpa FONTCONFIG_FILE
    yang benar, screenshot ter-render tapi teksnya hilang.
    """
    kw: dict = {"args": ARGS, "timeout": 90_000}
    env = dict(os.environ)
    exe = Path(CHROME_EXE) if CHROME_EXE else None
    if exe:
        kw["executable_path"] = str(exe)
        side_lib = exe.parent / "lib"
        side_conf = exe.parent / "fonts.conf"
        if side_lib.is_dir():
            env["LD_LIBRARY_PATH"] = (
                str(side_lib) + ":" + env.get("LD_LIBRARY_PATH", "")
            ).rstrip(":")
        if side_conf.is_file():
            env.setdefault("FONTCONFIG_FILE", str(side_conf))
            env.setdefault("FONTCONFIG_PATH", str(exe.parent))
    if CHROME_LIBS:
        env["LD_LIBRARY_PATH"] = CHROME_LIBS + ":" + env.get("LD_LIBRARY_PATH", "")
    if CHROME_FONTS:
        env["FONTCONFIG_FILE"] = CHROME_FONTS
    kw["env"] = env
    return kw


class Shots:
    def __init__(self, page):
        self.page = page
        self.n = 0

    def save(self, name: str, **kw) -> Path:
        path = OUT / f"{name}.png"
        self.page.screenshot(path=str(path), **kw)
        print(f"  ✔ {path.relative_to(REPO)}")
        return path

    def element(self, locator, name: str) -> Path:
        path = OUT / f"{name}.png"
        locator.screenshot(path=str(path))
        print(f"  ✔ {path.relative_to(REPO)} (element)")
        return path


def wait_idle(page, timeout: int = 90_000) -> None:
    """Tunggu sampai stream agent selesai (tombol 'Thinking…' hilang)."""
    page.wait_for_selector('button:has-text("Thinking…")', state="detached", timeout=timeout)
    page.wait_for_timeout(700)


def send_prompt(page, text: str) -> None:
    ta = page.locator("textarea").first
    ta.fill(text)
    ta.press("Enter")
    wait_idle(page)


def set_settings(update: dict) -> None:
    import json
    import urllib.request

    req = urllib.request.Request(
        f"{API}/api/settings",
        data=json.dumps(update).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=15).read()


def new_chat(page) -> None:
    page.click('button:has-text("New chat")')
    page.wait_for_timeout(350)


def close_interpreter(page) -> None:
    if page.locator('[data-testid="interpreter"]').count():
        page.click('header button:has-text("Mechanistic Interpreter")')
        page.wait_for_selector('[data-testid="interpreter"]', state="detached")
        page.wait_for_timeout(350)


def open_interpreter(page) -> None:
    if not page.locator('[data-testid="interpreter"]').count():
        page.click('header button:has-text("Mechanistic Interpreter")')
        page.wait_for_selector('[data-testid="interpreter"]')
        page.wait_for_timeout(400)


def stage_main(page: "Shots") -> None:
    p = page.page
    OUT.mkdir(parents=True, exist_ok=True)

    print("[1] Hero / landing")
    p.goto(BASE, wait_until="networkidle")
    p.wait_for_selector('h1:has-text("Ask Anything,")')
    p.wait_for_timeout(500)
    page.save("01-hero-landing")

    print("[2] Explore cards (scroll)")
    p.evaluate("document.querySelector('.grid-bg')?.scrollTo(0, 99999)")
    p.wait_for_timeout(400)
    page.save("02-hero-explore")
    p.evaluate("document.querySelector('.grid-bg')?.scrollTo(0, 0)")

    print("[3] Navbar collapsed → expand")
    p.click('[data-testid="sidebar-toggle"]')
    p.wait_for_selector('[data-testid="sidebar"][data-collapsed="true"]')
    p.wait_for_timeout(450)
    page.save("19-sidebar-collapsed")
    page.element(p.locator('[data-testid="sidebar"]'), "13-sidebar-history")
    p.click('[data-testid="sidebar-toggle"]')
    p.wait_for_selector('[data-testid="sidebar"][data-collapsed="false"]')
    p.wait_for_timeout(400)

    print("[4] Banner troubleshooting (provider huggingface, model belum dimuat)")
    saved_provider = "mock"
    set_settings({"provider": "huggingface"})
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(1400)
    if p.locator("text=Belum ada model offline yang dimuat").count():
        page.save("12-banner-llm-offline")
    set_settings({"provider": saved_provider})
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(900)

    print("[5] Composer terisi via chip")
    p.click('button:has-text("Diagram alir →")')
    p.wait_for_timeout(300)
    page.save("03-composer-filled")

    print("[6] Diagram → kanvas graph lebar + provenance + interpreter")
    if SEARCH_DEMO:
        set_settings({"search_ddg_url": SEARCH_DEMO})
    p.locator("textarea").first.press("Enter")
    p.wait_for_selector('[data-testid="graph-canvas"]', timeout=60_000)
    wait_idle(p)
    p.wait_for_timeout(600)
    page.save("04-chat-diagram-interpreter")
    page.element(p.locator('[data-testid="diagram-card"]').first, "20-canvas-diagram")

    print("[7] Kanvas layar penuh")
    p.click('[data-testid="diagram-fullscreen"]')
    p.wait_for_selector('[data-testid="diagram-card"][data-fullscreen="true"]')
    p.wait_for_timeout(800)
    page.save("21-canvas-fullscreen")
    p.keyboard.press("Escape")
    p.wait_for_selector('[data-testid="diagram-card"][data-fullscreen="false"]')
    p.wait_for_timeout(400)

    print("[8] Interpreter: tab Log (eksekusi tool)")
    open_interpreter(p)
    page.save("22-interpreter-log")
    # satu baris dibuka supaya payload mentah terlihat
    row = p.locator('[data-testid^="log-row-"]').nth(4)
    if row.count():
        row.click()
        p.wait_for_timeout(300)
    page.save("05-interpreter-timeline-expanded")

    print("[9] Interpreter: LLM (blackbox) / Sumber / Metrik")
    for tab, name in [("LLM", "06-interpreter-prompt"),
                      ("Sumber", "23-interpreter-sources"),
                      ("Metrik", "08-interpreter-metrics")]:
        p.locator(f'[data-testid="interpreter"] button:has-text("{tab}")').first.click()
        p.wait_for_timeout(400)
        page.save(name)
    p.locator('[data-testid="interpreter"] button:has-text("Tools")').first.click()
    p.wait_for_timeout(350)
    page.save("07-interpreter-tokens")

    print("[10] Browsing: hasil + sitasi (gateway demo lokal)")
    new_chat(p)
    close_interpreter(p)
    send_prompt(p, "Cari berita teknologi terkini minggu ini, rangkum 3 teratas lengkap dengan link sumber.")
    page.save("24-chat-browsing-cited")
    if p.locator('[data-testid="citation-bar"]').count():
        page.element(p.locator('[data-testid="citation-bar"]').first, "25-citation-bar")
    if p.locator('[data-testid="tool-chip-web_search"]').count():
        page.element(p.locator("main").first, "26-tool-badges")

    print("[11] Interpreter pada run bersitasi")
    open_interpreter(p)
    p.locator('[data-testid="interpreter"] button:has-text("Sumber")').first.click()
    p.wait_for_timeout(400)
    page.save("23-interpreter-sources")
    close_interpreter(p)

    print("[12] Browsing tanpa hasil (internet diblokir) — status, bukan bubble kosong")
    set_settings({"search_ddg_url": "http://127.0.0.1:9/lite/"})
    new_chat(p)
    send_prompt(p, "Cari berita teknologi terkini minggu ini, rangkum 3 teratas lengkap dengan link sumber.")
    page.save("09-chat-browsing-error")
    if p.locator('[data-testid="tool-chip-web_search"]').count():
        page.element(p.locator('[data-testid="tool-chip-web_search"]').first, "27-tool-empty-state")
    if SEARCH_DEMO:
        set_settings({"search_ddg_url": SEARCH_DEMO})

    print("[13] Ruang chat lega (lebar penuh) — kalkulator")
    new_chat(p)
    send_prompt(p, "Hitung (1250 * 8) / 100 + 2 ** 5 dan jelaskan urutannya.")
    page.save("10-chat-calculator")

    print("[14] Layout lebar: chat + interpreter berdampingan")
    with p.context.browser.new_context(viewport=WIDE, device_scale_factor=2) as ctx:
        w = ctx.new_page()
        w.goto(BASE, wait_until="networkidle")
        new_chat(w)
        send_prompt(w, "Buatkan diagram alir proses registrasi pengguna dengan langkah validasi email.")
        # run yang sudah selesai otomatis membuka interpreter; helper ini
        # idempoten (tidak men-toggle-nya jadi tertutup lagi).
        open_interpreter(w)
        w.wait_for_timeout(500)
        w.screenshot(path=str(OUT / "28-wide-room-plus-interpreter.png"))
        print(f"  ✔ {OUT / '28-wide-room-plus-interpreter.png'}")
        # dan saat navbar di-collapse: ruang makin lega
        w.click('[data-testid="sidebar-toggle"]')
        w.wait_for_timeout(450)
        w.screenshot(path=str(OUT / "29-wide-room-navbar-collapsed.png"))
        print(f"  ✔ {OUT / '29-wide-room-navbar-collapsed.png'}")

    print("[15] Settings provider")
    p.goto(BASE, wait_until="networkidle")
    p.click('button:has-text("Settings provider")')
    p.wait_for_selector('text=Provider')
    p.wait_for_timeout(400)
    page.save("11-settings-provider")
    p.click('button:has-text("Cancel")')
    p.wait_for_timeout(300)

    print("[16] Sidebar riwayat (expanded)")
    page.element(p.locator('[data-testid="sidebar"]'), "13-sidebar-history")

    print("[17] Slides cara kerja")
    p.goto(f"{BASE}/slides/slides-cara-kerja.html", wait_until="networkidle")
    p.wait_for_timeout(1500)
    page.save("14-slides-cara-kerja")

    print("[18] Aksen warna")
    p.goto(BASE, wait_until="networkidle")
    new_chat(p)
    p.click('button[title="orange"]')
    p.wait_for_timeout(300)
    page.save("16-accent-orange")
    p.click('button[title="indigo"]')

    print("[19] Mobile viewport")
    with p.context.browser.new_context(viewport=MOBILE, device_scale_factor=2) as ctx:
        m = ctx.new_page()
        m.goto(BASE, wait_until="networkidle")
        m.wait_for_timeout(600)
        m.screenshot(path=str(OUT / "15-mobile-hero.png"))
        print(f"  ✔ {OUT / '15-mobile-hero.png'}")


def stage_pages(page: "Shots") -> None:
    p = page.page
    for route, name in [("/panduan", "17-halaman-panduan"),
                        ("/developer", "18-halaman-developer")]:
        print(f"[pages] {route}")
        p.goto(BASE + route, wait_until="networkidle")
        p.wait_for_timeout(800)
        # show the first embedded screenshot so the shot represents the page
        p.locator("figure").first.scroll_into_view_if_needed()
        p.wait_for_timeout(400)
        # viewport-only: full-page would embed every screenshot again (multi-MB)
        page.save(name)


def main() -> int:
    stage = sys.argv[1] if len(sys.argv) > 1 else "main"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**browser_kwargs())
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
        ctx.set_default_timeout(30_000)
        page = ctx.new_page()
        shots = Shots(page)
        if stage == "main":
            stage_main(shots)
        elif stage == "pages":
            stage_pages(shots)
        else:
            print(f"stage tidak dikenal: {stage}")
            return 2
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
