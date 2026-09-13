#!/usr/bin/env python3
"""Server pencarian & halaman web tiruan untuk demo/uji UI tanpa internet.

Berguna di dua situasi:
1. Development offline / CI yang tidak punya akses ke lite.duckduckgo.com —
   `web_search` dan `fetch_url` tetap bisa diuji end-to-end (termasuk alur
   sitasi: hasil pencarian → sumber bernomor → jawaban dengan [n]).
2. Demo "gateway pencarian internal": bentuk responsnya sengaja identik dengan
   DuckDuckGo-lite, jadi tidak ada kode aplikasi yang berubah.

HANYA untuk demo/pengujian — datanya fiktif dan server tidak melakukan
validasi apa pun. Jangan pakai ini sebagai sumber fakta di produksi.

Pemakaian:
    python3 scripts/fake_search_server.py --port 8099
    ASK_SEARCH_DDG_URL=http://127.0.0.1:8099/lite/  …  (atau POST /api/settings)

Endpoint:
    GET /lite/?q=…          → HTML daftar hasil (diparse tools/web_search.py)
    GET /page/<slug>        → halaman artikel (diparse tools/fetch_url.py)
    GET /health             → {"ok": true}
"""
from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

#: Data fiktif — judul/url/snippet dibuat konsisten supaya bisa diperiksa test.
DOCS: list[dict[str, str]] = [
    {
        "slug": "agent-loop",
        "title": "Apa itu agent loop (dokumentasi demo)",
        "url_path": "/page/agent-loop",
        "snippet": "Agent loop mengulang: rencana, panggil tool, baca hasil, "
                   "lalu jawab. Panjang loop dibatasi max_steps.",
        "body": "Agent loop adalah siklus: model menerima pesan, memutuskan "
                "memanggil tool atau tidak, hasil tool disisipkan sebagai pesan "
                "role tool, lalu model menjawab. Batas langkah (max_steps) "
                "mencegah loop tak berhenti. Setiap langkah dicatat sebagai "
                "event trace supaya bisa direkonstruksi di interpreter.",
    },
    {
        "slug": "mekanisme-sitasi",
        "title": "Mekanisme sitasi jawaban LLM (dokumentasi demo)",
        "url_path": "/page/mekanisme-sitasi",
        "snippet": "Sitasi dibuat valid dengan daftar sumber bernomor; marker "
                   "[n] diverifikasi terhadap daftar itu sebelum ditampilkan.",
        "body": "Sitasi yang dapat diverifikasi membutuhkan registri sumber: "
                "setiap URL yang benar-benar diambil dicatat dan diberi nomor. "
                "Model diminta menulis [n] setelah kalimat yang dibuktikannya. "
                "Nomor di luar registri dianggap tidak valid dan ditandai, bukan "
                "disembunyikan. Konten yang dibuat tool (mis. diagram) tidak "
                "boleh disajikan sebagai sumber karena bukan bukti eksternal.",
    },
    {
        "slug": "render-diagram",
        "title": "Renderer diagram: SVG statis vs graph interaktif (dokumentasi demo)",
        "url_path": "/page/render-diagram",
        "snippet": "Renderer ketat gagal total saat sumber rusak; parser toleran "
                   "menyisakan node yang terbaca dan mencatat sisanya.",
        "body": "Ada dua strategi merender diagram. Pertama: serahkan sumber "
                 "ke renderer ketat — sekali sintaks salah, seluruh diagram "
                 "hilang. Kedua: parse sendiri secara toleran, kumpulkan node "
                 "dan edge yang terbaca, catat baris bermasalah sebagai "
                 "peringatan, lalu render sebagai struktur yang bisa "
                 "diinteraksi. Strategi kedua membuat hasil keluaran model yang "
                 "sering tidak sempurna tetap berguna.",
    },
]

_BY_SLUG = {d["slug"]: d for d in DOCS}
_HOST = "http://127.0.0.1:8099"


def _lite_html(query: str) -> str:
    """Tata letak DuckDuckGo-lite: <a href> lalu sel snippet di sebelahnya."""
    rows = []
    for d in DOCS:
        if query and query.lower()[:4] not in d["title"].lower() and query.lower() not in d["body"].lower():
            # tetap kembalikan semuanya: query bebas, yang penting alurnya nyata
            pass
        rows.append(
            "<tr><td>"
            f'<a rel="nofollow" href="{_HOST}{d["url_path"]}">'
            f"{html.escape(d['title'])}</a>"
            f"</td></tr><tr><td>{html.escape(d['snippet'])}</td></tr>"
        )
    return (
        "<html><head><title>demo search</title></head><body><table>"
        + "".join(rows)
        + "</table></body></html>"
    )


def _page_html(doc: dict[str, str]) -> str:
    extra = "".join(
        f"<li><a href=\"{_HOST}{o['url_path']}\">{html.escape(o['title'])}</a></li>"
        for o in DOCS if o is not doc
    )
    return f"""<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<title>{html.escape(doc['title'])}</title>
<style>body{{font:16px/1.7 system-ui;max-width:46rem;margin:3rem auto;padding:0 1rem}}
h1{{font-size:1.6rem}} nav{{margin-top:2rem;border-top:1px solid #ddd;padding-top:1rem}}</style>
</head><body>
<header><span>dokumentasi demo — data fiktif</span></header>
<h1>{html.escape(doc['title'])}</h1>
<p>{html.escape(doc['body'])}</p>
<p>Referensi tambahan: materi tentang mekanisasi sitasi dan renderer diagram
ada di halaman terkait di bawah ini.</p>
<nav><ul>{extra}</ul></nav>
<footer><span>halaman demo lokal, bukan sumber publik</span></footer>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        u = urlparse(self.path)
        if u.path in ("/lite", "/lite/"):
            q = (parse_qs(u.query).get("q") or [""])[0]
            self._send(200, _lite_html(q).encode(), "text/html")
        elif u.path == "/health":
            self._send(200, json.dumps({"ok": True, "docs": len(DOCS)}).encode(),
                       "application/json")
        elif u.path.startswith("/page/"):
            slug = u.path.split("/page/", 1)[1].strip("/")
            doc = _BY_SLUG.get(slug)
            if doc is None:
                self._send(404, b"<html><body>not found</body></html>", "text/html")
                return
            self._send(200, _page_html(doc).encode(), "text/html")
        else:
            self._send(404, b"<html><body>not found</body></html>", "text/html")

    def log_message(self, *a) -> None:  # senyap
        return


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8099)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"fake search/page server → http://127.0.0.1:{args.port}/lite/")
    print(f"set ASK_SEARCH_DDG_URL=http://127.0.0.1:{args.port}/lite/")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
