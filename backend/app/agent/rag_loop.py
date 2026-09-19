"""RAG query loop — retrieve → generate dengan protokol trace yang sama
persis dengan agent chat, sehingga Mechanistic Interpreter menampilkan
seluruh pipeline RAG: embed query, retrieval (+skor), konteks terpasang,
sampling, token, sitasi.

Sengaja tidak memakai tool: mode RAG menjawab dari dokumen, jadi jejaknya
bersih dan auditnya lurus (setiap klaim → potongan dokumen bernomor).
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from .. import db, rag
from ..config import Settings
from ..providers import BaseProvider
from ..sources import SourceRegistry, finalize_answer
from .loop import _accumulate_usage, _preview

EmitFn = Any


async def run_rag_query(
    *,
    conversation_id: str,
    question: str,
    provider: BaseProvider,
    settings: Settings,
    emit: EmitFn,
    document_ids: list[str] | None = None,
    #: Snapshot kuota token end user — ikut direkam di trace (lihat loop.py).
    quota_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from ..governance import policy

    pol = policy()
    run_id = uuid.uuid4().hex[:8]
    seq = 0
    t0 = time.time()

    async def trace(type_: str, payload: dict[str, Any]) -> None:
        nonlocal seq
        payload = {"t_ms": round((time.time() - t0) * 1000, 1), "step": steps,
                   **payload}
        db.add_trace(conversation_id, run_id, seq, type_, payload)
        seq += 1
        await emit({"type": type_, "run_id": run_id, "seq": seq - 1, **payload})

    steps = 0
    db.add_message(conversation_id, "user", question)

    if quota_status:
        await trace("quota", dict(quota_status))

    await trace("meta", {
        "provider": provider.name,
        "model": provider.model_label(),
        "pipeline": "rag",
        "mode": "rag",
        "interpreter": {"always_on": True},
        "tools": [],
        "policy": {"modes": pol["modes"], "rag": pol["rag"]},
    })

    # ---- 1. embed query -----------------------------------------------------
    steps += 1
    t_embed = time.time()
    embedder = rag.HashingEmbedder()
    qv = embedder.embed_one(question)
    await trace("rag_stage", {
        "stage": "embed",
        "status": "ok",
        "backend": embedder.backend,
        "dim": len(qv),
        "message": f"Query di-embed ({embedder.backend}, {len(qv)} dim)",
        "duration_ms": round((time.time() - t_embed) * 1000, 1),
    })

    # ---- 2. retrieve --------------------------------------------------------
    steps += 1
    t_ret = time.time()
    top_k = int(pol["rag"]["top_k"])
    hits = rag.retrieve(question, top_k=top_k, document_ids=document_ids)
    await trace("rag_retrieve", {
        "stage": "retrieve",
        "status": "ok" if hits else "no-results",
        "top_k": top_k,
        "document_filter": document_ids or [],
        # Strategi retrieval ikut dibuka: pembaca Interpreter harus bisa tahu
        # KENAPA sebuah potongan terpilih (cosine, BM25, atau gabungannya).
        "strategy": {
            "mode": pol["rag"].get("retrieval_mode", "hybrid"),
            "candidates": pol["rag"].get("retrieval_candidates", 50),
            "mmr_lambda": pol["rag"].get("mmr_lambda", 0.7),
            "context_neighbors": pol["rag"].get("context_neighbors", 0),
            "fusion": "reciprocal-rank-fusion",
        },
        "hits": [{"doc_id": h["doc_id"], "doc_title": h["doc_title"],
                  "seq": h["seq"], "page": h["page"], "score": h["score"],
                  "scores": h.get("scores", {}),
                  "preview": _preview(h["text"], 140)} for h in hits],
        "message": (f"Retrieval: {len(hits)} potongan (top_k={top_k}, "
                    f"{pol['rag'].get('retrieval_mode', 'hybrid')})"
                    if hits else "Retrieval: 0 potongan cocok"),
        "duration_ms": round((time.time() - t_ret) * 1000, 1),
    })

    # ---- 3. context assembly ------------------------------------------------
    steps += 1
    context = rag.context_block(hits)
    sources = SourceRegistry()
    rag.register_hits(sources, hits)
    llm_messages = [
        {"role": "system", "content": rag.RAG_SYSTEM_PROMPT},
        {"role": "system", "content": context},
        {"role": "user", "content": question},
    ]
    await trace("prompt", {
        "system": rag.RAG_SYSTEM_PROMPT,
        "context": context,
        "messages": llm_messages,
        "tools": [],
        "message_count": len(llm_messages),
    })

    # ---- 4. generate (stream) ----------------------------------------------
    steps += 1
    answer_parts: list[str] = []
    thinking_parts: list[str] = []
    usage: dict[str, Any] = {}
    finish_reason = None
    gen_t0 = time.time()

    await trace("llm_request", {
        "messages": llm_messages,
        "message_count": len(llm_messages),
        "tools": [],
        "sampling": {"temperature": settings.temperature,
                     "max_tokens": settings.max_tokens},
    })
    async for ev in provider.stream(
        llm_messages, [],
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        logprobs=settings.logprobs,
        top_logprobs=settings.top_logprobs,
    ):
        if ev.type == "thinking":
            thinking_parts.append(ev.data["text"])
            await trace("thinking", {"text": ev.data["text"]})
        elif ev.type == "delta":
            answer_parts.append(ev.data["text"])
            await trace("delta", {"text": ev.data["text"]})
        elif ev.type == "logprobs":
            await trace("logprobs", ev.data)
        elif ev.type == "usage":
            _accumulate_usage(usage, ev.data)
            await trace("usage", ev.data)
        elif ev.type == "error":
            await trace("error", ev.data)
            return {"answer": "", "error": ev.data.get("message"),
                    "steps": steps, "hits": hits}
        elif ev.type == "done":
            finish_reason = ev.data.get("finish_reason")

    raw = "".join(answer_parts).strip()
    await trace("llm_response", {
        "text": raw,
        "text_preview": _preview(raw),
        "thinking": "".join(thinking_parts),
        "finish_reason": finish_reason,
        "chars": len(raw),
        "duration_ms": round((time.time() - gen_t0) * 1000, 1),
    })

    # ---- 5. citations (verifikasi [n] terhadap potongan dokumen) -----------
    answer, citations = finalize_answer(raw, sources)
    await trace("citations", {
        "status": citations["status"],
        "total": citations["total"],
        "cited": citations["cited"],
        "uncited": citations["uncited"],
        "invalid": citations["invalid"],
        "detail": citations["detail"],
        "sources": sources.to_dicts(),
    })

    elapsed = round((time.time() - t0) * 1000, 1)
    usage["latency_ms"] = elapsed
    usage["steps"] = steps
    await trace("done", {"answer": answer, "stopped_reason": "stop", **usage})

    assistant_msg = db.add_message(
        conversation_id, "assistant", answer,
        meta={"thinking": "".join(thinking_parts), "usage": usage,
              "stopped_reason": "stop", "mode": "rag",
              "sources": sources.to_dicts(), "citations": citations,
              "rag": {"hits": [{"doc_id": h["doc_id"],
                                "doc_title": h["doc_title"],
                                "page": h["page"], "score": h["score"]}
                               for h in hits],
                      "top_k": top_k, "backend": embedder.backend},
              },
    )
    return {"answer": answer, "steps": steps, "usage": usage, "run_id": run_id,
            "message_id": assistant_msg["id"], "citations": citations,
            "sources": sources.to_dicts(), "hits": hits, "error": None}


def to_jsonable(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)
