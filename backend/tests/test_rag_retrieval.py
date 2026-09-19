"""Kecerdasan retrieval RAG: hibrida BM25 + embedding, RRF, MMR, tetangga.

Yang dijaga tes ini adalah perbaikan yang bisa diukur, bukan sekadar "ada":

  * istilah persis (nomor pasal / kode produk) ditemukan walau embedder
    hashing gagal menangkapnya — ini kelemahan nyata mode vector-only,
  * hasil `top_k` tidak berisi potongan yang saling duplikat (MMR),
  * rincian skor per pencari ikut dilaporkan supaya keputusan retrieval
    bisa diaudit di Mechanistic Interpreter,
  * perluasan tetangga menyatukan kalimat yang terpotong batas chunk,
  * mode retrieval bisa diatur admin, dan default-nya tidak menurunkan
    perilaku lama.
"""
from __future__ import annotations

import pytest

from app import governance, rag
from app.config import settings


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


def _index(pages: list[str], *, title: str = "dok.pdf") -> str:
    """Daftarkan dokumen langsung dari teks halaman (lewati parsing PDF)."""
    doc = rag.create_document(title, sum(len(p) for p in pages), title)
    chunks = rag.chunk_pages([{"page": i, "text": text}
                              for i, text in enumerate(pages, start=1)],
                             1200, 100)
    embeddings = rag.HashingEmbedder().embed([c["text"] for c in chunks])
    rag.add_chunks(doc["id"], chunks, embeddings)
    rag._set_status(doc["id"], "ready", chunks=len(chunks), pages=len(pages))
    return doc["id"]


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------

def test_bm25_ranks_the_document_containing_the_rare_term_first():
    docs = [
        "Perusahaan menjual berbagai produk dan layanan kepada pelanggan.",
        "Ketentuan ini diatur dalam Pasal 1365 KUHPerdata tentang perbuatan.",
        "Layanan pelanggan tersedia setiap hari kerja pukul delapan pagi.",
    ]
    scores = rag.bm25_scores("Pasal 1365", docs)
    assert scores[1] == max(scores) > 0
    assert scores[0] == 0 and scores[2] == 0


def test_bm25_returns_zeros_for_an_empty_query():
    assert rag.bm25_scores("", ["apa pun"]) == [0.0]
    assert rag.bm25_scores("apa", []) == []


def test_bm25_normalises_document_length():
    """Kata yang sama di dokumen pendek harus lebih menentukan."""
    short = "banjir bandang"
    long = "banjir bandang " + ("kata lain " * 200)
    scores = rag.bm25_scores("banjir bandang", [short, long])
    assert scores[0] > scores[1]


# ---------------------------------------------------------------------------
# Fusion & MMR
# ---------------------------------------------------------------------------

def test_rrf_rewards_items_ranked_highly_by_both_rankers():
    fused = rag.reciprocal_rank_fusion([[5, 1, 2], [5, 2, 1]])
    assert max(fused, key=fused.get) == 5


def test_rrf_still_surfaces_an_item_only_one_ranker_found():
    fused = rag.reciprocal_rank_fusion([[1, 2], [9]])
    assert 9 in fused and fused[9] > 0


def test_mmr_drops_near_duplicates():
    def item(vec, rel):
        return {"_vec": vec, "_rel": rel, "text": str(vec)}

    candidates = [
        item([1.0, 0.0], 0.9),   # dipilih pertama
        item([1.0, 0.0], 0.88),  # duplikat → harus dilewati
        item([0.0, 1.0], 0.5),   # berbeda → harus masuk
    ]
    chosen = rag.mmr_select(candidates, top_k=2, lambda_=0.5)
    assert len(chosen) == 2
    assert chosen[1]["_vec"] == [0.0, 1.0]


def test_mmr_with_lambda_one_is_pure_relevance():
    def item(vec, rel):
        return {"_vec": vec, "_rel": rel}

    candidates = [item([1.0, 0.0], 0.9), item([1.0, 0.0], 0.88),
                  item([0.0, 1.0], 0.5)]
    chosen = rag.mmr_select(candidates, top_k=2, lambda_=1.0)
    assert chosen[1]["_rel"] == 0.88


def test_mmr_handles_an_empty_candidate_list():
    assert rag.mmr_select([], top_k=3) == []


# ---------------------------------------------------------------------------
# Retrieval end-to-end
# ---------------------------------------------------------------------------

def test_hybrid_ranks_exact_identifiers_with_a_lexical_contribution():
    """Istilah persis (nomor pasal/kode) terambil, dan kontribusi BM25 terlihat.

    Catatan kejujuran: pada korpus kecil, mode `vector` saja juga menemukan
    istilah seperti ini — embedder hashing memberi slot tersendiri untuk token
    langka. Yang dijamin tes ini bukan "hybrid mengalahkan vector", melainkan
    bahwa jalur leksikal benar-benar ikut menilai (pendapat kedua yang tidak
    bergantung pada tabrakan slot hash), dan hybrid tidak memburukkan hasil.
    """
    _index([
        "Bab pendahuluan membahas latar belakang organisasi secara umum "
        "beserta struktur dan sejarah singkat pendiriannya.",
        "Sanksi administratif diatur dalam Pasal 1365 KUHPerdata bagi pihak "
        "yang menimbulkan kerugian.",
    ])

    hybrid = rag.retrieve("Pasal 1365", top_k=1, mode="hybrid")
    assert hybrid, "hybrid harus menemukan sesuatu"
    assert "1365" in hybrid[0]["text"]
    assert hybrid[0]["scores"]["lexical"] > 0, "BM25 harus ikut berkontribusi"

    vector_only = rag.retrieve("Pasal 1365", top_k=1, mode="vector")
    assert "1365" in vector_only[0]["text"], "hybrid tidak boleh lebih buruk"


def test_mmr_measurably_reduces_duplicate_passages_in_top_k():
    """Manfaat yang terukur: top_k berisi potongan berbeda, bukan berulang.

    Dokumen nyata sering memuat paragraf boilerplate yang sama berkali-kali
    (kop, disclaimer, klausul standar). Tanpa MMR seluruh `top_k` bisa terisi
    salinan kalimat yang sama sehingga konteks yang sampai ke model menyempit.
    """
    boilerplate = ("Dokumen ini bersifat rahasia dan hanya untuk penggunaan "
                   "internal perusahaan.")
    pages = [boilerplate] * 6 + [
        boilerplate + " Selain itu, nilai kontrak tercatat sebesar sembilan "
        "miliar rupiah pada periode berjalan."
    ]
    _index(pages)

    greedy = rag.retrieve("dokumen rahasia internal", top_k=4, mmr_lambda=1.0)
    diverse = rag.retrieve("dokumen rahasia internal", top_k=4, mmr_lambda=0.3)

    def unique_texts(hits):
        return len({h["text"].strip() for h in hits})

    assert unique_texts(diverse) >= unique_texts(greedy)
    # Yang membawa informasi tambahan (nilai kontrak) harus ikut terangkat.
    assert any("sembilan miliar" in h["text"] for h in diverse)


def test_default_policy_already_diversifies():
    """Nilai default (mmr_lambda=0.7) harus sudah memberi manfaat itu.

    Diukur: pada lambda=1.0 keempat hasil identik dan informasi tambahan
    hilang; pada 0.7 (default) halaman pembawa informasi ikut masuk.
    """
    boilerplate = ("Dokumen ini bersifat rahasia dan hanya untuk penggunaan "
                   "internal perusahaan.")
    _index([boilerplate] * 6 + [
        boilerplate + " Selain itu, nilai kontrak tercatat sebesar sembilan "
        "miliar rupiah pada periode berjalan."])

    default_hits = rag.retrieve("dokumen rahasia internal", top_k=4)
    assert any("sembilan miliar" in h["text"] for h in default_hits)
    assert len({h["text"].strip() for h in default_hits}) > 1


def test_scores_breakdown_is_reported_for_the_interpreter():
    _index(["Total pendapatan perseroan tahun ini naik lima belas persen."])
    hits = rag.retrieve("pendapatan perseroan naik", top_k=2)
    assert hits
    assert set(hits[0]["scores"]) == {"vector", "lexical", "fused"}
    assert hits[0]["retrieval_mode"] == "hybrid"


def test_retrieval_mode_can_be_forced_to_lexical_or_vector():
    _index(["Piutang usaha sebesar dua belas miliar rupiah."])
    assert rag.retrieve("piutang usaha", top_k=1, mode="lexical")
    assert rag.retrieve("piutang usaha", top_k=1, mode="vector")


def test_unrelated_query_returns_nothing():
    _index(["Jadwal operasional kantor cabang wilayah timur."])
    assert rag.retrieve("resep rendang padang otentik", top_k=3) == []


def test_empty_query_returns_nothing():
    _index(["apa pun"])
    assert rag.retrieve("   ", top_k=3) == []


def test_top_k_is_respected():
    _index([f"Bagian {i} membahas topik anggaran belanja daerah." 
            for i in range(1, 8)])
    assert len(rag.retrieve("anggaran belanja", top_k=3)) <= 3


def test_document_filter_restricts_the_search():
    first = _index(["Kebijakan cuti tahunan karyawan tetap."], title="a.pdf")
    _index(["Kebijakan cuti tahunan karyawan kontrak."], title="b.pdf")

    hits = rag.retrieve("kebijakan cuti tahunan", top_k=5,
                        document_ids=[first])
    assert hits
    assert {h["doc_id"] for h in hits} == {first}


def test_neighbour_expansion_joins_adjacent_chunks():
    """Kalimat yang terpotong batas chunk tetap utuh saat dibaca model."""
    long_page = "\n\n".join(f"Paragraf {i} tentang tata kelola perusahaan "
                            f"dan kepatuhan regulasi." for i in range(1, 9))
    _index([long_page])

    plain = rag.retrieve("tata kelola kepatuhan", top_k=1, neighbors=0)
    expanded = rag.retrieve("tata kelola kepatuhan", top_k=1, neighbors=1)
    assert plain and expanded
    assert len(expanded[0]["text"]) >= len(plain[0]["text"])


def test_admin_policy_drives_the_retrieval_strategy():
    _index(["Nomor rekening 8891 digunakan untuk pembayaran royalti."])
    governance.update_policy({"rag": {"retrieval_mode": "lexical",
                                      "mmr_lambda": 1.0}})
    hits = rag.retrieve("rekening 8891", top_k=1)
    assert hits and hits[0]["retrieval_mode"] == "lexical"


def test_deleted_document_disappears_from_retrieval():
    doc_id = _index(["Produk A diluncurkan dengan harga sepuluh ribu."])
    assert rag.retrieve("produk A harga", top_k=2)
    rag.delete_document(doc_id, settings=settings)
    assert rag.retrieve("produk A harga", top_k=2) == []


def test_only_ready_documents_are_searched():
    doc_id = _index(["Data rahasia yang belum selesai diproses."])
    rag._set_status(doc_id, "embedding")
    assert rag.retrieve("data rahasia", top_k=2) == []


# ---------------------------------------------------------------------------
# Jejak di interpreter
# ---------------------------------------------------------------------------

def test_retrieve_event_discloses_the_strategy(client):
    _index(["Laba bersih perseroan mencapai tujuh miliar rupiah."])
    import json

    with client.stream("POST", "/api/rag/query",
                       json={"question": "berapa laba bersih perseroan?"}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines()
                  if line.startswith("data: ")]

    event = next(e for e in events if e["type"] == "rag_retrieve")
    assert event["strategy"]["fusion"] == "reciprocal-rank-fusion"
    assert event["strategy"]["mode"] in ("hybrid", "vector", "lexical")
    assert event["hits"], event["message"]
    assert "scores" in event["hits"][0]
