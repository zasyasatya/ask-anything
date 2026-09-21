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
    python3 scripts/capture_screenshots.py roles      # login, role member/admin, task

Stage `main`  : seluruh flow UI (hero, navbar collapse, chat + sitasi, kanvas
                fullscreen, interpreter log/LLM/sumber, settings, riwayat)
Stage `pages` : screenshot halaman dokumentasi in-app (jalan setelah stage main,
                karena halaman tersebut menampilkan gambar hasil stage main)
Stage `roles` : alur login & peran — halaman /login, playground member, papan
                task yang ditugaskan, papan /internship, Profil (ganti password),
                konsol Admin (Users + akses per peran). Butuh backend dengan
                `ASK_AUTH_MODE=required` dan akun hasil seed (admin/admin123,
                intern1..3/intern123; dapat di-override lewat env di bawah).

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

#: Kredensial akun hasil seed untuk stage `roles` (lihat app/users.ensure_seed_users).
ADMIN_CREDS = {
    "username": os.environ.get("SEED_ADMIN_USER", "admin"),
    "password": os.environ.get("SEED_ADMIN_PASSWORD", "admin123"),
}
MEMBER_CREDS = {
    "username": os.environ.get("SEED_MEMBER_USER", "intern1"),
    "password": os.environ.get("SEED_MEMBER_PASSWORD", "intern123"),
}
MEMBER_TMP_PASSWORD = os.environ.get("SEED_MEMBER_TMP_PASSWORD", "intern1234")


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


#: Cookie sesi admin untuk panggilan API di luar browser (diisi otomatis).
_API_COOKIE = {"value": ""}


def api_login(creds: dict) -> str:
    """Login ke backend, simpan cookie sesi untuk panggilan API berikutnya."""
    import json
    import urllib.request

    req = urllib.request.Request(
        f"{API}/api/auth/login",
        data=json.dumps(creds).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        cookie = r.headers.get("Set-Cookie") or ""
    _API_COOKIE["value"] = cookie.split(";")[0]
    return _API_COOKIE["value"]


def set_settings(update: dict) -> None:
    import json
    import urllib.request

    if not _API_COOKIE["value"]:
        api_login(ADMIN_CREDS)
    req = urllib.request.Request(
        f"{API}/api/settings",
        data=json.dumps(update).encode(),
        headers={
            "Content-Type": "application/json",
            "Cookie": _API_COOKIE["value"],
        },
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


def ensure_admin_session(page, timeout: int = 90_000) -> None:
    """Mode `required`: login admin dulu supaya halaman aplikasi bisa difoto.

    Pada `ASK_AUTH_MODE=open` halaman langsung terbuka (admin anonim) dan
    fungsi ini tidak melakukan apa pun.
    """
    page.goto(BASE, wait_until="networkidle")
    if page.locator('[data-testid="login-submit"]').count():
        page.fill('[data-testid="login-username"]', ADMIN_CREDS["username"])
        page.fill('[data-testid="login-password"]', ADMIN_CREDS["password"])
        page.click('[data-testid="login-submit"]')
        page.wait_for_selector('[data-testid="nav-user"]', timeout=timeout)
    page.wait_for_timeout(400)


def stage_main(page: "Shots") -> None:
    p = page.page
    OUT.mkdir(parents=True, exist_ok=True)
    ensure_admin_session(p)

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
        ensure_admin_session(w)
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

    print("[15] Settings provider (admin)")
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
        ensure_admin_session(m)
        m.wait_for_timeout(600)
        m.screenshot(path=str(OUT / "15-mobile-hero.png"))
        print(f"  ✔ {OUT / '15-mobile-hero.png'}")


def login(page, creds: dict, timeout: int = 90_000) -> None:
    """Masuk lewat halaman /login seperti user sungguhan (cookie sesi HttpOnly)."""
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.wait_for_selector('[data-testid="login-submit"]')
    page.fill('[data-testid="login-username"]', creds["username"])
    page.fill('[data-testid="login-password"]', creds["password"])
    page.click('[data-testid="login-submit"]')
    # Sidebar hanya muncul setelah sesi sah terbaca klien (GET /api/auth/me).
    page.wait_for_selector('[data-testid="nav-user"]', timeout=timeout)
    page.wait_for_timeout(500)


def logout(page, timeout: int = 60_000) -> None:
    # Tombol keluar ada di sidebar — halaman seperti /internship & /tasks tidak
    # punya sidebar, jadi kembali ke playground dulu.
    if not page.locator('[data-testid="nav-logout"]').count():
        page.goto(BASE, wait_until="networkidle")
        page.wait_for_selector('[data-testid="nav-logout"]', timeout=timeout)
    page.click('[data-testid="nav-logout"]')
    page.wait_for_selector('[data-testid="login-submit"]', timeout=timeout)
    page.wait_for_timeout(400)


def goto(page, path: str, wait: str | None = None, timeout: int = 90_000) -> None:
    page.goto(BASE + path, wait_until="networkidle")
    if wait:
        page.wait_for_selector(wait, timeout=timeout)
    page.wait_for_timeout(600)


def stage_roles(page: "Shots") -> None:
    """Alur login & peran: member (playground + task sendiri) dan admin (konsol).

    Semua tangkapan memakai UI asli; satu-satunya intervensi adalah mengganti
    password member lalu mengembalikannya, supaya basis data contoh tetap sesuai
    dokumentasi (intern123).
    """
    p = page.page
    OUT.mkdir(parents=True, exist_ok=True)

    print("[1] Halaman login (belum ada sesi)")
    p.context.clear_cookies()  # type: ignore[attr-defined]
    goto(p, "/login", '[data-testid="login-submit"]')
    page.save("30-login")

    print("[2] Login gagal (password salah)")
    p.fill('[data-testid="login-username"]', MEMBER_CREDS["username"])
    p.fill('[data-testid="login-password"]', "password-salah")
    p.click('[data-testid="login-submit"]')
    p.wait_for_selector('[data-testid="login-error"]')
    p.wait_for_timeout(400)
    page.save("31-login-error")

    print("[3] Masuk sebagai member (intern) → playground")
    p.fill('[data-testid="login-password"]', MEMBER_CREDS["password"])
    p.click('[data-testid="login-submit"]')
    p.wait_for_selector('[data-testid="nav-user"]')
    p.wait_for_selector('[data-testid="member-provider-badge"]')
    p.wait_for_timeout(900)
    page.save("32-member-chat")
    page.element(p.locator('[data-testid="sidebar"]'), "33-member-sidebar")

    print("[4] Profil member: ganti nama & password sendiri")
    p.click('[data-testid="nav-settings"]')
    p.wait_for_selector('[data-testid="profile-modal"]')
    p.wait_for_timeout(400)
    page.save("34-member-profile")

    print("[5] Ganti password (bukti sukses) → lalu dikembalikan ke password awal")
    fields = p.locator('[data-testid="profile-modal"] input[type="password"]')
    fields.nth(0).fill(MEMBER_CREDS["password"])
    fields.nth(1).fill(MEMBER_TMP_PASSWORD)
    fields.nth(2).fill(MEMBER_TMP_PASSWORD)
    p.click('[data-testid="profile-modal"] button:has-text("Ganti password")')
    p.wait_for_selector("text=Password diganti")
    p.wait_for_timeout(400)
    page.save("35-member-password-changed")
    fields.nth(0).fill(MEMBER_TMP_PASSWORD)
    fields.nth(1).fill(MEMBER_CREDS["password"])
    fields.nth(2).fill(MEMBER_CREDS["password"])
    p.click('[data-testid="profile-modal"] button:has-text("Ganti password")')
    p.wait_for_timeout(1500)
    p.click('[data-testid="profile-modal"] button:has-text("Tutup")')
    p.wait_for_timeout(400)

    print("[6] Papan task member: hanya task yang ditugaskan")
    goto(p, "/tasks", '[data-testid="task-count"]')
    page.save("36-member-tasks")

    print("[7] Detail task (member: status & komentar, tanpa hapus/penugasan)")
    cards = p.locator('[data-testid^="task-open-"]')
    if cards.count():
        cards.first.click()
        p.wait_for_selector('[data-testid="task-detail"]')
        p.wait_for_timeout(600)
        page.save("37-member-task-detail")
        p.locator('[data-testid="task-detail"]').get_by_text("Tutup", exact=True).first.click()
        p.wait_for_timeout(400)

    print("[8] Papan proyek internship (member: task INT-NNN miliknya)")
    goto(p, "/internship", "text=Proyek Internship")
    p.wait_for_timeout(900)
    page.save("38-member-internship")

    print("[9] Admin: konsol → Users")
    logout(p)
    login(p, ADMIN_CREDS)
    goto(p, "/admin", "text=Admin — Pipeline")
    p.click('nav button:has-text("Users")')
    p.wait_for_selector("text=Akun & peran")
    p.wait_for_timeout(600)
    page.save("39-admin-users")

    print("[10] Admin: reset password member (inline)")
    p.click('button:has-text("Reset password")')
    p.wait_for_timeout(300)
    p.fill('input[placeholder="password baru (min. 6 karakter)"]',
           MEMBER_TMP_PASSWORD)
    page.save("40-admin-reset-password")
    p.click('button:has-text("Reset password")')  # tutup panel tanpa menyimpan
    p.wait_for_timeout(300)
    # kembalikan ke panel tertutup: tak ada perubahan password yang tersimpan.

    print("[11] Admin: Pipeline → akses per peran")
    p.click('nav button:has-text("Pipeline")')
    p.wait_for_selector("text=Akses per peran")
    p.wait_for_timeout(700)
    page.save("41-admin-pipeline-roles")

    print("[12] Admin: papan task dengan pemilih trek (Platform | Internship)")
    goto(p, "/tasks", '[data-testid="task-count"]')
    p.wait_for_timeout(900)
    page.save("42-admin-board-platform")
    p.click('button:has-text("Internship")')
    p.wait_for_timeout(1500)
    page.save("43-admin-board-internship")

    print("[13] Admin: papan proyek internship (semua peserta)")
    goto(p, "/internship", "text=Proyek Internship")
    p.wait_for_timeout(900)
    page.save("44-admin-internship")

    print("[14] Admin: ringkasan pipeline")
    goto(p, "/admin", "text=Admin — Pipeline")
    p.wait_for_timeout(700)
    page.save("45-admin-overview")


def stage_pages(page: "Shots") -> None:
    p = page.page
    ensure_admin_session(p)
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
        elif stage == "roles":
            stage_roles(shots)
        else:
            print(f"stage tidak dikenal: {stage}")
            return 2
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
