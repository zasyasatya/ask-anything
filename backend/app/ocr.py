"""OCR untuk pipeline RAG — membaca PDF hasil scan dan berkas gambar.

Kenapa perlu: `pypdf` hanya bisa mengambil teks yang memang *tertanam* di PDF.
Dokumen hasil scan/foto tidak punya lapisan teks, sehingga sebelumnya masuk ke
index sebagai halaman kosong — dokumen "berhasil" diproses tapi tidak pernah
bisa dijawab. Modul ini menutup celah itu.

Alur:

    halaman PDF  --pypdf-->  teks tertanam
                             │
                             └─ terlalu sedikit (lihat `needs_ocr`)?
                                   │
                                   ├─ pypdfium2: render halaman → bitmap
                                   ├─ praproses: grayscale, upscale, deskew
                                   └─ mesin OCR → teks + confidence

Mesin OCR dipilih berlapis (`preferred_engine`, lalu urutan `ENGINE_ORDER`):

  rapidocr   — PP-OCRv4 di atas onnxruntime. Murni wheel pip (tanpa binary
               sistem), jadi bisa dipasang di container maupun Windows.
  tesseract  — dipakai bila `pytesseract` + binary Tesseract tersedia
               (mis. image Docker yang sudah memuatnya).

Bila tidak ada mesin yang tersedia, modul ini **tidak melempar**: dokumen tetap
diproses dengan teks yang ada dan alasannya dilaporkan ke status dokumen +
`/api/health`, supaya kegagalan terlihat alih-alih menjadi index kosong.
"""
from __future__ import annotations

import io
import time
from typing import Any

#: Urutan percobaan mesin OCR bila `ocr_engine` = "auto".
ENGINE_ORDER: tuple[str, ...] = ("rapidocr", "tesseract")

#: Cache engine: inisialisasi RapidOCR memuat model ONNX (~2 detik) — tidak
#: boleh diulang untuk setiap halaman.
_ENGINE_CACHE: dict[str, Any] = {}

INSTALL_HINT = (
    "OCR belum aktif. Pasang mesin OCR tanpa binary sistem:\n"
    "  pip install pypdfium2 rapidocr-onnxruntime\n"
    "(alternatif: pip install pytesseract + install binary Tesseract)"
)


# ---------------------------------------------------------------------------
# Ketersediaan
# ---------------------------------------------------------------------------

def _module(name: str) -> Any | None:
    try:
        return __import__(name)
    except Exception:  # noqa: BLE001 - paket rusak = dianggap tidak ada
        return None


def dependencies() -> dict[str, Any]:
    """Apa yang benar-benar bisa dipakai di environment ini."""
    renderer = _module("pypdfium2")
    pillow = _module("PIL")
    rapid = _module("rapidocr_onnxruntime")
    tess = _module("pytesseract")

    tesseract_binary = False
    if tess is not None:
        try:
            tess.get_tesseract_version()
            tesseract_binary = True
        except Exception:  # noqa: BLE001 - paket ada, binary tidak
            tesseract_binary = False

    engines = []
    if rapid is not None:
        engines.append("rapidocr")
    if tesseract_binary:
        engines.append("tesseract")

    return {
        "available": bool(engines),
        "engines": engines,
        "pdf_render": renderer is not None,
        "pillow": pillow is not None,
        "install_hint": None if engines else INSTALL_HINT,
    }


def available() -> bool:
    return dependencies()["available"]


def pick_engine(preferred: str = "auto") -> str | None:
    """Nama mesin yang akan dipakai, atau None bila tak ada."""
    engines = dependencies()["engines"]
    preferred = (preferred or "auto").strip().lower()
    if preferred and preferred != "auto":
        return preferred if preferred in engines else None
    for name in ENGINE_ORDER:
        if name in engines:
            return name
    return None


# ---------------------------------------------------------------------------
# Praproses gambar
# ---------------------------------------------------------------------------

def _deskew(array: Any) -> Any:
    """Luruskan halaman yang miring (hasil scan/foto).

    Hanya diterapkan pada kemiringan 0,3°–15°: di bawah itu tidak berpengaruh,
    di atas itu deteksi sudut biasanya salah (mis. gambar/tabel besar) dan
    memutar halaman justru merusak akurasi.
    """
    try:
        import cv2
        import numpy as np
    except Exception:  # noqa: BLE001 - opencv opsional
        return array

    try:
        gray = array if array.ndim == 2 else cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
        inverted = cv2.bitwise_not(gray)
        mask = cv2.threshold(inverted, 0, 255,
                             cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        coords = cv2.findNonZero(mask)
        if coords is None:
            return array
        angle = cv2.minAreaRect(coords)[-1]
        if angle > 45:
            angle -= 90
        if not (0.3 <= abs(angle) <= 15):
            return array
        h, w = array.shape[:2]
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(array, matrix, (w, h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
    except Exception:  # noqa: BLE001 - praproses gagal ≠ OCR gagal
        return array


def preprocess(image: Any, *, min_long_side: int = 1200,
               max_long_side: int = 1800, deskew: bool = True) -> Any:
    """Grayscale + upscale **terukur** + deskew → numpy array siap OCR.

    Upscale hanya berguna untuk gambar yang benar-benar kecil (teks beberapa
    belas piksel). Menaikkan gambar yang sudah cukup besar justru merugikan:
    diukur pada mesin ini, 1000×300 yang dinaikkan ke 3333×1000 memakan ~65 s
    dengan confidence 0,83 — sedangkan halaman native 2480×3508 selesai dengan
    confidence 0,90. Potongan lebar-pendek (struk, kop surat) paling parah
    terkena bila skala hanya berpatokan pada tinggi.

    Aturannya: perbesar hanya bila sisi terpanjang < `min_long_side`, dan
    jangan sampai melewati `max_long_side` (maksimum 2×).
    """
    from PIL import Image

    if not isinstance(image, Image.Image):  # sudah array
        array = image
    else:
        picture = image.convert("L")
        long_side = max(picture.width, picture.height)
        if long_side < min_long_side:
            scale = min(2.0, max_long_side / max(1, long_side))
            if scale > 1.05:
                picture = picture.resize(
                    (int(picture.width * scale), int(picture.height * scale)),
                    Image.LANCZOS)
        array = _to_array(picture)
    return _deskew(array) if deskew else array


def _to_array(picture: Any) -> Any:
    import numpy as np

    return np.array(picture)


# ---------------------------------------------------------------------------
# Mesin OCR
# ---------------------------------------------------------------------------

def _rapidocr(array: Any) -> dict[str, Any]:
    from rapidocr_onnxruntime import RapidOCR

    engine = _ENGINE_CACHE.get("rapidocr")
    if engine is None:
        engine = RapidOCR()
        _ENGINE_CACHE["rapidocr"] = engine

    result, _timings = engine(array)
    lines: list[dict[str, Any]] = []
    for item in result or []:
        # RapidOCR 1.2.x mengembalikan [box, text, score] dengan score berupa
        # string — konversi eksplisit, jangan asumsikan float.
        if len(item) < 3:
            continue
        text = str(item[1] or "").strip()
        try:
            score = float(item[2])
        except (TypeError, ValueError):
            score = 0.0
        if text:
            lines.append({"text": text, "confidence": round(score, 4)})
    return _merge_lines(lines, engine_name="rapidocr")


def _tesseract(array: Any) -> dict[str, Any]:
    import pytesseract
    from PIL import Image

    picture = Image.fromarray(array)
    data = pytesseract.image_to_data(
        picture, lang="ind+eng", output_type=pytesseract.Output.DICT)
    lines: list[dict[str, Any]] = []
    for text, conf in zip(data.get("text", []), data.get("conf", [])):
        text = (text or "").strip()
        try:
            score = float(conf) / 100.0
        except (TypeError, ValueError):
            score = 0.0
        if text and score >= 0:
            lines.append({"text": text, "confidence": round(score, 4)})
    return _merge_lines(lines, engine_name="tesseract")


def _merge_lines(lines: list[dict[str, Any]], *, engine_name: str) -> dict[str, Any]:
    text = "\n".join(line["text"] for line in lines)
    confidences = [line["confidence"] for line in lines if line["confidence"] > 0]
    return {
        "text": text,
        "lines": lines,
        "line_count": len(lines),
        "confidence": round(sum(confidences) / len(confidences), 4)
        if confidences else 0.0,
        "engine": engine_name,
    }


_RUNNERS = {"rapidocr": _rapidocr, "tesseract": _tesseract}


def ocr_image(image: Any, *, engine: str = "auto",
              deskew: bool = True) -> dict[str, Any]:
    """OCR satu gambar (PIL.Image atau numpy array).

    Selalu mengembalikan dict; kegagalan dilaporkan di kunci `error` alih-alih
    melempar, karena satu halaman rusak tidak boleh menggagalkan dokumen.
    """
    name = pick_engine(engine)
    if name is None:
        return {"text": "", "lines": [], "line_count": 0, "confidence": 0.0,
                "engine": "", "error": INSTALL_HINT}
    started = time.time()
    try:
        array = preprocess(image, deskew=deskew)
        out = _RUNNERS[name](array)
    except Exception as exc:  # noqa: BLE001
        return {"text": "", "lines": [], "line_count": 0, "confidence": 0.0,
                "engine": name, "error": f"{type(exc).__name__}: {exc}"}
    out["duration_ms"] = round((time.time() - started) * 1000, 1)
    return out


def ocr_image_bytes(data: bytes, **kwargs: Any) -> dict[str, Any]:
    """OCR berkas gambar mentah (upload PNG/JPG/TIFF)."""
    try:
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        return {"text": "", "lines": [], "line_count": 0, "confidence": 0.0,
                "engine": "", "error": f"Pillow tidak tersedia: {exc}"}
    try:
        picture = Image.open(io.BytesIO(data))
        picture.load()
    except Exception as exc:  # noqa: BLE001
        return {"text": "", "lines": [], "line_count": 0, "confidence": 0.0,
                "engine": "", "error": f"gambar tidak bisa dibaca: {exc}"}
    return ocr_image(picture, **kwargs)


# ---------------------------------------------------------------------------
# PDF hasil scan
# ---------------------------------------------------------------------------

def needs_ocr(page_text: str, min_chars: int = 80) -> bool:
    """Halaman ini praktis tanpa teks (hasil scan)?

    Memakai jumlah karakter *bermakna*: halaman scan sering menyisakan
    artefak seperti nomor halaman atau spasi/newline saja, yang membuat
    pemeriksaan `if not text` tidak pernah menyala.
    """
    return _alnum_len(page_text) < max(0, int(min_chars))


def _alnum_len(text: str) -> int:
    """Panjang teks tanpa spasi/tanda baca — ukuran "isi" sebenarnya."""
    return sum(1 for ch in (text or "") if ch.isalnum())


def render_pdf_pages(data: bytes, page_numbers: list[int], *,
                     dpi: int = 200) -> dict[int, Any]:
    """Render halaman tertentu (1-based) menjadi PIL.Image via pypdfium2."""
    import pypdfium2 as pdfium

    scale = max(0.5, min(6.0, dpi / 72.0))
    out: dict[int, Any] = {}
    document = pdfium.PdfDocument(io.BytesIO(data))
    try:
        total = len(document)
        for number in page_numbers:
            index = int(number) - 1
            if index < 0 or index >= total:
                continue
            page = document[index]
            try:
                out[int(number)] = page.render(scale=scale).to_pil()
            finally:
                page.close()
    finally:
        document.close()
    return out


def ocr_pdf(data: bytes, pages: list[dict[str, Any]], *,
            min_chars: int = 80, dpi: int = 200, max_pages: int = 40,
            engine: str = "auto", deskew: bool = True) -> dict[str, Any]:
    """Lengkapi halaman tanpa teks dengan hasil OCR.

    `pages` adalah keluaran `rag.parse_pdf` dan **dimodifikasi di tempat**:
    halaman yang berhasil di-OCR mendapat `text`, penanda `ocr=True`, dan
    confidence-nya. Nilai kembalian adalah ringkasan untuk status dokumen dan
    Mechanistic Interpreter.
    """
    targets = [p["page"] for p in pages if needs_ocr(p.get("text", ""), min_chars)]
    summary: dict[str, Any] = {
        "attempted": False,
        "engine": "",
        "pages_scanned": len(targets),
        "pages_ocred": 0,
        "chars_added": 0,
        "confidence": 0.0,
        "skipped": [],
        "error": "",
        "duration_ms": 0.0,
    }
    if not targets:
        return summary

    name = pick_engine(engine)
    if name is None:
        summary["error"] = INSTALL_HINT
        return summary
    if not dependencies()["pdf_render"]:
        summary["error"] = ("pypdfium2 belum ter-install — halaman scan tidak "
                            "bisa dirender. pip install pypdfium2")
        return summary

    summary["attempted"] = True
    summary["engine"] = name
    started = time.time()

    # Pagar pengaman: dokumen scan 500 halaman tidak boleh menyandera server.
    limited = targets[: max(1, int(max_pages))]
    if len(targets) > len(limited):
        summary["skipped"] = targets[len(limited):]

    try:
        images = render_pdf_pages(data, limited, dpi=dpi)
    except Exception as exc:  # noqa: BLE001
        summary["error"] = f"render halaman gagal: {type(exc).__name__}: {exc}"
        summary["duration_ms"] = round((time.time() - started) * 1000, 1)
        return summary

    by_page = {int(p["page"]): p for p in pages}
    confidences: list[float] = []
    for number, image in images.items():
        result = ocr_image(image, engine=name, deskew=deskew)
        if result.get("error"):
            summary["error"] = result["error"]
            continue
        text = (result.get("text") or "").strip()
        if not text:
            continue
        page = by_page.get(number)
        if page is None:
            continue
        # Jangan pernah menukar teks tertanam dengan hasil OCR yang lebih
        # miskin. Halaman dengan satu baris teks sah tetap lolos `needs_ocr`
        # (di bawah ambang), dan OCR halaman seperti itu bisa mengembalikan
        # potongan yang lebih pendek/rusak — menimpanya akan MENURUNKAN
        # kualitas index.
        existing = page.get("text") or ""
        if _alnum_len(text) <= _alnum_len(existing):
            summary["kept_embedded"] = summary.get("kept_embedded", 0) + 1
            continue
        page["text"] = text
        page["ocr"] = True
        page["ocr_confidence"] = result.get("confidence", 0.0)
        summary["pages_ocred"] += 1
        summary["chars_added"] += len(text)
        if result.get("confidence"):
            confidences.append(float(result["confidence"]))

    if confidences:
        summary["confidence"] = round(sum(confidences) / len(confidences), 4)
    summary["duration_ms"] = round((time.time() - started) * 1000, 1)
    return summary
