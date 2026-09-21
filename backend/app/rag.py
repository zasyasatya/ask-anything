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
    from .governance import policy

    pol = policy()["rag"]
    doc = create_document(filename, len(data), title)
    did = doc["id"]

    base = _raw_path(doc, settings).parent
    base.mkdir(parents=True, exist_ok=True)
    try:
        _raw_path(doc, settings).write_bytes(data)
    except OSError:
        pass  # arsip mentah opsional — jangan gagalkan pipeline

    timings: dict[str, float] = {}
    try:
        t0 = time.time()
        _set_status(did, "parsing")
        pages = parse_pdf(data)
        timings["parse_ms"] = round((time.time() - t0) * 1000, 1)

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
                    chunks=len(chunks), chars=chars, timings=json.dumps(timings))
    except Exception as exc:  # noqa: BLE001 - status error tampil di UI
        _set_status(did, "error", error=f"{type(exc).__name__}: {exc}")
    return get_document(did) or {}


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(query: str, top_k: int = 4,
             document_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Cari `top_k` chunk paling mirip (cosine) — murni SQL + python, tanpa
    server vector eksternal."""
    if not (query or "").strip():
        return []
    qv = HashingEmbedder().embed_one(query)
    sql = ("SELECT c.id, c.doc_id, c.seq, c.page, c.text, c.embedding, "
           "d.title AS doc_title, d.filename AS doc_filename "
           "FROM rag_chunks c JOIN rag_documents d ON d.id = c.doc_id "
           "WHERE d.status='ready'")
    params: list[Any] = []
    if document_ids:
        sql += f" AND c.doc_id IN ({','.join('?' * len(document_ids))})"
        params.extend(document_ids)
    rows = db.query_all(sql, tuple(params))

    scored: list[dict[str, Any]] = []
    for r in rows:
        try:
            emb = json.loads(r.pop("embedding") or "[]")
        except (TypeError, ValueError):
            continue
        if len(emb) != len(qv):
            continue
        score = cosine(qv, emb)
        if score > 0.01:
            scored.append({**r, "score": round(score, 4)})
    scored.sort(key=lambda h: h["score"], reverse=True)
    return scored[: max(1, int(top_k))]


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
