#!/usr/bin/env python3
"""Smoke test UI asli: navbar collapse, ruang chat lebar, kanvas + fullscreen,
badge provenance, sitasi, dan tab Interpreter. Dipakai sebelum & sesudah
perubahan untuk memastikan tidak ada regressi visual/fungsional."""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:3000")
CHROME = os.environ.get("CHROME_EXE", "/tmp/chrome/chromium")

ARGS = [
    "--no-sandbox", "--disable-setuid-sandbox", "--no-zygote",
    "--disable-dev-shm-usage", "--hide-scrollbars",
    "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
]

fails: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"  {'✔' if cond else '✘'} {name}{(' — ' + extra) if extra and not cond else ''}")
    if not cond:
        fails.append(name)


def main() -> int:
    env = dict(os.environ)
    # Chromium lokal (hasil ekstrak @sparticuz/chromium) tidak memakai fontconfig
    # sistem: tanpa dua baris ini teks ter-render nol-karena-glyph-tak-tercari.
    env.setdefault("LD_LIBRARY_PATH", "/tmp/chrome/lib")
    env.setdefault("FONTCONFIG_FILE", "/tmp/chrome/fonts.conf")
    env.setdefault("FONTCONFIG_PATH", "/tmp/chrome")
    with sync_playwright() as pw:
        kw = {"args": ARGS, "timeout": 90_000, "env": env}
        if CHROME and os.path.exists(CHROME):
            kw["executable_path"] = CHROME
        b = pw.chromium.launch(**kw)
        pg = b.new_context(viewport={"width": 1440, "height": 900},
                           device_scale_factor=2).new_page()
        pg.set_default_timeout(30_000)

        print("[1] hero + navbar")
        pg.goto(BASE, wait_until="networkidle")
        pg.wait_for_selector('h1:has-text("Ask Anything,")')
        sidebar = pg.locator('[data-testid="sidebar"]')
        w0 = sidebar.bounding_box()["width"]
        check("navbar expanded 268px", abs(w0 - 268) < 2, f"{w0}px")
        pg.click('[data-testid="sidebar-toggle"]')
        pg.wait_for_timeout(400)
        w1 = sidebar.bounding_box()["width"]
        check("navbar collapsed jadi rail 64px", abs(w1 - 64) < 2, f"{w1}px")
        check("toggle menyiapkan aria-expanded=false",
              sidebar.get_attribute("data-collapsed") == "true")
        pg.click('[data-testid="sidebar-toggle"]')
        pg.wait_for_timeout(400)
        check("expand kembali mengembalikan lebar",
              abs(sidebar.bounding_box()["width"] - w0) < 2)

        print("[2] kirim prompt browsing → provenance + sitasi")
        pg.click('button:has-text("Browsing →")')
        pg.locator("textarea").first.press("Enter")
        pg.wait_for_selector('button:has-text("Thinking…")', state="detached",
                             timeout=60_000)
        pg.wait_for_timeout(800)
        chip = pg.locator('[data-testid="tool-chip-web_search"]')
        check("chip tool menampilkan badge Browser",
              "Browser" in (chip.first.inner_text() if chip.count() else ""),
              chip.first.inner_text() if chip.count() else "chip hilang")
        cbar = pg.locator('[data-testid="citation-bar"]')
        check("bar sitasi tampil", cbar.count() > 0)
        if cbar.count():
            txt = cbar.first.inner_text()
            check("sumber terdaftar & ditandai dikutip",
                  "Sumber Satu" in txt or "dokumentasi demo" in txt, txt[:120])
        check("blok Sumber ada di jawaban",
              pg.locator("text=Sumber").count() > 0)

        print("[3] ruang chat lebih lega")
        wide = pg.locator("div.max-w-\\[1180px\\]")
        check("kontainer chat max-w-[1180px] dipakai", wide.count() > 0)
        check("tidak ada lagi max-w-3xl di chat",
              pg.locator("div.max-w-3xl").count() == 0)

        print("[4] prompt diagram → kanvas + fullscreen + provenance")
        # interpreter memakan ~460px; tutup dulu (lewat toggle header, bukan ✕
        # yang bisaMATCH tombol lain) supaya lebar kolom terukur apa adanya
        if pg.locator('[data-testid="interpreter"]').count():
            pg.click('header button:has-text("Mechanistic Interpreter")')
            pg.wait_for_selector('[data-testid="interpreter"]', state="detached")
            pg.wait_for_timeout(400)
        pg.click('button:has-text("New chat")')
        pg.wait_for_timeout(300)
        pg.click('button:has-text("Diagram alir →")')
        pg.locator("textarea").first.press("Enter")
        pg.wait_for_selector('[data-testid="graph-canvas"]', timeout=60_000)
        pg.wait_for_selector('button:has-text("Thinking…")', state="detached",
                             timeout=60_000)
        pg.wait_for_timeout(700)
        card = pg.locator('[data-testid="diagram-card"]')
        cw = card.bounding_box()["width"]
        colw = pg.evaluate(
            """() => {const el=document.querySelector('[class*="max-w-[1180px]"]');
                     return el? el.getBoundingClientRect().width : 0;}"""
        )
        # kartu harus mengisi kolom teks (dikurangi gutter + avatar logo)
        check("kartu diagram selebar kolom chat", cw > colw - 120,
              f"card {cw:.0f}px vs kolom {colw:.0f}px")
        prov = pg.locator('[data-testid="diagram-provenance"]')
        check("badge provenance diagram tampil", prov.count() > 0,
              prov.first.inner_text() if prov.count() else "")
        if prov.count():
            check("badge menyebut create_diagram",
                  "create_diagram" in prov.first.inner_text(),
                  prov.first.inner_text())

        before = pg.locator('[data-testid="graph-canvas"]').bounding_box()["height"]
        pg.click('[data-testid="diagram-fullscreen"]')
        pg.wait_for_timeout(700)
        after = pg.locator('[data-testid="graph-canvas"]').bounding_box()["height"]
        check("fullscreen/focus mode menambah tinggi kanvas", after > before,
              f"{before} → {after}")
        check("kartu jadi overlay penuh",
              pg.locator('[data-testid="diagram-card"][data-fullscreen="true"]').count() > 0)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(500)
        check("Esc keluar dari layar penuh",
              pg.locator('[data-testid="diagram-card"][data-fullscreen="false"]').count() > 0)

        print("[5] Mechanistic Interpreter")
        if not pg.locator('[data-testid="interpreter"]').count():
            pg.click('button:has-text("Mechanistic Interpreter")')
        pg.wait_for_selector('[data-testid="interpreter"]', timeout=15_000)
        pg.wait_for_timeout(400)
        log = pg.locator('[data-testid="interp-log"]')
        check("tab Log jadi default", log.count() > 0)
        rows = pg.locator('[data-testid^="log-row-"]')
        check("log punya banyak baris terstruktur", rows.count() >= 6,
              f"{rows.count()} rows")
        body = pg.locator('[data-testid="interpreter"]').inner_text()
        check("log memuat nama tool", "web_search" in body or "create_diagram" in body)
        check("log memuat satuan waktu", "t+" in body)
        pg.click('button:has-text("LLM")')
        pg.wait_for_selector('[data-testid="interp-llm"]')
        llm = pg.locator('[data-testid="interp-llm"]').inner_text()
        check("tab LLM membuka request & raw completion",
              "request messages" in llm and "raw completion" in llm, llm[:140])
        pg.click('button:has-text("Sumber")')
        pg.wait_for_selector('[data-testid="interp-sources"]')

        print("[6] collapse saat chat terbuka (Ruang chat ikut meluas)")
        w_chat_open = pg.locator("main").bounding_box()["width"]
        pg.click('[data-testid="sidebar-toggle"]')
        pg.wait_for_timeout(450)
        w_chat_collapsed = pg.locator("main").bounding_box()["width"]
        check("me-collapse navbar memperlebar area chat",
              w_chat_collapsed > w_chat_open,
              f"{w_chat_open} → {w_chat_collapsed}")

        print("[7] halaman docs in-app")
        for route in ("/panduan", "/developer"):
            pg.goto(BASE + route, wait_until="networkidle")
            check(f"{route} terRender", pg.locator("h1").count() > 0)

        b.close()
    print()
    if fails:
        print(f"❌ {len(fails)} pemeriksaan gagal: {fails}")
        return 1
    print("✅ semua pemeriksaan UI lulus")
    return 0


if __name__ == "__main__":
    sys.exit(main())
