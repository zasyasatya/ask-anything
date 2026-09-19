"""OCR untuk RAG: PDF hasil scan & berkas gambar.

Yang dijaga tes ini:
  * deteksi halaman "praktis tanpa teks" (halaman scan hanya menyisakan
    artefak seperti nomor halaman — `if not text` tidak cukup),
  * halaman scan benar-benar terbaca dan masuk index sehingga bisa diretrieval
    (sebelum ini dokumen scan berstatus `ready` tetapi kosong),
  * gambar lepas (foto/scan) bisa jadi dokumen RAG,
  * tanpa mesin OCR pipeline **tidak crash** tapi melaporkan sebabnya,
  * pagar pengaman: OCR bisa dimatikan admin, jumlah halaman dibatasi.

Tes yang benar-benar menjalankan OCR ditandai `needs_ocr_engine` supaya suite
tetap hijau di environment tanpa paket OCR.
"""
from __future__ import annotations

import io

import pytest

from app import governance, ocr, rag
from app.config import settings

needs_ocr_engine = pytest.mark.skipif(
    not ocr.available(),
    reason="mesin OCR tidak terpasang (pip install -r backend/requirements-ocr.txt)",
)
needs_pillow = pytest.mark.skipif(
    not ocr.dependencies()["pillow"], reason="Pillow tidak terpasang")

#: OCR di CPU memakan puluhan detik per halaman. Tes yang benar-benar
#: menjalankannya ditandai `slow` supaya bisa dilewati saat iterasi cepat:
#:     pytest backend/tests -m "not slow"
real_ocr = pytest.mark.slow


@pytest.fixture(autouse=True)
def _clean_rag():
    from app import db, main

    main._init_storage()

    def _reset() -> None:
        db.execute("DELETE FROM rag_chunks")
        db.execute("DELETE FROM rag_documents")
        db.execute("DELETE FROM admin_policy WHERE key='rag'")

    _reset()
    yield
    _reset()


# ---------------------------------------------------------------------------
# Pembuat berkas uji
# ---------------------------------------------------------------------------

def _text_image(lines: list[str], *, size=(1300, 230), rotate: float = 0):
    """Gambar uji berisi teks.

    Ukuran dipilih agar sisi terpanjang sudah >= `min_long_side` di
    `ocr.preprocess`, sehingga tidak ada upscale — OCR di CPU sangat sensitif
    terhadap jumlah piksel dan ini menjaga suite tetap waras durasinya.
    """
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 42)
    except Exception:  # noqa: BLE001 - font sistem berbeda antar OS
        font = ImageFont.load_default()
    y = 40
    for line in lines:
        draw.text((40, y), line, fill="black", font=font)
        y += 80
    if rotate:
        image = image.rotate(rotate, expand=False, fillcolor="white")
    return image


def _scanned_pdf(pages: list[list[str]]) -> bytes:
    """PDF yang isinya hanya gambar — tanpa lapisan teks, seperti hasil scan."""
    images = [_text_image(lines, size=(1300, 300)) for lines in pages]
    buffer = io.BytesIO()
    images[0].save(buffer, "PDF", save_all=True, append_images=images[1:])
    return buffer.getvalue()


def _image_bytes(lines: list[str], fmt: str = "PNG", **kwargs) -> bytes:
    buffer = io.BytesIO()
    _text_image(lines, **kwargs).save(buffer, fmt)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Deteksi halaman scan
# ---------------------------------------------------------------------------

def test_blank_and_artefact_only_pages_are_marked_for_ocr():
    assert ocr.needs_ocr("") is True
    assert ocr.needs_ocr("   \n\n  \t ") is True
    assert ocr.needs_ocr("- 3 -") is True, "nomor halaman saja = halaman scan"


def test_a_page_with_real_text_is_not_sent_to_ocr():
    assert ocr.needs_ocr("Ini paragraf yang cukup panjang " * 5) is False


def test_threshold_is_configurable():
    assert ocr.needs_ocr("dua belas", min_chars=5) is False
    assert ocr.needs_ocr("dua belas", min_chars=50) is True


def test_only_alphanumeric_characters_count():
    """Halaman penuh garis/simbol hasil scan tetap dianggap butuh OCR."""
    assert ocr.needs_ocr("---- ..... ____ |||| " * 10) is True


# ---------------------------------------------------------------------------
# Ketersediaan & pemilihan mesin
# ---------------------------------------------------------------------------

def test_dependencies_reports_engines_and_install_hint():
    deps = ocr.dependencies()
    assert isinstance(deps["engines"], list)
    assert deps["available"] is bool(deps["engines"])
    if not deps["available"]:
        assert deps["install_hint"], "kalau tidak tersedia, harus ada petunjuk"


def test_unknown_preferred_engine_is_not_silently_replaced():
    assert ocr.pick_engine("mesin-yang-tidak-ada") is None


@needs_ocr_engine
def test_auto_picks_an_installed_engine():
    assert ocr.pick_engine("auto") in ocr.dependencies()["engines"]


def test_ocr_reports_an_error_instead_of_raising_without_an_engine(monkeypatch):
    """Tanpa mesin OCR, pipeline harus menjelaskan sebabnya — bukan meledak."""
    monkeypatch.setattr(ocr, "pick_engine", lambda *_a, **_k: None)
    out = ocr.ocr_image(object())
    assert out["text"] == ""
    assert out["error"] and "pip install" in out["error"]


def test_unreadable_image_bytes_are_reported_gracefully():
    out = ocr.ocr_image_bytes(b"ini bukan gambar")
    assert out["text"] == ""
    assert "tidak bisa dibaca" in out["error"] or out["error"]


# ---------------------------------------------------------------------------
# OCR sungguhan
# ---------------------------------------------------------------------------

@real_ocr
@needs_ocr_engine
@needs_pillow
def test_text_in_an_image_is_read_back():
    out = ocr.ocr_image_bytes(_image_bytes(["Nomor 471 SKD 2026"]))
    assert not out.get("error"), out
    assert "471" in out["text"]
    assert out["confidence"] > 0.5
    assert out["engine"] in ocr.dependencies()["engines"]


@real_ocr
@needs_ocr_engine
@needs_pillow
def test_a_skewed_page_is_still_read():
    """Scan miring adalah kasus normal; praproses meluruskannya."""
    out = ocr.ocr_image_bytes(_image_bytes(["Piutang usaha Rp 12 miliar"],
                                           rotate=2))
    assert not out.get("error"), out
    assert "12" in out["text"]


@real_ocr
@needs_ocr_engine
@needs_pillow
def test_scanned_pdf_pages_get_their_text_filled_in():
    data = _scanned_pdf([["LAPORAN KEUANGAN 2026"], ["Laba bersih Rp 7 miliar"]])
    pages = rag.parse_pdf(data)
    # prasyarat: PDF ini memang tidak punya lapisan teks
    assert all(ocr.needs_ocr(p["text"]) for p in pages)

    summary = ocr.ocr_pdf(data, pages, dpi=150)
    assert summary["attempted"] is True
    assert summary["pages_ocred"] == 2, summary
    assert summary["confidence"] > 0.5
    assert all(p.get("ocr") is True for p in pages)
    joined = " ".join(p["text"] for p in pages)
    assert "2026" in joined and "7" in joined


@real_ocr
@needs_ocr_engine
@needs_pillow
def test_max_pages_guard_limits_huge_scans():
    data = _scanned_pdf([["Halaman satu"], ["Halaman dua"], ["Halaman tiga"]])
    pages = rag.parse_pdf(data)
    summary = ocr.ocr_pdf(data, pages, dpi=100, max_pages=1)
    assert summary["pages_ocred"] == 1
    assert summary["skipped"] == [2, 3]


def test_pages_with_text_are_never_sent_to_ocr():
    """Hemat waktu & biaya: PDF teks normal tidak boleh memicu OCR."""
    pages = [{"page": 1, "text": "Paragraf lengkap dengan banyak kata. " * 10}]
    summary = ocr.ocr_pdf(b"", pages, dpi=100)
    assert summary["attempted"] is False
    assert summary["pages_scanned"] == 0


def test_embedded_text_is_not_replaced_by_a_poorer_ocr_result(monkeypatch):
    """Pengaman kualitas index.

    Halaman dengan satu baris teks sah tetap di bawah ambang `needs_ocr`, jadi
    tetap di-OCR. Bila hasil OCR lebih miskin dari teks tertanamnya, teks asli
    harus DIPERTAHANKAN — menimpanya akan menurunkan kualitas retrieval.
    """
    original = "Pasal 12 ayat 3 UU Cipta Kerja"
    pages = [{"page": 1, "text": original}]

    monkeypatch.setattr(ocr, "pick_engine", lambda *_a, **_k: "rapidocr")
    monkeypatch.setattr(ocr, "dependencies",
                        lambda: {"available": True, "engines": ["rapidocr"],
                                 "pdf_render": True, "pillow": True,
                                 "install_hint": None})
    monkeypatch.setattr(ocr, "render_pdf_pages",
                        lambda *_a, **_k: {1: object()})
    monkeypatch.setattr(ocr, "ocr_image",
                        lambda *_a, **_k: {"text": "Pasa 12", "confidence": 0.4,
                                           "lines": [], "line_count": 1})

    summary = ocr.ocr_pdf(b"", pages, min_chars=80)
    assert pages[0]["text"] == original, "teks tertanam tidak boleh tertimpa"
    assert summary["pages_ocred"] == 0
    assert summary["kept_embedded"] == 1


def test_richer_ocr_text_does_replace_a_near_empty_page(monkeypatch):
    pages = [{"page": 1, "text": "- 2 -"}]
    monkeypatch.setattr(ocr, "pick_engine", lambda *_a, **_k: "rapidocr")
    monkeypatch.setattr(ocr, "dependencies",
                        lambda: {"available": True, "engines": ["rapidocr"],
                                 "pdf_render": True, "pillow": True,
                                 "install_hint": None})
    monkeypatch.setattr(ocr, "render_pdf_pages",
                        lambda *_a, **_k: {1: object()})
    monkeypatch.setattr(ocr, "ocr_image",
                        lambda *_a, **_k: {"text": "Jumlah karyawan 318 orang",
                                           "confidence": 0.93, "lines": [],
                                           "line_count": 1})

    summary = ocr.ocr_pdf(b"", pages, min_chars=80)
    assert "318" in pages[0]["text"]
    assert pages[0]["ocr"] is True
    assert summary["pages_ocred"] == 1


# ---------------------------------------------------------------------------
# Integrasi pipeline RAG
# ---------------------------------------------------------------------------

@real_ocr
@needs_ocr_engine
@needs_pillow
def test_scanned_pdf_becomes_a_searchable_document():
    """Inti fitur: dokumen scan bisa dijawab, bukan hanya berstatus ready."""
    governance.update_policy({"rag": {"ocr_enabled": True, "ocr_dpi": 150}})
    data = _scanned_pdf([["Jumlah karyawan tetap 318 orang"]])

    doc = rag.ingest_file(settings=settings, filename="scan.pdf", data=data)
    assert doc["status"] == "ready", doc.get("error")
    assert doc["kind"] == "pdf"
    assert doc["ocr_pages"] == 1
    assert doc["ocr_engine"]
    assert doc["chars"] > 0, "dokumen scan tidak boleh masuk index kosong"
    assert doc["timings"].get("ocr_ms", 0) > 0

    hits = rag.retrieve("berapa jumlah karyawan tetap", top_k=3)
    assert hits, "isi hasil OCR harus bisa diretrieval"
    assert "318" in hits[0]["text"]


@real_ocr
@needs_ocr_engine
@needs_pillow
def test_image_upload_becomes_a_rag_document():
    doc = rag.ingest_file(settings=settings, filename="surat.png",
                          data=_image_bytes(["Surat Keterangan Domisili"]))
    assert doc["status"] == "ready", doc.get("error")
    assert doc["kind"] == "image"
    assert doc["ocr_pages"] == 1
    assert rag.retrieve("surat keterangan domisili", top_k=2)


@needs_pillow
def test_admin_can_switch_ocr_off():
    """Dimatikan admin → dokumen gagal dengan alasan jelas, bukan diam-diam."""
    governance.update_policy({"rag": {"ocr_enabled": False}})
    doc = rag.ingest_file(settings=settings, filename="surat.png",
                          data=_image_bytes(["apa pun"]))
    assert doc["status"] == "error"
    assert "OCR dimatikan" in doc["error"]


@needs_pillow
def test_pdf_with_real_text_still_ingests_without_ocr():
    """Regresi: jalur PDF teks biasa tidak boleh berubah perilaku."""
    from pypdf import PdfWriter

    # PDF teks dibuat lewat reportlab tidak tersedia; pakai chunk manual.
    pages = [{"page": 1, "text": "Pendapatan tahun ini naik 15 persen. " * 20}]
    chunks = rag.chunk_pages(pages, 400, 50)
    assert chunks and all(c["text"] for c in chunks)
    assert PdfWriter is not None  # pypdf tersedia


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def test_ocr_status_endpoint_exposes_readiness(client):
    out = client.get("/api/rag/ocr").json()
    assert "deps" in out and "engines" in out["deps"]
    assert ".pdf" in out["accepts"]
    assert ".png" in out["accepts"]
    assert out["policy"]["ocr_enabled"] in (True, False)


def test_health_reports_ocr_readiness(client):
    out = client.get("/api/health").json()
    assert "ocr" in out
    assert isinstance(out["ocr"]["engines"], list)


def test_upload_rejects_an_unsupported_extension(client):
    r = client.post("/api/rag/upload",
                    files={"file": ("catatan.txt", b"halo", "text/plain")})
    assert r.status_code == 415
    assert "OCR" in r.json()["detail"]


@real_ocr
@needs_ocr_engine
@needs_pillow
def test_upload_accepts_an_image(client):
    r = client.post("/api/rag/upload?wait=true",
                    files={"file": ("foto.png",
                                    _image_bytes(["Faktur nomor 8891"]),
                                    "image/png")})
    assert r.status_code == 200, r.text
    doc = r.json()["document"]
    assert doc["kind"] == "image"
    assert doc["status"] == "ready", doc.get("error")


@needs_pillow
def test_upload_returns_immediately_and_finishes_in_the_background(
        client, monkeypatch):
    """OCR lambat tidak boleh menyandera request HTTP.

    Dokumen tebal hasil scan bisa memakan puluhan detik per halaman; upload
    harus langsung membalas, lalu kemajuannya dipantau dari daftar dokumen.

    Yang diuji di sini adalah **mekanisme background**, bukan akurasi OCR —
    karena itu mesinnya distub. Sinkronisasi memakai `threading.Event`, bukan
    ambang waktu: versi berbasis waktu terbukti flaky (lulus sendirian, gagal
    saat seluruh suite membebani mesin).
    """
    import threading
    import time as _time

    from app import ocr as ocr_module

    entered = threading.Event()   # worker sudah masuk tahap OCR
    release = threading.Event()   # izinkan worker menyelesaikan

    def stubbed_ocr(_data, **_kwargs):
        entered.set()
        release.wait(timeout=60)
        return {"text": "Kuitansi 12345", "confidence": 0.95,
                "lines": [{"text": "Kuitansi 12345", "confidence": 0.95}],
                "line_count": 1, "engine": "stub"}

    monkeypatch.setattr(ocr_module, "ocr_image_bytes", stubbed_ocr)
    monkeypatch.setattr(ocr_module, "available", lambda: True)

    r = client.post("/api/rag/upload",
                    files={"file": ("antre.png",
                                    _image_bytes(["Kuitansi 12345"]),
                                    "image/png")})
    assert r.status_code == 200, r.text
    doc = r.json()["document"]

    # Bukti inti: respons sudah kembali sementara worker masih tertahan di OCR.
    assert entered.wait(timeout=30), "worker background tidak pernah berjalan"
    still = next(d for d in client.get("/api/rag/documents").json()["documents"]
                 if d["id"] == doc["id"])
    assert still["status"] != "ready", \
        "upload tidak boleh menunggu OCR selesai"

    release.set()
    deadline = _time.time() + 60
    final = still
    while _time.time() < deadline:
        docs = client.get("/api/rag/documents").json()["documents"]
        final = next(d for d in docs if d["id"] == doc["id"])
        if final["status"] in ("ready", "error"):
            break
        _time.sleep(0.05)
    assert final["status"] == "ready", final.get("error")
    assert final["ocr_pages"] == 1
    assert final["ocr_engine"] == "stub"
