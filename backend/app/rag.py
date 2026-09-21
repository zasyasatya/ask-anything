"""RAG pipeline: upload PDF → parsing → chunking → embedding → index →
retrieve → generate. Semua tahap terecord (status dokumen + trace event di
Mechanistic Interpreter) supaya user melihat *cara* jawaban terbentuk.

Paket yang dipakai:
  pypdf            — parsing PDF teks per halaman (pure-python, tanpa binary).
  (fallback)       — bila pypdf tidak ada, upload ditolak dengan pesan install
                     yang jelas, bukan error diam-diam.

Embedding memakai **hashing embedder deterministik** (word unigram + bigram →
vektor 384-dim, L2-normalized): tanpa server, tanpa unduhan model, cocok untuk
retrieval leksikal. Antarmuka `Embedder` sengaja berupa protocol supaya
sentence-transformers / API embedding bisa dipasang tanpa mengubah pipeline.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from typing import Any, Iterable

from . import db

EMBED_DIM = 384
EMBED_BACKEND = "hashing-v1"

#: Prompt khusus mode RAG: jawaban wajib bersumber dari konteks dokumen.
RAG_SYSTEM_PROMPT = """You are **Ask Anything** dalam mode RAG (Retrieval-Augmented
Generation). Anda menjawab HANYA dari konteks dokumen yang diberikan.

Aturan:
1. Jawab berdasarkan potongan dokumen bernomor ([1], [2], …) yang tersedia.
2. CITASI WAJIB: tulis [n] tepat setelah kalimat yang didukung potongan n.
3. Jika konteks tidak memuat jawaban, katakan terus terang bahwa dokumen
   belum memuat informasi itu — jangan mengarang, jangan memakai angka sitasi
   yang tidak ada di daftar.
4. Jawab dalam bahasa user, ringkas dan terstruktur.
"""


# ---------------------------------------------------------------------------
# Embedder (protocol + implementasi hashing deterministik)
# ---------------------------------------------------------------------------

class Embedder:
    """Protocol kecil: embed(texts) → list[list[float]] (L2-normalized)."""

    backend: str = "abstract"

    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover
        raise NotImplementedError


class HashingEmbedder(Embedder):
    """Word unigram (1.0) + bigram (0.5) di-hash ke vektor tetap 384-dim.

    Deterministik & cepat: sama untuk teks yang sama di proses mana pun, jadi
    index yang dibuat saat upload tetap valid kapan pun di-query.
    """

    backend = EMBED_BACKEND

    def __init__(self, dim: int = EMBED_DIM) -> None:
        self.dim = dim

    def _slot(self, token: str) -> int:
        d = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(d, "big") % self.dim

    def _tokens(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9\u00c0-\u024f]{2,}", (text or "").lower())

    def embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        words = self._tokens(text)
        for w in words:
            vec[self._slot(w)] += 1.0
        for a, b in zip(words, words[1:]):
            vec[self._slot(f"{a}~{b}")] += 0.5
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(t) for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Retrieval leksikal (BM25) — pelengkap embedding
# ---------------------------------------------------------------------------
#: Kenapa perlu: embedder hashing memetakan token ke slot tetap, jadi dua kata
#: berbeda bisa bertabrakan di slot yang sama dan kata langka tidak diberi bobot
#: lebih. BM25 memberi bobot IDF (kata langka lebih menentukan) dan menormalkan
#: panjang dokumen — justru paling kuat untuk pertanyaan berisi nomor pasal,
#: nama orang, atau kode produk, yang sering muncul pada dokumen nyata.

_BM25_K1 = 1.5
_BM25_B = 0.75


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9\u00c0-\u024f]{2,}", (text or "").lower())


def bm25_scores(query: str, documents: list[str]) -> list[float]:
    """Skor BM25 query terhadap tiap dokumen (korpus = kandidat itu sendiri)."""
    import math

    query_terms = tokenize(query)
    if not query_terms or not documents:
        return [0.0] * len(documents)

    tokenised = [tokenize(d) for d in documents]
    lengths = [len(t) or 1 for t in tokenised]
    avg_len = sum(lengths) / len(lengths)
    counts: list[dict[str, int]] = []
    for tokens in tokenised:
        freq: dict[str, int] = {}
        for token in tokens:
            freq[token] = freq.get(token, 0) + 1
        counts.append(freq)

    total = len(documents)
    scores = [0.0] * total
    for term in set(query_terms):
        containing = sum(1 for freq in counts if term in freq)
        if containing == 0:
            continue
        idf = math.log(1 + (total - containing + 0.5) / (containing + 0.5))
        for i, freq in enumerate(counts):
            tf = freq.get(term, 0)
            if not tf:
                continue
            denominator = tf + _BM25_K1 * (
                1 - _BM25_B + _BM25_B * lengths[i] / avg_len)
            scores[i] += idf * (tf * (_BM25_K1 + 1)) / denominator
    return scores


def reciprocal_rank_fusion(rankings: list[list[int]], *, k: int = 60,
                           weights: list[float] | None = None) -> dict[int, float]:
    """Gabungkan beberapa peringkat memakai RRF.

    RRF dipakai alih-alih menjumlahkan skor mentah karena skala BM25 dan cosine
    tidak sebanding (BM25 tak berbatas, cosine 0–1): menormalkannya selalu
    rapuh terhadap outlier, sedangkan peringkat tidak.
    """
    weights = weights or [1.0] * len(rankings)
    fused: dict[int, float] = {}
    for ranking, weight in zip(rankings, weights):
        for rank, index in enumerate(ranking, start=1):
            fused[index] = fused.get(index, 0.0) + weight / (k + rank)
    return fused


def mmr_select(candidates: list[dict[str, Any]], *, top_k: int,
               lambda_: float = 0.7) -> list[dict[str, Any]]:
    """Maximal Marginal Relevance: relevan TAPI tidak saling duplikat.

    Tanpa ini top-k sering berisi beberapa chunk yang nyaris identik (overlap
    sliding window, atau paragraf yang berulang di beberapa halaman), sehingga
    konteks yang sampai ke model jadi sempit padahal kuotanya terpakai.
    """
    if top_k <= 0 or not candidates:
        return []
    lambda_ = min(1.0, max(0.0, float(lambda_)))
    remaining = list(candidates)
    selected: list[dict[str, Any]] = [remaining.pop(0)]
    while remaining and len(selected) < top_k:
        best_index, best_value = 0, None
        for i, candidate in enumerate(remaining):
            similarity = max(
                (cosine(candidate["_vec"], chosen["_vec"])
                 for chosen in selected if candidate.get("_vec")
                 and chosen.get("_vec")),
                default=0.0)
            value = lambda_ * candidate["_rel"] - (1 - lambda_) * similarity
            if best_value is None or value > best_value:
                best_index, best_value = i, value
        selected.append(remaining.pop(best_index))
    return selected


# ---------------------------------------------------------------------------
# PDF parsing + chunking
# ---------------------------------------------------------------------------

def parse_pdf(data: bytes) -> list[dict[str, Any]]:
    """Ekstrak teks per halaman: [{page (1-based), text}] — butuh pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - environment tanpa pypdf
        raise RuntimeError(
            "pypdf belum ter-install — jalankan: "
            "pip install -r backend/requirements.txt"
        ) from exc
    import io

    reader = PdfReader(io.BytesIO(data))
    pages: list[dict[str, Any]] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - halaman rusak tidak menggagalkan doc
            text = ""
        pages.append({"page": i, "text": text})
    return pages


def chunk_pages(pages: list[dict[str, Any]], size: int = 1200,
                overlap: int = 150) -> list[dict[str, Any]]:
    """Sliding window per halaman — chunk tidak memotong halaman, sehingga
    sitasi `[n]` selalu bisa menyebut nomor halaman yang benar."""
    size = max(200, int(size))
    overlap = max(0, min(int(overlap), size // 2))
    chunks: list[dict[str, Any]] = []

    def emit(buf: str, page: int) -> None:
        buf = buf.strip()
        if buf:
            chunks.append({"seq": len(chunks), "page": page, "text": buf})

    for p in pages:
        page_no = int(p["page"])
        for para in re.split(r"\n{2,}", p["text"]):
            para = para.strip()
            if not para:
                continue
            buf = ""
            # Paragraf yang lebih besar dari `size` di-hard-split (dengan overlap).
            while len(para) > size:
                emit(buf, page_no)
                buf = ""
                chunks.append({"seq": len(chunks), "page": page_no,
                               "text": para[:size].strip()})
                para = para[size - overlap:]
            if len(buf) + len(para) + 2 > size and buf:
                tail = buf[-overlap:] if overlap else ""
                emit(buf, page_no)
                buf = tail
            buf = f"{buf}\n\n{para}" if buf else para
        emit(buf, page_no)
    return chunks


# ---------------------------------------------------------------------------
# Document registry (status = progres pipeline yang terlihat di UI)
# ---------------------------------------------------------------------------

def create_document(filename: str, size_bytes: int, title: str = "") -> dict:
    did = uuid.uuid4().hex[:12]
    ts = db.now()
    db.execute(
        "INSERT INTO rag_documents(id,filename,title,size_bytes,status,"
        "created_at,updated_at) VALUES(?,?,?,?, 'uploaded', ?, ?)",
        (did, filename, title or filename, int(size_bytes), ts, ts),
    )
    return get_document(did) or {}


def _hydrate(row: dict | None) -> dict | None:
    if not row:
        return None
    try:
        row["timings"] = json.loads(row.get("timings") or "{}")
    except (TypeError, ValueError):
        row["timings"] = {}
    try:
        row["ocr_detail"] = json.loads(row.get("ocr_detail") or "{}")
    except (TypeError, ValueError):
        row["ocr_detail"] = {}
    return row


def get_document(doc_id: str) -> dict | None:
    return _hydrate(db.query_one("SELECT * FROM rag_documents WHERE id=?", (doc_id,)))


def list_documents() -> list[dict]:
    return [r for r in (_hydrate(r) for r in db.query_all(
        "SELECT * FROM rag_documents ORDER BY created_at DESC")) if r]


def _set_status(doc_id: str, status: str, error: str = "", **fields: Any) -> None:
    sets = ["status=?", "updated_at=?", "error=?"]
    params: list[Any] = [status, db.now(), error]
    for k, v in fields.items():
        sets.append(f"{k}=?")
        params.append(v)
    params.append(doc_id)
    db.execute(f"UPDATE rag_documents SET {', '.join(sets)} WHERE id=?",
               tuple(params))


def add_chunks(doc_id: str, chunks: list[dict[str, Any]],
               embeddings: list[list[float]]) -> int:
    rows = [(doc_id, c["seq"], c["page"], c["text"],
             json.dumps(embeddings[i])) for i, c in enumerate(chunks)]
    from .db import _c, _lock  # bulk insert dalam satu transaksi
    with _lock:
        _c().executemany(
            "INSERT INTO rag_chunks(doc_id,seq,page,text,embedding) "
            "VALUES(?,?,?,?,?)", rows)
        _c().commit()
    return len(rows)


def delete_document(doc_id: str, settings: Any | None = None) -> bool:
    doc = get_document(doc_id)
    if not doc:
        return False
    db.execute("DELETE FROM rag_chunks WHERE doc_id=?", (doc_id,))
    db.execute("DELETE FROM rag_documents WHERE id=?", (doc_id,))
    if settings is not None:
        try:
            _raw_path(doc, settings).unlink(missing_ok=True)
        except OSError:
            pass
    return True


def _raw_path(doc: dict, settings: Any):
    from pathlib import Path

    resolver = getattr(settings, "resolved_rag_dir", None)
    if callable(resolver):
        base = Path(resolver())
    else:  # pragma: no cover - settings tiruan di test lama
        from .config import PROJECT_ROOT
        base = Path(getattr(settings, "rag_dir", "data/rag"))
        if not base.is_absolute():
            base = PROJECT_ROOT / base
    return base / f"{doc['id']}_{doc['filename']}"


# ---------------------------------------------------------------------------
# Ingest: upload → parse → chunk → embed → index (status per tahap)
# ---------------------------------------------------------------------------

def ingest_pdf(*, settings: Any, filename: str, data: bytes,
               title: str = "") -> dict:
    """Jalankan seluruh pipeline ingest. Setiap tahap memperbarui status
    dokumen (terlihat di panel RAG) dan dicatat di `timings`."""
    doc = create_document(filename, len(data), title)
    return _process_pdf(doc["id"], settings=settings, data=data)


def _archive(doc_id: str, settings: Any, data: bytes) -> None:
    """Simpan berkas mentah (opsional — kegagalan tidak menggagalkan ingest)."""
    doc = get_document(doc_id)
    if not doc:
        return
    try:
        path = _raw_path(doc, settings)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    except OSError:
        pass


def _process_pdf(did: str, *, settings: Any, data: bytes) -> dict:
    from .governance import policy

    pol = policy()["rag"]
    _archive(did, settings, data)

    timings: dict[str, float] = {}
    try:
        t0 = time.time()
        _set_status(did, "parsing")
        pages = parse_pdf(data)
        timings["parse_ms"] = round((time.time() - t0) * 1000, 1)

        # ---- OCR: halaman hasil scan tidak punya lapisan teks --------------
        # Tanpa tahap ini dokumen scan masuk index sebagai halaman kosong:
        # statusnya "ready" tetapi tidak satu pun pertanyaan bisa dijawab.
        ocr_summary = _maybe_ocr(did, data, pages, pol)
        if ocr_summary.get("duration_ms"):
            timings["ocr_ms"] = ocr_summary["duration_ms"]

        t0 = time.time()
        _set_status(did, "chunking", pages=len(pages))
        chunks = chunk_pages(pages, pol["chunk_size"], pol["chunk_overlap"])
        timings["chunk_ms"] = round((time.time() - t0) * 1000, 1)

        t0 = time.time()
        _set_status(did, "embedding", chunks=len(chunks))
        embeddings = HashingEmbedder().embed([c["text"] for c in chunks])
        timings["embed_ms"] = round((time.time() - t0) * 1000, 1)

        t0 = time.time()
        add_chunks(did, chunks, embeddings)
        timings["index_ms"] = round((time.time() - t0) * 1000, 1)

        chars = sum(len(c["text"]) for c in chunks)
        _set_status(did, "ready", embed_backend=EMBED_BACKEND, pages=len(pages),
                    chunks=len(chunks), chars=chars, timings=json.dumps(timings),
                    ocr_pages=int(ocr_summary.get("pages_ocred") or 0),
                    ocr_engine=str(ocr_summary.get("engine") or ""),
                    ocr_confidence=float(ocr_summary.get("confidence") or 0.0),
                    ocr_detail=json.dumps(ocr_summary))
    except Exception as exc:  # noqa: BLE001 - status error tampil di UI
        _set_status(did, "error", error=f"{type(exc).__name__}: {exc}")
    return get_document(did) or {}


def _maybe_ocr(doc_id: str, data: bytes, pages: list[dict[str, Any]],
               pol: dict[str, Any]) -> dict[str, Any]:
    """Jalankan OCR untuk halaman tanpa teks (tidak pernah melempar)."""
    from . import ocr as ocr_engine

    if not pol.get("ocr_enabled", True):
        return {"attempted": False, "error": "OCR dimatikan admin"}
    scanned = [p for p in pages
               if ocr_engine.needs_ocr(p.get("text", ""),
                                       int(pol.get("ocr_min_chars") or 80))]
    if not scanned:
        return {"attempted": False, "pages_scanned": 0}

    _set_status(doc_id, "ocr")
    try:
        return ocr_engine.ocr_pdf(
            data, pages,
            min_chars=int(pol.get("ocr_min_chars") or 80),
            dpi=int(pol.get("ocr_dpi") or 200),
            max_pages=int(pol.get("ocr_max_pages") or 40),
            engine=str(pol.get("ocr_engine") or "auto"),
            deskew=bool(pol.get("ocr_deskew", True)),
        )
    except Exception as exc:  # noqa: BLE001 - OCR gagal ≠ dokumen gagal
        return {"attempted": True, "pages_ocred": 0,
                "error": f"{type(exc).__name__}: {exc}"}


#: Ekstensi gambar yang diterima pipeline RAG (semuanya lewat OCR).
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")


def ingest_image(*, settings: Any, filename: str, data: bytes,
                 title: str = "") -> dict:
    """Ingest berkas gambar (foto/scan lepas) — isinya murni dari OCR."""
    doc = create_document(filename, len(data), title)
    _set_status(doc["id"], "uploaded", kind="image")
    return _process_image(doc["id"], settings=settings, data=data)


def _process_image(did: str, *, settings: Any, data: bytes) -> dict:
    from . import ocr as ocr_engine
    from .governance import policy

    pol = policy()["rag"]
    _archive(did, settings, data)

    timings: dict[str, float] = {}
    try:
        if not pol.get("ocr_enabled", True):
            raise RuntimeError("OCR dimatikan admin — gambar tidak bisa dibaca")
        _set_status(did, "ocr", kind="image")
        t0 = time.time()
        result = ocr_engine.ocr_image_bytes(
            data, engine=str(pol.get("ocr_engine") or "auto"),
            deskew=bool(pol.get("ocr_deskew", True)))
        timings["ocr_ms"] = round((time.time() - t0) * 1000, 1)
        if result.get("error"):
            raise RuntimeError(result["error"])
        text = (result.get("text") or "").strip()
        if not text:
            raise RuntimeError("OCR tidak menemukan teks pada gambar ini")

        pages = [{"page": 1, "text": text, "ocr": True,
                  "ocr_confidence": result.get("confidence", 0.0)}]
        t0 = time.time()
        _set_status(did, "chunking", pages=1, kind="image")
        chunks = chunk_pages(pages, pol["chunk_size"], pol["chunk_overlap"])
        timings["chunk_ms"] = round((time.time() - t0) * 1000, 1)

        t0 = time.time()
        _set_status(did, "embedding", chunks=len(chunks), kind="image")
        embeddings = HashingEmbedder().embed([c["text"] for c in chunks])
        timings["embed_ms"] = round((time.time() - t0) * 1000, 1)
        add_chunks(did, chunks, embeddings)

        _set_status(did, "ready", kind="image", embed_backend=EMBED_BACKEND,
                    pages=1, chunks=len(chunks), chars=len(text),
                    timings=json.dumps(timings), ocr_pages=1,
                    ocr_engine=str(result.get("engine") or ""),
                    ocr_confidence=float(result.get("confidence") or 0.0),
                    ocr_detail=json.dumps({
                        "attempted": True, "pages_ocred": 1,
                        "engine": result.get("engine", ""),
                        "confidence": result.get("confidence", 0.0),
                        "line_count": result.get("line_count", 0),
                        "chars_added": len(text),
                    }))
    except Exception as exc:  # noqa: BLE001
        _set_status(did, "error", error=f"{type(exc).__name__}: {exc}",
                    kind="image")
    return get_document(did) or {}


def ingest_file(*, settings: Any, filename: str, data: bytes,
                title: str = "") -> dict:
    """Pintu masuk tunggal: pilih pipeline PDF atau gambar dari ekstensi."""
    lowered = (filename or "").lower()
    if lowered.endswith(IMAGE_EXTENSIONS):
        return ingest_image(settings=settings, filename=filename, data=data,
                            title=title)
    return ingest_pdf(settings=settings, filename=filename, data=data,
                      title=title)


def ingest_file_background(*, settings: Any, filename: str, data: bytes,
                           title: str = "") -> dict:
    """Daftarkan dokumen lalu proses di thread terpisah.

    OCR bersifat CPU-bound: satu halaman scan bisa memakan puluhan detik di
    CPU, sehingga dokumen 20 halaman akan melewati batas waktu request HTTP
    (dan proxy di depannya) bila dikerjakan inline. Dokumen dibuat lebih dulu
    dengan status `queued`; klien memantau kemajuannya lewat
    `GET /api/rag/documents` — status per tahap (`parsing` → `ocr` →
    `chunking` → `embedding` → `ready`) memang sudah ditampilkan panel RAG.
    """
    import threading

    lowered = (filename or "").lower()
    kind = "image" if lowered.endswith(IMAGE_EXTENSIONS) else "pdf"
    doc = create_document(filename, len(data), title)
    _set_status(doc["id"], "queued", kind=kind)

    def worker() -> None:
        try:
            _ingest_into(doc_id=doc["id"], settings=settings,
                         filename=filename, data=data, kind=kind)
        except BaseException as exc:  # noqa: BLE001 - thread tidak boleh diam
            _set_status(doc["id"], "error",
                        error=f"{type(exc).__name__}: {exc}", kind=kind)

    threading.Thread(target=worker, name=f"rag-ingest-{doc['id'][:6]}",
                     daemon=True).start()
    return get_document(doc["id"]) or {}


def _ingest_into(*, doc_id: str, settings: Any, filename: str, data: bytes,
                 kind: str) -> dict:
    """Proses dokumen yang SUDAH terdaftar (dipakai jalur background)."""
    if kind == "image":
        return _process_image(doc_id, settings=settings, data=data)
    return _process_pdf(doc_id, settings=settings, data=data)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(query: str, top_k: int = 4,
             document_ids: list[str] | None = None,
             *, mode: str | None = None, candidates: int | None = None,
             mmr_lambda: float | None = None,
             min_score: float | None = None,
             neighbors: int | None = None) -> list[dict[str, Any]]:
    """Retrieval hibrida: embedding + BM25 → RRF → MMR → perluasan konteks.

    Tahapannya, dan alasan tiap tahap ada:

    1. **Dua pencari**. Cosine pada embedding menangkap kemiripan parafrasa;
       BM25 menangkap istilah persis (nomor pasal, kode produk, nama) yang
       justru paling sering ditanyakan dan paling mudah hilang pada embedder
       hashing karena tabrakan slot.
    2. **RRF** menggabungkan keduanya lewat peringkat, bukan skor mentah, karena
       skala BM25 dan cosine tidak sebanding.
    3. **MMR** membuang hasil yang saling duplikat, sehingga `top_k` berisi
       potongan yang benar-benar berbeda.
    4. **Tetangga** (opsional) menambahkan chunk sebelum/sesudahnya agar kalimat
       yang terpotong batas chunk tetap utuh saat dibaca model.

    Nilai kembalian tetap berbentuk seperti sebelumnya (`score`, `text`,
    `page`, `doc_title`, …) dengan tambahan `scores` (rincian per pencari)
    supaya keputusan retrieval terlihat di Mechanistic Interpreter.
    """
    if not (query or "").strip():
        return []

    from .governance import policy

    pol = policy()["rag"]
    mode = (mode or pol.get("retrieval_mode") or "hybrid").strip().lower()
    candidates = int(candidates or pol.get("retrieval_candidates") or 50)
    mmr_lambda = float(pol.get("mmr_lambda", 0.7) if mmr_lambda is None
                       else mmr_lambda)
    min_score = float(pol.get("min_score", 0.0) if min_score is None
                      else min_score)
    neighbors = int(pol.get("context_neighbors", 0) if neighbors is None
                    else neighbors)
    top_k = max(1, int(top_k))

    rows = _candidate_rows(document_ids)
    if not rows:
        return []

    embedder = HashingEmbedder()
    query_vector = embedder.embed_one(query)

    vector_scores: list[float] = []
    for row in rows:
        vector = row.get("_vec") or []
        vector_scores.append(cosine(query_vector, vector) if len(vector)
                             == len(query_vector) else 0.0)
    lexical_scores = bm25_scores(query, [row["text"] for row in rows])

    order = list(range(len(rows)))
    if mode == "vector":
        fused = {i: vector_scores[i] for i in order}
    elif mode == "lexical":
        fused = {i: lexical_scores[i] for i in order}
    else:
        by_vector = sorted(order, key=lambda i: vector_scores[i], reverse=True)
        by_lexical = sorted(order, key=lambda i: lexical_scores[i], reverse=True)
        fused = reciprocal_rank_fusion([by_vector, by_lexical])

    ranked = sorted(order, key=lambda i: fused.get(i, 0.0), reverse=True)
    # Buang kandidat yang tidak tersentuh sama sekali oleh kedua pencari:
    # tanpa ini MMR bisa memasukkan chunk acak hanya demi keberagaman.
    ranked = [i for i in ranked
              if vector_scores[i] > 0.01 or lexical_scores[i] > 0.0]
    if not ranked:
        return []
    ranked = ranked[: max(top_k, candidates)]

    pool: list[dict[str, Any]] = []
    for i in ranked:
        row = dict(rows[i])
        row["_rel"] = float(fused.get(i, 0.0))
        row["scores"] = {
            "vector": round(vector_scores[i], 4),
            "lexical": round(lexical_scores[i], 4),
            "fused": round(float(fused.get(i, 0.0)), 6),
        }
        pool.append(row)

    chosen = mmr_select(pool, top_k=top_k, lambda_=mmr_lambda)

    out: list[dict[str, Any]] = []
    for row in chosen:
        # `score` dipertahankan sebagai cosine agar angkanya tetap punya arti
        # yang sama seperti sebelumnya untuk pembaca UI (0–1).
        score = round(float(row["scores"]["vector"]), 4)
        if score < min_score and row["scores"]["lexical"] <= 0:
            continue
        row.pop("_rel", None)
        row.pop("_vec", None)
        row["score"] = score
        row["retrieval_mode"] = mode
        if neighbors > 0:
            row["text"] = _with_neighbours(row, neighbors)
        out.append(row)
    return out


def _candidate_rows(document_ids: list[str] | None) -> list[dict[str, Any]]:
    sql = ("SELECT c.id, c.doc_id, c.seq, c.page, c.text, c.embedding, "
           "d.title AS doc_title, d.filename AS doc_filename "
           "FROM rag_chunks c JOIN rag_documents d ON d.id = c.doc_id "
           "WHERE d.status='ready'")
    params: list[Any] = []
    if document_ids:
        sql += f" AND c.doc_id IN ({','.join('?' * len(document_ids))})"
        params.extend(document_ids)
    rows = db.query_all(sql, tuple(params))
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            row["_vec"] = json.loads(row.pop("embedding") or "[]")
        except (TypeError, ValueError):
            row["_vec"] = []
        out.append(row)
    return out


def _with_neighbours(hit: dict[str, Any], span: int) -> str:
    """Sambung chunk tetangga agar kalimat yang terpotong batas chunk utuh."""
    rows = db.query_all(
        "SELECT seq, text FROM rag_chunks WHERE doc_id=? AND seq BETWEEN ? AND ? "
        "ORDER BY seq", (hit["doc_id"], int(hit["seq"]) - span,
                         int(hit["seq"]) + span))
    if not rows:
        return hit["text"]
    return "\n\n".join(r["text"] for r in rows)


def context_block(hits: list[dict[str, Any]], max_chars_per_hit: int = 1600) -> str:
    """Potongan hasil retrieval jadi blok bernomor untuk prompt."""
    if not hits:
        return ("DOCUMENT CONTEXT: no matching passages were found in the "
                "indexed documents. Say so plainly and do not invent content.")
    lines = ["DOCUMENT CONTEXT (numbered passages from the uploaded PDFs). "
             "Cite with [n]:", ""]
    for i, h in enumerate(hits, start=1):
        text = h["text"][:max_chars_per_hit]
        more = " …" if len(h["text"]) > max_chars_per_hit else ""
        lines.append(f"[{i}] {h['doc_title']} — halaman {h['page']}\n{text}{more}")
        lines.append("")
    return "\n".join(lines)


def register_hits(sources, hits: list[dict[str, Any]]) -> int:
    """Daftarkan hits ke SourceRegistry (url `rag://…` supaya sitasi & bar
    sumber di UI bekerja persis seperti bukti browser)."""
    added = 0
    for h in hits:
        before = len(sources.items)
        sources.add(
            f"rag://{h['doc_id']}#chunk-{h['seq']}",
            title=f"{h['doc_title']} (hal. {h['page']})",
            tool="rag",
            snippet=h["text"][:400],
            read=True,
        )
        added += len(sources.items) - before
    return added
