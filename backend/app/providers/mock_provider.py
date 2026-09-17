"""Deterministic offline provider used for tests and dependency-free demos.

Mimics a real agentic model: thinks, calls tools (search / diagram), then
answers — with fake streaming logprobs so the interpreter UI is fully testable.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
from typing import Any, AsyncIterator

from .base import BaseProvider, StreamEvent

_SEARCH_RE = re.compile(r"\b(cari|search|berita|news|harga|price|cuaca|weather)\b", re.I)
_DIAGRAM_RE = re.compile(r"\b(diagram|flowchart|alur|graph|graf|mindmap|skema)\b", re.I)
#: Mode yang dipilih user di composer → dikirim agent loop sebagai arah di
#: system prompt ("MODE: gambar" / "MODE: PPT"). Mock mengenali arah itu agar
#: demo offline menunjukkan alur tool generatif yang sama seperti provider nyata.
_IMAGE_MODE_RE = re.compile(r"MODE: gambar", re.I)
_PPT_MODE_RE = re.compile(r"MODE: PPT", re.I)


def _fake_logprobs(token: str) -> dict[str, Any]:
    return {
        "items": [
            {
                "token": token,
                "logprob": -0.08,
                "top": [
                    {"token": token, "logprob": -0.08},
                    {"token": "alternatif", "logprob": -2.71},
                    {"token": "opsi", "logprob": -3.94},
                ],
            }
        ]
    }


class MockProvider(BaseProvider):
    name = "mock"

    def model_label(self) -> str:
        return "mock-agent (offline demo)"

    def _wants(self, messages: list[dict[str, Any]]) -> dict[str, bool]:
        text = " ".join(
            m.get("content") or "" for m in messages if m.get("role") == "user"
        )
        system = " ".join(
            m.get("content") or "" for m in messages if m.get("role") == "system"
        )
        already_tool = any(m.get("role") == "tool" for m in messages)
        return {
            "search": bool(_SEARCH_RE.search(text)),
            "diagram": bool(_DIAGRAM_RE.search(text)),
            "image_mode": bool(_IMAGE_MODE_RE.search(system)),
            "ppt_mode": bool(_PPT_MODE_RE.search(system)),
            "already_tool": already_tool,
        }

    @staticmethod
    def _tool_payloads(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Payload JSON dari setiap pesan tool (role == "tool")."""
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.get("role") != "tool":
                continue
            try:
                data = json.loads(m.get("content") or "")
            except ValueError:
                continue
            if isinstance(data, dict):
                out.append(data)
        return out

    @staticmethod
    def _artifacts(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Artefak (gambar/PPT) yang benar-benar dibuat tool — tautan nyata."""
        out: list[dict[str, Any]] = []
        for data in MockProvider._tool_payloads(messages):
            art = data.get("artifact")
            if isinstance(art, dict) and art.get("url"):
                out.append(art)
        return out

    @staticmethod
    def _diagram_source(messages: list[dict[str, Any]]) -> str | None:
        """Ambil sumber Mermaid dari hasil tool create_diagram (bila ada)."""
        for data in MockProvider._tool_payloads(messages):
            if data.get("mermaid"):
                return str(data["mermaid"])
        return None

    @staticmethod
    def _search_hits(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Hasil web_search yang benar-benar ada — tidak pernah dikarang."""
        hits: list[dict[str, Any]] = []
        for data in MockProvider._tool_payloads(messages):
            for r in data.get("results") or []:
                if isinstance(r, dict) and r.get("url"):
                    hits.append(r)
        return hits

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        logprobs: bool = False,
        top_logprobs: int = 4,
    ) -> AsyncIterator[StreamEvent]:
        wants = self._wants(messages)
        user_text = " ".join(
            m.get("content") or "" for m in messages if m.get("role") == "user"
        ).strip()
        # Hanya tool yang benar-benar diiklankan boleh dipanggil — mode RAG
        # tidak memberi tool apa pun, jadi mock langsung menjawab dari konteks.
        tool_names = {t["function"]["name"] for t in tools or []}
        rag_context = any("DOCUMENT CONTEXT" in (m.get("content") or "")
                          for m in messages if m.get("role") == "system")
        await asyncio.sleep(0)

        if wants["search"] and "web_search" in tool_names and not wants["already_tool"]:
            yield StreamEvent(
                "thinking",
                {"text": "Pengguna meminta informasi terkini → saya perlu "
                          "memanggil tool web_search dulu, jangan menjawab dari "
                          "memori saja."},
            )
            yield StreamEvent(
                "tool_calls",
                {"calls": [{"id": "call_mock_1", "name": "web_search",
                            "arguments": {"query": "berita teknologi terkini"}}]},
            )
            yield StreamEvent("done", {"finish_reason": "tool_calls"})
            return

        if wants["diagram"] and "create_diagram" in tool_names and not wants["already_tool"]:
            yield StreamEvent(
                "thinking",
                {"text": "Ini permintaan visual → saya susun node & edge lalu "
                          "panggil create_diagram agar strukturnya valid."},
            )
            yield StreamEvent(
                "tool_calls",
                {"calls": [
                    {
                        "id": "call_mock_2",
                        "name": "create_diagram",
                        "arguments": {
                            "kind": "flowchart",
                            "title": "Alur Kerja Agent",
                            "nodes": [
                                {"id": "q", "label": "Pertanyaan user"},
                                {"id": "p", "label": "Rencana (thinking)"},
                                {"id": "t", "label": "Tool: browsing/diagram"},
                                {"id": "a", "label": "Jawaban + visual"},
                            ],
                            "edges": [
                                {"from": "q", "to": "p"},
                                {"from": "p", "to": "t", "label": "butuh data"},
                                {"from": "t", "to": "a"},
                                {"from": "p", "to": "a", "label": "langsung"},
                            ],
                        },
                    }
                ]},
            )
            yield StreamEvent("done", {"finish_reason": "tool_calls"})
            return

        if wants["image_mode"] and "generate_image" in tool_names and not wants["already_tool"]:
            yield StreamEvent(
                "thinking",
                {"text": "Mode gambar aktif → saya panggil generate_image "
                          "dengan prompt deskriptif dari permintaan user."},
            )
            yield StreamEvent(
                "tool_calls",
                {"calls": [{"id": "call_mock_img",
                            "name": "generate_image",
                            "arguments": {"prompt": text[:300] or "ilustrasi abstrak"}}]},
            )
            yield StreamEvent("done", {"finish_reason": "tool_calls"})
            return

        if wants["ppt_mode"] and "generate_ppt" in tool_names and not wants["already_tool"]:
            topic = (user_text[:80] or "Topik presentasi").strip()
            yield StreamEvent(
                "thinking",
                {"text": "Mode PPT aktif → saya susun outline lalu panggil "
                          "generate_ppt untuk membuat deck .pptx."},
            )
            yield StreamEvent(
                "tool_calls",
                {"calls": [{"id": "call_mock_ppt",
                            "name": "generate_ppt",
                            "arguments": {
                                "title": topic,
                                "slides": [
                                    {"title": "Latar belakang",
                                     "bullets": ["Konteks " + topic,
                                                 "Mengapa penting"]},
                                    {"title": "Rencana",
                                     "bullets": ["Langkah 1", "Langkah 2",
                                                 "Langkah 3"]},
                                    {"title": "Kesimpulan",
                                     "bullets": ["Ringkasan", "Langkah berikutnya"]},
                                ],
                            }}]},
            )
            yield StreamEvent("done", {"finish_reason": "tool_calls"})
            return

        # final answer turn
        yield StreamEvent(
            "thinking",
            {"text": "Konteks lengkap (termasuk hasil tool bila ada). "
                      "Saya rangkum menjadi jawaban akhir."},
        )
        hits = self._search_hits(messages)
        if rag_context:
            ctx_line = ""
            for m in messages:
                if m.get("role") == "system" and "DOCUMENT CONTEXT" in (m.get("content") or ""):
                    body = m["content"].split("[1]", 1)
                    ctx_line = ("[1]" + body[1])[:220].strip() if len(body) > 1 else ""
                    break
            answer = (
                "Berdasarkan dokumen yang diunggah: "
                + (ctx_line or "potongan relevan ditemukan")
                + " [1]. Jawaban ini murni dari konteks dokumen — bukan dari "
                  "pengetahuan umum model."
            )
        elif hits:
            # Hanya fakta yang benar-benar ada di payload yang boleh disitasi.
            first = hits[0]
            answer = (
                "Berikut ringkasan saya: agent Ask-Anything menerima pertanyaan, "
                "merencanakan langkah, memanggil tool bila perlu, lalu menyusun "
                "jawaban final. Hasil browsing berasal dari sumber bernomor, "
                f"mis. {str(first.get('title') or first.get('url'))[:60]} [1]."
            )
        else:
            answer = (
                "Berikut ringkasan saya: agent Ask-Anything menerima pertanyaan, "
                "merencanakan langkah, memanggil tool bila perlu, lalu menyusun "
                "jawaban final yang bisa memuat diagram Mermaid. "
                "Catatan: browsing belum menghasilkan data apa pun, jadi tidak "
                "ada klaim yang bisa disitasi pada jawaban ini."
            )
        artifacts_out = self._artifacts(messages)
        if artifacts_out:
            links = " · ".join(
                f"[{a.get('kind', 'artifact')}]({a.get('url', '#')})"
                for a in artifacts_out)
            answer += (
                f"\n\nArtefak siap diunduh: {links}. Semua tahap pembuatannya "
                "terekord di Mechanistic Interpreter."
            )
        diagram = self._diagram_source(messages)
        if diagram:
            answer = (
                "Diagram berikut dihasilkan tool **create_diagram** (bukan sumber "
                "web) dan dirender otomatis oleh UI — pilih mode **Graph** untuk "
                "versi interaktif:\n\n```mermaid\n"
                + diagram
                + "\n```\n\n"
                + answer
            )
        answer_words = answer.split(" ")
        for i, word in enumerate(answer_words):
            chunk = word if i == 0 else " " + word
            yield StreamEvent("delta", {"text": chunk})
            if logprobs and i % 3 == 0:
                yield StreamEvent("logprobs", _fake_logprobs(word))
            await asyncio.sleep(0.005)
        yield StreamEvent(
            "usage",
            {"prompt_tokens": 120, "completion_tokens": len(answer_words),
             "total_tokens": 120 + len(answer_words)},
        )
        yield StreamEvent("done", {"finish_reason": "stop"})
