import type { Metadata } from "next";
import {
  C,
  Code,
  DocShell,
  H2,
  H3,
  Note,
  OL,
  P,
  Shot,
  Table,
  UL,
} from "@/components/docs/DocShell";

export const metadata: Metadata = {
  title: "Docs Developer — Ask Anything",
  description:
    "Arsitektur, API SSE, agent loop & tracing, provider/tools registry, setup dev, testing, dan pipeline screenshot dokumentasi Ask Anything.",
};

const TOC: Array<[string, string]> = [
  ["arsitektur", "Arsitektur"],
  ["repo", "Struktur repo"],
  ["setup", "Setup lingkungan dev"],
  ["test", "Menjalankan & testing"],
  ["api", "HTTP API & event SSE"],
  ["loop", "Agent loop & tracing"],
  ["providers", "Providers"],
  ["tools", "Tools registry"],
  ["frontend", "Frontend"],
  ["screenshots", "Pipeline screenshot docs"],
  ["env", "Referensi env"],
  ["troubleshoot", "Troubleshooting dev"],
];

export default function DeveloperPage() {
  return (
    <DocShell
      active="developer"
      title="Docs Developer"
      subtitle="Peta lengkap codebase untuk kontributor: aliran data SSE, schema tracing, cara menambah provider/tool, dan cara me-regenerate screenshot dokumentasi."
      toc={TOC}
    >
      <section className="space-y-4">
        <H2 id="arsitektur">1. Arsitektur</H2>
        <P>
          Monolith FastAPI berbicara SSE dengan frontend Next.js. Agent loop berada di backend;
          provider (HuggingFace lokal / OpenAI / mock) dan tools (search, fetch, diagram,
          calculator) di-plug lewat registry schema-driven.
        </P>
        <Code>{`┌──────────────┐   SSE (/api/chat)   ┌──────────────────────────────┐
│  Next.js UI  │ ◄────────────────── │  FastAPI backend (monolith)  │
│  + Mermaid   │ ──────────────────► │  agent loop + tools + trace  │
└──────────────┘      POST           │        │            │       │
                                     │   providers         tools   │
                                     │  hf / openai / mock  search │
                                     │        │             fetch  │
                                     │        ▼             diagram│
                                     │  models/<repo>       calc   │
                                     │  (transformers in-process)  │
                                     └──────────────────────────────┘`}</Code>
        <UL
          items={[
            <>Backend: <C>backend/app/</C> — FastAPI + SQLite (conversations, messages, trace_events).</>,
            <>Frontend: <C>frontend/</C> — Next.js 16 App Router, Tailwind, mermaid untuk render diagram.</>,
            <>Demo: <C>scripts/fake_llama_server.py</C> mengemulasi server OpenAI-compatible (wire-format SSE lengkap: think block, tool_calls dicicil, logprobs, usage).</>,
          ]}
        />
        <Shot
          src="/docs-images/04-chat-diagram-interpreter.png"
          alt="UI dengan interpreter"
          caption="Satu run lengkap: tool_call create_diagram → tool_result (Mermaid) → jawaban final; setiap event juga masuk trace_events untuk replay."
        />
      </section>

      <section className="space-y-4">
        <H2 id="repo">2. Struktur repo</H2>
        <Code>{`run.py / run.bat / run.sh      # launcher: cek+install dependensi, jalankan BE+FE
backend/
  app/
    main.py                  # FastAPI app + mount /slides & /docs-images
    config.py                # pydantic-settings (prefix ASK_*)
    db.py                    # SQLite: conversations, messages, trace_events
    providers/               # base / openai / huggingface / mock
    tools/                   # web_search, fetch_url, diagrams, calculator
    agent/                   # loop.py (agent+tracing), prompts.py
    api/routes.py            # /api/chat (SSE), conversations, settings, health
  tests/                     # pytest: provider SSE parser, agent, tools, API
scripts/
  fake_llama_server.py       # server OpenAI-compatible tiruan (--demo & testing)
  capture_screenshots.py     # generator screenshot docs (Playwright)
docs/                        # METODOLOGI.md, slides, PANDUAN-*, images/
frontend/                    # Next.js 16: sidebar, hero, chat, interpreter, docs`}</Code>
      </section>

      <section className="space-y-4">
        <H2 id="setup">3. Setup lingkungan dev</H2>
        <Code>{`# backend
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
ASK_PROVIDER=mock .venv/bin/python -m uvicorn backend.app.main:app --port 8000

# frontend
cd frontend && npm install && npx next dev -p 3000

# atau satu perintah (cek+install otomatis):
python3 run.py            # tambah --demo untuk emulator LLM di :8081`}</Code>
        <Note>
          Dev server Next 16 memblokir dev-resources cross-origin. Repo sudah menyetel{" "}
          <C>allowedDevOrigins</C> di <C>next.config.ts</C> (127.0.0.1 + *.e2b.app) agar UI hydrate
          saat diakses dari host preview/sandbox.
        </Note>
      </section>

      <section className="space-y-4">
        <H2 id="test">4. Menjalankan &amp; testing</H2>
        <Code>{`.venv/bin/python -m pytest backend/tests -q   # 15 passed
cd frontend && npx tsc --noEmit && npx next build
python3 run.py --demo                          # E2E live (emulator LLM)`}</Code>
        <Table
          head={["File test", "Cakupan"]}
          rows={[
            ["test_providers.py", "Parser SSE protokol OpenAI: think-block terbelah, akumulasi tool_calls.arguments, logprobs, usage."],
            ["test_api.py", "Endpoint /api/chat end-to-end via TestClient: event SSE + persist trace (prompt, tool_call, logprobs)."],
            ["test_tools.py", "Validasi diagram Mermaid, keamanan calculator (AST), ekstraksi fetch_url."],
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="api">5. HTTP API &amp; event SSE</H2>
        <Table
          head={["Method", "Path", "Kegunaan"]}
          rows={[
            ["POST", "/api/chat", "Stream satu run agent (SSE). Body: {message, conversation_id?}."],
            ["GET", "/api/conversations", "Daftar percakapan (untuk sidebar)."],
            ["GET", "/api/conversations/{id}", "Messages + trace lengkap (replay Interpreter)."],
            ["DELETE", "/api/conversations/{id}", "Hapus percakapan."],
            ["GET/POST", "/api/settings", "Baca/ubah runtime settings (provider, base url, model, temperature)."],
            ["GET", "/api/health", "Status backend + llm_reachable (untuk banner & indikator sidebar)."],
            ["GET", "/docs (backend)", "Swagger UI FastAPI; /slides/* & /docs-images/* static mount."],
          ]}
        />
        <H3>Event SSE (urutan khas satu run)</H3>
        <Table
          head={["type", "Payload penting", "Konsumsi UI"]}
          rows={[
            ["start", "conversation_id", "page.tsx: set active id"],
            ["meta", "provider, model, temperature, max_steps, logprobs", "Interpreter Metrics"],
            ["prompt", "system, messages, tools", "Interpreter Prompt"],
            ["thinking", "text (stream)", "kotak 💭 + Timeline"],
            ["delta", "text (stream)", "jawaban markdown"],
            ["logprobs", "items[{token, prob, top[]}]", "Interpreter Tokens"],
            ["tool_call", "id, name, arguments mentah", "chip tool + Timeline"],
            ["tool_result", "id, name, summary, data", "chip ✓ + Timeline"],
            ["usage", "prompt/completion/total tokens", "Metrics"],
            ["done", "answer, latency_ms, steps", "selesai + persist"],
            ["error", "message", "banner inline & Timeline"],
          ]}
        />
        <Code>{`curl -N localhost:8000/api/chat -H 'Content-Type: application/json' \\
     -d '{"message":"Buatkan diagram alur proses registrasi pengguna"}'`}</Code>
      </section>

      <section className="space-y-4">
        <H2 id="loop">6. Agent loop &amp; tracing</H2>
        <OL
          items={[
            <>routes.py membuat conversation (bila baru) + asyncio.Queue; task agent dijalankan terpisah agar klien putus = cancel.</>,
            <>loop.py merakit messages (history SQLite → protokol OpenAI, termasuk role tool & assistant_toolcalls), emit event <C>prompt</C>, lalu stream dari provider.</>,
            <>Bila model emit tool_calls (maks <C>ASK_MAX_STEPS</C>): emit <C>tool_call</C>, eksekusi via registry (timeout 30 dtk), emit <C>tool_result</C>, messages += assistant(tool_calls) + role:tool + hint sistem, lalu stream lagi.</>,
            <>Setiap event ditulis ke tabel <C>trace_events(conversation_id, run_id, seq, type, payload, ts)</C> sehingga riwayat bisa direplay penuh.</>,
            <>Payload dibatasi 12k char (_cap) agar DB aman; error tool diberikan ke model sebagai data (graceful).</>,
          ]}
        />
        <Note>
          Kontrak replay: <C>db.list_trace()</C> meratakan <C>payload</C> ke level atas supaya bentuk
          event replay identik dengan wire SSE ({'{'}type, ...fields{'}'}). UI membaca field
          top-level (<C>text</C>, <C>items</C>, <C>summary</C>, …) untuk keduanya.
        </Note>
        <Shot
          src="/docs-images/05-interpreter-timeline-expanded.png"
          alt="Timeline replay"
          caption="Replay dari SQLite: event timeline dibentangkan menunjukkan payload JSON mentah per event."
        />
      </section>

      <section className="space-y-4">
        <H2 id="providers">7. Providers</H2>
        <P>
          Semua provider mengimplementasikan <C>BaseProvider.stream()</C> yang yield{" "}
          <C>StreamEvent</C> (thinking / delta / logprobs / tool_calls / usage / done).{" "}
          <C>HuggingFaceProvider</C> mewarisi <C>OpenAIProtocolProvider</C> (parser SSE bersama:
          state-machine <C>&lt;think&gt;</C> terbelah chunk, akumulasi <C>tool_calls.arguments</C>{" "}
          per index, logprobs, usage).
        </P>
        <H3>Menambah provider baru</H3>
        <OL
          items={[
            <>Buat <C>backend/app/providers/foo_provider.py</C>, subclass <C>BaseProvider</C> (atau OpenAIProtocolProvider bila kompatibel).</>,
            <>Daftarkan di <C>providers/__init__.py:build_provider()</C> + tambahkan nama di <C>config.py</C> & UI SettingsModal.</>,
            <>Tambahkan test parser di <C>backend/tests/test_providers.py</C>.</>,
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="tools">8. Tools registry</H2>
        <Table
          head={["Tool", "Fungsi", "Catatan keamanan"]}
          rows={[
            ["web_search", "DuckDuckGo lite (default) / Serper / Tavily; parse BS4 judul+URL+snippet.", "Timeout & payload cap; error → tool_result."],
            ["fetch_url", "Ekstrak teks halaman (readability ringan) ≤ 12k char.", "Hanya teks; tanpa eksekusi konten."],
            ["create_diagram", "Mermaid flowchart / graph / mindmap dari nodes+edges.", "Validasi server-side: id dinormalisasi, label di-escape, edge diverifikasi."],
            ["calculator", "Aritmetika via AST whitelist (+ - * / // % **).", "Tidak ada eval(); node di luar whitelist = error."],
          ]}
        />
        <H3>Menambah tool baru</H3>
        <Code>{`# backend/app/tools/foo.py
from .base import Tool, ToolContext, ToolResult

async def run_foo(args: dict, ctx: ToolContext) -> ToolResult:
    ...  # args sudah tervalidasi schema JSON-Schema
    return ToolResult(summary="...", data={...})

FOO = Tool(name="foo", description="...", parameters={...}, run=run_foo)

# daftarkan di tools/__init__.py (ALL_TOOLS) — schema otomatis dikirim ke LLM`}</Code>
      </section>

      <section className="space-y-4">
        <H2 id="frontend">9. Frontend</H2>
        <Table
          head={["File", "Tanggung jawab"]}
          rows={[
            ["app/page.tsx", "Orkestrasi state: conversations, messages, trace, live-stream, settings, aksen."],
            ["lib/api.ts", "Klien SSE (parser baris data:), CRUD conversations, settings, health."],
            ["components/ChatView.tsx", "Render pesan, chip tool, kotak thinking, live answer."],
            ["components/Interpreter.tsx", "4 tab trace (Timeline/Prompt/Tokens/Metrics) dari event live maupun replay."],
            ["components/Mermaid.tsx", "mermaid.render() aman (securityLevel strict) untuk fence ```mermaid & hasil tool."],
            ["next.config.ts", "Rewrite /api, /slides, /docs-images ke backend (same-origin utk browser & preview)."],
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="screenshots">10. Pipeline screenshot docs</H2>
        <P>
          Gambar di <C>docs/images/</C> (dipakai halaman ini, /panduan, dan markdown docs) diambil
          dari aplikasi yang benar-benar berjalan:
        </P>
        <Code>{`# 1) jalankan stack (backend + emulator LLM + frontend)
python3 run.py --demo

# 2) capture (butuh playwright; lihat docstring script utk env Chromium khusus)
BASE_URL=http://127.0.0.1:3000 python3 scripts/capture_screenshots.py main
python3 scripts/capture_screenshots.py pages   # setelah halaman docs ada`}</Code>
        <UL
          items={[
            <>Script men-drive UI: kirim prompt diagram/search/kalkulasi, buka tab Interpreter, settings, banner offline, viewport mobile.</>,
            <>Backend menyajikan gambar via mount <C>/docs-images</C>; Next me-rewrite path yang sama sehingga halaman docs tetap same-origin.</>,
            <>Di lingkungan tanpa CDN browser, set <C>CHROME_EXE</C>/<C>CHROME_LIBS</C>/<C>CHROME_FONTS</C> (mis. binary dari paket npm @sparticuz/chromium).</>,
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="env">11. Referensi env (prefix ASK_)</H2>
        <Table
          head={["Variabel", "Default", "Keterangan"]}
          rows={[
            ["ASK_PROVIDER", "huggingface", "huggingface | openai | mock"],
            ["ASK_HF_MODE", "local", "local = inference di proses backend · server = URL OpenAI-compatible"],
            ["ASK_HF_MODEL", "–", "Repo id model offline yang aktif, mis. Qwen/Qwen3-1.7B"],
            ["ASK_MODELS_DIR", "models", "Folder project tempat model HuggingFace diunduh"],
            ["ASK_HF_TOKEN", "–", "Token Hub untuk repo gated/privat"],
            ["ASK_HF_BASE_URL", "http://127.0.0.1:8081/v1", "Hanya untuk hf_mode=server"],
            ["ASK_OPENAI_API_KEY / _BASE_URL / _MODEL", "– / api.openai.com / gpt-4o-mini", "Provider OpenAI"],
            ["ASK_TEMPERATURE / ASK_MAX_STEPS / ASK_LOGPROBS", "0.7 / 6 / true", "Generasi & interpreter"],
            ["ASK_SEARCH_BACKEND", "ddg", "ddg | serper | tavily (+ key masing-masing)"],
            ["ASK_DB_PATH", "data/ask_anything.db", "Lokasi SQLite"],
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="troubleshoot">12. Troubleshooting dev</H2>
        <Table
          head={["Masalah", "Penyebab", "Fix"]}
          rows={[
            ["UI tampil tapi tidak interaktif (state kosong)", "Next 16 memblokir dev-resources cross-origin → hydrate gagal.", "Tambahkan host ke allowedDevOrigins di next.config.ts, restart dev server."],
            ["Interpreter replay kosong", "Event replay tidak flat (payload nested).", "Pastikan db.list_trace() meratakan payload (kontrak replay)."],
            ["Playwright gagal download Chromium", "Jaringan memblokir CDN.", "Pakai CHROME_EXE (binary alternatif) — lihat docstring capture_screenshots.py."],
            ["Screenshot tanpa teks", "Fontconfig tidak menemukan font.", "Set CHROME_FONTS ke fonts.conf dengan <dir> font tersedia."],
            ["web_search error di sandbox offline", "Egress diblokir.", "Diharapkan: agent menangani error graceful; gunakan Serper/Tavily bila punya akses."],
          ]}
        />
      </section>
    </DocShell>
  );
}
