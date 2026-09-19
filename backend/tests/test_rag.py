"""Tests: RAG pipeline end-to-end — PDF sintetis → parse → chunk → embed →
retrieve → generate (mock), plus gates policy dan endpoint upload."""
import json as _json

import pytest

from app import rag


# ---------------------------------------------------------------------------
# Helper: bangun PDF minimal yang valid (tanpa dependensi tambahan)
# ---------------------------------------------------------------------------

def make_pdf(page_texts: list[str]) -> bytes:
    """PDF 1..n halaman, masing-masing satu baris teks — cukup untuk pypdf."""
    objects: dict[int, bytes] = {}

    def stream_obj(text: str) -> bytes:
        content = (f"BT /F1 12 Tf 72 720 Td 14 TL ({text}) Tj ET").encode()
        return (f"<< /Length {len(content)} >>\nstream\n".encode() + content
                + b"\nendstream")

    n = len(page_texts)
    kids = " ".join(f"{4 + i * 2} 0 R" for i in range(n))
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = (f"<< /Type /Pages /Kids [{kids}] /Count {n} >>").encode()
    objects[3] = (b"<< /Type /Font /Subtype /Type1 "
                  b"/BaseFont /Helvetica >>")
    for i, text in enumerate(page_texts):
        page_no = 4 + i * 2
        content_no = page_no + 1
        objects[page_no] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_no} 0 R "
            f"/Resources << /Font << /F1 3 0 R >> >> >>").encode()
        objects[content_no] = stream_obj(text)

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for num in sorted(objects):
        offsets.append(len(out))
        out += f"{num} 0 obj\n".encode() + objects[num] + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF").encode()
    return bytes(out)


@pytest.fixture(autouse=True)
def _clean_rag(client):
    from app import db, governance

    # File uji di sini adalah PDF dengan teks tertanam: yang diuji adalah jalur
    # parse → chunk → embed, bukan OCR. Halaman uji sengaja pendek (satu baris)
    # sehingga lolos ambang `needs_ocr` dan akan memicu OCR sungguhan —
    # melambatkan suite tanpa menambah cakupan. OCR diuji di test_ocr.py.
    governance.update_policy({"rag": {"ocr_enabled": False}})
    for d in rag.list_documents():
        rag.delete_document(d["id"])
    yield
    for d in rag.list_documents():
        rag.delete_document(d["id"])
    db.execute("DELETE FROM admin_policy WHERE key='rag'")


def test_chunking_respects_size_and_pages():
    pages = [
        {"page": 1, "text": "Paragraf satu. " * 40 + "\n\nParagraf dua."},
        {"page": 2, "text": "Halaman dua isinya pendek."},
    ]
    chunks = rag.chunk_pages(pages, size=300, overlap=50)
    assert chunks, "harus menghasilkan chunk"
    assert all(len(c["text"]) <= 320 for c in chunks)
    assert any(c["page"] == 2 for c in chunks)          # halaman terpisah
    seqs = [c["seq"] for c in chunks]
    assert seqs == list(range(len(chunks)))


def test_hashing_embedder_deterministic_and_normalized():
    e1 = rag.HashingEmbedder().embed_one("retrieval augmented generation")
    e2 = rag.HashingEmbedder().embed_one("retrieval augmented generation")
    assert e1 == e2
    assert abs(sum(v * v for v in e1) - 1.0) < 1e-9     # L2-normalized
    unrelated = rag.HashingEmbedder().embed_one("kucing astronot")
    assert rag.cosine(e1, unrelated) < rag.cosine(e1, e2)


def test_ingest_and_retrieve_end_to_end(client):
    from app.config import settings
    pdf = make_pdf([
        "Kebijakan cuti karyawan: cuti tahunan 12 hari kerja dan dapat "
        "diakumulasi maksimal dua tahun.",
        "Klaim reimbursement medis diajukan melalui portal HR paling lambat "
        "30 hari setelah tanggal perawatan.",
    ])
    doc = rag.ingest_pdf(settings=settings,
                         filename="handbook.pdf", data=pdf)
    assert doc["status"] == "ready", doc
    assert doc["pages"] == 2 and doc["chunks"] >= 2
    assert doc["embed_backend"] == "hashing-v1"
    assert doc["timings"]["embed_ms"] >= 0

    hits = rag.retrieve("berapa lama cuti tahunan?", top_k=2)
    assert hits and "cuti" in hits[0]["text"].lower()
    assert hits[0]["score"] > 0.2
    assert hits[0]["doc_title"] == "handbook.pdf"

    # filter dokumen
    hits2 = rag.retrieve("cuti tahunan", top_k=4,
                         document_ids=["doc-tidak-ada"])
    assert hits2 == []

    # context block bernomor untuk prompt
    block = rag.context_block(hits)
    assert "[1]" in block and "[2]" in block


def test_rag_upload_and_query_sse(client):
    pdf = make_pdf([
        "Produk A diluncurkan 2024 dengan harga Rp10.000.",
        "Produk B adalah varian premium dengan garansi tiga tahun.",
    ])
    r = client.post("/api/rag/upload?wait=true",
                    files={"file": ("produk.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    doc = r.json()["document"]
    assert doc["status"] == "ready"
    assert doc["chunks"] >= 2

    # daftar dokumen
    docs = client.get("/api/rag/documents").json()["documents"]
    assert any(d["id"] == doc["id"] for d in docs)

    # query SSE: seluruh tahap muncul di trace (interpreter merecord semua)
    with client.stream("POST", "/api/rag/query",
                       json={"question": "berapa harga Produk A?"}) as resp:
        assert resp.status_code == 200
        evs = [_json.loads(l[6:]) for l in resp.iter_lines()
               if l.startswith("data: ")]
    types = [e["type"] for e in evs]
    assert "rag_stage" in types and "rag_retrieve" in types
    assert "prompt" in types and "delta" in types and "citations" in types
    ret = next(e for e in evs if e["type"] == "rag_retrieve")
    assert ret["hits"] and "Produk A" in ret["hits"][0]["preview"]
    cit = next(e for e in evs if e["type"] == "citations")
    assert cit["sources"][0]["url"].startswith("rag://")

    # percakapan RAG terecord di riwayat + trace bisa di-replay
    cid = next(e for e in evs if e["type"] == "start")["conversation_id"]
    conv = client.get(f"/api/conversations/{cid}").json()
    trace_types = {t["type"] for t in conv["trace"]}
    assert {"rag_stage", "rag_retrieve"} <= trace_types

    # delete dokumen → chunk ikut terhapus
    assert client.delete(f"/api/rag/documents/{doc['id']}").json()["ok"]
    assert rag.retrieve("Produk A") == []


def test_rag_upload_rejects_non_pdf_and_oversize(client):
    r = client.post("/api/rag/upload",
                    files={"file": ("catatan.txt", b"halo",
                                    "text/plain")})
    assert r.status_code == 415
    from app import governance
    old = governance.policy()["rag"]["max_upload_mb"]
    governance.update_policy({"rag": {"max_upload_mb": 0}})
    pdf = make_pdf(["kecil"])
    r2 = client.post("/api/rag/upload",
                     files={"file": ("kecil.pdf", pdf, "application/pdf")})
    assert r2.status_code == 413
    governance.update_policy({"rag": {"max_upload_mb": old}})


def test_rag_mode_disabled_is_gated(client):
    from app import governance
    pdf = make_pdf(["isi"])
    governance.update_policy({"modes": {"rag": False}})
    r = client.post("/api/rag/upload",
                    files={"file": ("d.pdf", pdf, "application/pdf")})
    assert r.status_code == 403
    with client.stream("POST", "/api/rag/query",
                       json={"question": "apa saja"}) as resp:
        body = "".join(resp.iter_lines())
    assert "dimatikan" in body
    governance.update_policy({"modes": {"rag": True}})
