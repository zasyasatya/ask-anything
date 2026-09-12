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
       (FONTCONFIG_FILE / dir fontconfig).

Pemakaian
---------
    BASE_URL=http://127.0.0.1:3000 python3 scripts/capture_screenshots.py main
    python3 scripts/capture_screenshots.py pages      # halaman /panduan & /developer

Stage `main`  : seluruh flow UI (hero, chat, interpreter, settings, dll.)
Stage `pages` : screenshot halaman dokumentasi in-app (jalan setelah stage main,
                karena halaman tersebut menampilkan gambar hasil stage main).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "images"
BASE = os.environ.get("BASE_URL", "http://127.0.0.1:3000")
API = os.environ.get("API_URL", "http://127.0.0.1:8000")

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
MOBILE = {"width": 390, "height": 844}


def browser_kwargs() -> dict:
    kw: dict = {"args": ARGS, "timeout": 90_000}
    env = dict(os.environ)
    if CHROME_EXE:
        kw["executable_path"] = CHROME_EXE
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

    print("[3] Banner troubleshooting (provider huggingface, LLM offline)")
    set_settings({"hf_base_url": "http://127.0.0.1:9/v1"})
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(1200)
    if p.locator("text=LLM lokal tidak terjangkau").count():
        page.save("12-banner-llm-offline")
    set_settings({"hf_base_url": "http://127.0.0.1:8081/v1"})
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(800)

    print("[4] Composer terisi via chip")
    p.click('button:has-text("Diagram alir →")')
    p.wait_for_timeout(300)
    page.save("03-composer-filled")

    print("[5] Kirim prompt diagram → chat + Mermaid + Interpreter")
    p.locator("textarea").first.press("Enter")
    p.wait_for_selector('main svg[id^="mm-"]', timeout=60_000)
    wait_idle(p)
    p.wait_for_timeout(600)
    page.save("04-chat-diagram-interpreter")

    print("[6] Interpreter: timeline expanded")
    for i in range(2):
        p.locator("aside details summary").nth(i).click()
        p.wait_for_timeout(150)
    page.save("05-interpreter-timeline-expanded")

    print("[7] Interpreter: Prompt / Tokens / Metrics")
    for tab, name in [("Prompt", "06-interpreter-prompt"),
                      ("Tokens", "07-interpreter-tokens"),
                      ("Metrics", "08-interpreter-metrics")]:
        p.locator(f'aside button:has-text("{tab}")').first.click()
        p.wait_for_timeout(350)
        page.save(name)

    print("[8] Browsing (tool error ditangani graceful)")
    p.click('aside button:has-text("New chat")')
    p.wait_for_timeout(400)
    send_prompt(p, "Cari berita teknologi terkini minggu ini, rangkum 3 teratas lengkap dengan link sumber.")
    page.save("09-chat-browsing-error")

    print("[9] Calculator")
    p.click('aside button:has-text("New chat")')
    p.wait_for_timeout(400)
    send_prompt(p, "Hitung (1250 * 8) / 100 + 2 ** 5 dan jelaskan urutannya.")
    page.save("10-chat-calculator")

    print("[10] Settings provider")
    p.click('button:has-text("Settings provider")')
    p.wait_for_selector('text=Provider')
    p.wait_for_timeout(300)
    page.save("11-settings-provider")
    p.click('button:has-text("Cancel")')
    p.wait_for_timeout(300)

    print("[11] Sidebar riwayat")
    p.locator("aside").first.screenshot(path=str(OUT / "13-sidebar-history.png"))
    print(f"  ✔ {OUT / '13-sidebar-history.png'}")

    print("[12] Slides cara kerja")
    p.goto(f"{BASE}/slides/slides-cara-kerja.html", wait_until="networkidle")
    p.wait_for_timeout(1500)
    page.save("14-slides-cara-kerja")

    print("[13] Aksen warna")
    p.goto(BASE, wait_until="networkidle")
    p.click('aside button:has-text("New chat")')
    p.wait_for_timeout(400)
    p.click('button[title="orange"]')
    p.wait_for_timeout(300)
    page.save("16-accent-orange")
    p.click('button[title="indigo"]')

    print("[14] Mobile viewport")
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
