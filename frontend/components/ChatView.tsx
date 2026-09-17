"use client";
/* Ruang chat.
   - Lebar: mengikuti lebar layar (maks 1180px) + padding longgar, dan
     ikut meluas saat navbar di-collapse maupun saat Interpreter terbuka.
   - Setiap hasil tool diberi badge PROVENANCE (Browser / Tool diagram /
     Kalkulator) sehingga terlihat jelas mana bukti web dan mana buatan tool.
   - Browser tanpa hasil ditampilkan sebagai status eksplisit, bukan bubble kosong.
   - Jawaban yang memakai bukti web menampilkan bar sitasi + marker [n] inline. */
import { useEffect, useRef } from "react";
import Markdown from "@/lib/markdown";
import Logo from "./Logo";
import Composer from "./Composer";
import { ThinkingIndicator } from "./LoadingScreen";
import DiagramBlock from "./DiagramBlock";
import type { PipelineMode, PolicyInfo } from "@/lib/types";
import FeedbackButtons from "./FeedbackButtons";
import ArtifactCards from "./ArtifactCards";
import type { ArtifactRef } from "./ArtifactCards";
import { answerHasDiagram, diagramArtifacts, type DiagramArtifact } from "@/lib/diagrams";
import type { LiveState, LiveTool } from "@/lib/live";
import {
  OUTCOME_LABEL,
  SOURCE_META,
  citationLabel,
  citationTone,
  metaOf,
  outcomeOf,
  sourceOf,
  type CitationReport,
  type SourceRef,
} from "@/lib/sources";

export interface DispMsg {
  role: string;
  content: string;
  meta?: Record<string, unknown>;
  /** id pesan assistant di DB — kunci tombol feedback 👍/👎. */
  id?: string;
}

// Status live dimiliki lib/live.ts (reducer murni, teruji tanpa DOM) dan
// diekspor ulang di sini supaya pemakaian lama tetap jalan.
export type { LiveState, LiveTool } from "@/lib/live";

/**
 * Kartu diagram untuk artefak tool.
 *
 * Diagram hasil `create_diagram` dirender dari payload tool, bukan dari teks
 * jawaban: model tidak perlu (dan sering tidak) menyalin sumber Mermaid ke
 * jawabannya, dan diagram tetap muncul. Yang sudah ada sebagai fence di
 * jawaban dilewati supaya tidak dobel.
 */
function DiagramCards({
  diagrams,
  answer = "",
}: {
  diagrams: DiagramArtifact[];
  answer?: string;
}) {
  const cards = diagrams.filter((d) => !answerHasDiagram(answer, d.mermaid));
  if (!cards.length) return null;
  return (
    <div className="my-2 space-y-1">
      {cards.map((d, i) => (
        <DiagramBlock
          key={`${d.title}-${i}`}
          source={d.mermaid}
          title={d.title}
          compact={cards.length > 1}
          provenance={{ tool: d.tool, titles: [d.title] }}
        />
      ))}
    </div>
  );
}

/** Badge kecil satu tool: provenance + hasil + durasi. */
function ToolChip({ tool }: { tool: LiveTool }) {
  const meta = metaOf(tool.name, tool.source);
  const outcome = outcomeOf(tool as never);
  const tone =
    outcome === "running"
      ? "border-sky-200 bg-sky-50 text-sky-700 animate-pulse"
      : outcome === "failed"
        ? "border-red-200 bg-red-50 text-red-700"
        : outcome === "empty"
          ? "border-amber-200 bg-amber-50 text-amber-700"
          : "border-emerald-200 bg-emerald-50 text-emerald-700";
  return (
    <span
      data-testid={`tool-chip-${tool.name}`}
      title={tool.summary || meta.hint}
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-mono text-[10.5px] ${tone}`}
    >
      <span aria-hidden="true">{meta.icon}</span>
      <span className="font-semibold">{tool.name}</span>
      <span className="opacity-70">· {meta.label}</span>
      {typeof tool.hits === "number" && (
        <span className="opacity-70">· {tool.hits} hasil</span>
      )}
      {outcome !== "running" && (
        <span className="opacity-80">· {OUTCOME_LABEL[outcome]}</span>
      )}
      {tool.duration_ms != null && (
        <span className="opacity-60">{Math.round(tool.duration_ms)}ms</span>
      )}
    </span>
  );
}

function ToolChips({ tools }: { tools: LiveTool[] }) {
  if (!tools.length) return null;
  return (
    <div className="mb-2 flex flex-wrap gap-1.5">
      {tools.map((t, i) => (
        <ToolChip key={`${t.name}-${i}`} tool={t} />
      ))}
    </div>
  );
}

/**
 * Chip tool dari riwayat. Argumen datang dari pesan `assistant_toolcalls`,
 * hasilnya dilipat ke `meta.tool_results` oleh page.tsx — jadi status,
 * jumlah hasil, dan durasi tetap terbaca setelah run selesai.
 */
function HistoryToolChips({
  calls,
  results = [],
}: {
  calls: Array<Record<string, unknown>>;
  results?: Array<Record<string, unknown>>;
}) {
  const resultFor = (call: Record<string, unknown>, i: number) =>
    results.find((r) => r.callId && r.callId === call.id) ?? results[i] ?? null;

  return (
    <div className="mb-2 flex flex-wrap gap-1.5">
      {calls.map((t, i) => {
        const name = String(t.name ?? "?");
        const res = resultFor(t, i);
        if (res) {
          return (
            <ToolChip
              key={i}
              tool={{
                name,
                status: res.ok === false ? "failed" : "done",
                source: res.source as string | undefined,
                ok: res.ok as boolean | undefined,
                hits: res.hits as number | null | undefined,
                duration_ms: res.duration_ms as number | undefined,
                new_sources: res.new_sources as number | undefined,
                summary: res.summary as string | undefined,
              }}
            />
          );
        }
        const meta = SOURCE_META[sourceOf(name, t.source as string)];
        return (
          <span
            key={i}
            data-testid={`tool-chip-${name}`}
            title={meta.hint}
            className="inline-flex items-center gap-1.5 rounded-md border border-zinc-200 bg-white px-2 py-0.5 font-mono text-[10.5px] text-zinc-500"
          >
            <span aria-hidden="true">{meta.icon}</span>
            {name}
            <span className="opacity-70">· {meta.label}</span>
            <span className="text-emerald-600">✓</span>
          </span>
        );
      })}
    </div>
  );
}

/** Panel sitasi: daftar sumber + status verifikasi, selalu terlihat bila ada. */
export function CitationBar({
  sources,
  report,
}: {
  sources: SourceRef[];
  report?: CitationReport | null;
}) {
  const tone = citationTone(report);
  const toneCls =
    tone === "ok"
      ? "border-emerald-200 bg-emerald-50/70 text-emerald-800"
      : tone === "warn"
        ? "border-amber-200 bg-amber-50/70 text-amber-800"
        : "border-zinc-200 bg-zinc-50 text-zinc-500";
  if (!sources.length && report?.status !== "no-evidence") return null;
  return (
    <div data-testid="citation-bar" className={`mt-3 rounded-xl border px-3 py-2.5 text-[12px] ${toneCls}`}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="inline-flex items-center gap-1.5 font-medium">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M6 3h9l5 5v13H6z" />
            <path d="M15 3v5h5" />
          </svg>
          Sitasi: {citationLabel(report)}
        </span>
        {report && report.invalid.length > 0 && (
          <span className="rounded bg-red-100 px-1.5 py-0.5 font-mono text-[10.5px] text-red-700">
            {report.invalid.length} nomor di luar daftar
          </span>
        )}
      </div>
      {sources.length > 0 && (
        <ol className="mt-2 space-y-1">
          {sources.map((s) => (
            <li key={s.index} className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
              <span className="font-mono text-[10.5px] text-zinc-400">[{s.index}]</span>
              <a
                href={s.url}
                target="_blank"
                rel="noreferrer"
                className="max-w-full truncate underline decoration-dotted underline-offset-2 hover:opacity-80"
              >
                {s.title || s.url}
              </a>
              <span className="rounded bg-white/70 px-1.5 py-0.5 font-mono text-[10px] text-zinc-500">
                {s.tool}
              </span>
              <span className="rounded bg-white/70 px-1.5 py-0.5 font-mono text-[10px] text-sky-600">
                browser
              </span>
              <span className="font-mono text-[10px]">
                {s.cited ? <span className="text-emerald-600">✓ dikutip</span> : <span className="text-amber-600">belum dikutip</span>}
              </span>
            </li>
          ))}
        </ol>
      )}
      {!sources.length && report?.detail && (
        <p className="mt-1 text-[11.5px] opacity-80">{report.detail}</p>
      )}
    </div>
  );
}

/** Lebar ruang chat: lega, tapi tetap terkontrol di monitor ultrawide. */
export const CHAT_WIDTH = "mx-auto w-full max-w-[1180px] px-6 md:px-10";

/** Index pesan assistant terakhir di riwayat — tombol feedback hanya untuk
    jawaban final terakhir supaya tidak berisik di percakapan panjang. */
function lastAssistantIndex(messages: DispMsg[]): number {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "assistant") return i;
  }
  return -1;
}

export default function ChatView({
  messages,
  live,
  streaming,
  input,
  setInput,
  onSend,
  accent,
  onAccent,
  deepResearch,
  onDeepResearch,
  conversationId,
  feedbackEnabled,
  policy,
  mode,
  onMode,
}: {
  messages: DispMsg[];
  live: LiveState;
  streaming: boolean;
  input: string;
  setInput: (v: string) => void;
  onSend: () => void;
  accent: string;
  onAccent: (a: string) => void;
  deepResearch?: boolean;
  onDeepResearch?: (v: boolean) => void;
  /** Mode RAG: pertanyaan diarahkan ke pipeline dokumen, bukan browsing. */
  ragMode?: boolean;
  /** Policy publik + mode aktif → chip mode di composer. */
  policy?: PolicyInfo | null;
  mode?: PipelineMode;
  onMode?: (m: PipelineMode) => void;
  conversationId?: string | null;
  feedbackEnabled?: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // `?.()` — beberapa lingkungan (jsdom, embedded view) tidak punya
    // Element.prototype.scrollIntoView; auto-scroll tidak boleh menjatuhkan UI.
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages.length, live.answer, live.tools.length]);

  return (
    <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        <div className={CHAT_WIDTH}>
          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="mb-6 flex justify-end">
                <div className="max-w-[min(100%,760px)] whitespace-pre-wrap rounded-2xl rounded-br-md bg-accent-soft px-4 py-2.5 text-[15px] leading-7 text-zinc-800">
                  {m.content}
                </div>
              </div>
            ) : m.role === "assistant_toolcalls" ? (
              <div key={i} className="mb-4 flex items-start gap-3">
                <div className="mt-1 shrink-0"><Logo size={18} /></div>
                <div className="min-w-0 flex-1">
                  <HistoryToolChips
                    calls={(m.meta?.tool_calls as Array<Record<string, unknown>>) || []}
                    results={(m.meta?.tool_results as Array<Record<string, unknown>>) || []}
                  />
                </div>
              </div>
            ) : (
              <div key={i} className="mb-7 flex items-start gap-3">
                <div className="mt-1 shrink-0"><Logo size={18} /></div>
                <div className="min-w-0 flex-1">
                  <Markdown
                    text={m.content}
                    sources={(m.meta?.sources as SourceRef[]) || []}
                    diagramOrigin={
                      (m.meta?.diagram_origin as { tool: string; titles: string[] }) || null
                    }
                  />
                  {/* Diagram hasil tool dirender dari payload tool: tetap ada
                      walau model tidak menulis fence ```mermaid. */}
                  <DiagramCards
                    diagrams={diagramArtifacts(m.meta?.diagrams)}
                    answer={m.content}
                  />
                  <ArtifactCards artifacts={(m.meta?.artifacts as ArtifactRef[]) || []} />
                  <CitationBar
                    sources={(m.meta?.sources as SourceRef[]) || []}
                    report={(m.meta?.citations as CitationReport) || null}
                  />
                  {feedbackEnabled && m.id && i === lastAssistantIndex(messages) && (
                    <FeedbackButtons
                      conversationId={conversationId || null}
                      messageId={m.id}
                    />
                  )}
                </div>
              </div>
            )
          )}

          {streaming && (
            <div className="mb-7 flex items-start gap-3">
              <div className="mt-1 shrink-0"><Logo size={18} /></div>
              <div className="min-w-0 flex-1">
                {live.thinking && !live.answer && (
                  <p className="mb-2 max-h-28 overflow-y-auto rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 font-mono text-[11px] leading-5 text-amber-700">
                    💭 {live.thinking}
                  </p>
                )}
                <ToolChips tools={live.tools} />
                {live.answer ? (
                  <>
                    {/* Sumber yang sudah terdaftar diteruskan ke markdown saat
                        streaming: tanpa ini marker [n] tampil sebagai "nomor
                        tidak ada di daftar sumber" padahal sumbernya ada. */}
                    <Markdown text={live.answer} sources={live.sources || []} />
                    <span className="ml-0.5 inline-block h-4 w-[7px] animate-pulse rounded-sm bg-accent align-middle" />
                  </>
                ) : !live.tools.length ? (
                  /* Loading screen pre-token: streaming otomatis aktif, tapi
                     token pertama bisa butuh beberapa detik (prompt panjang /
                     CPU-only). Jangan biarkan user menatap gelembung kosong. */
                  <div className="py-0.5" data-testid="thinking-indicator">
                    <ThinkingIndicator label="Model sedang berpikir" />
                  </div>
                ) : null}
                <DiagramCards
                  diagrams={live.diagrams || []}
                  answer={live.answer}
                />
                <ArtifactCards artifacts={(live.artifacts as ArtifactRef[]) || []} />
                {live.sources && live.sources.length > 0 && (
                  <CitationBar
                    sources={live.sources}
                    report={live.citations || undefined}
                  />
                )}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="border-t border-zinc-200/70 bg-[#f7f7f8]/80 px-6 py-4 backdrop-blur md:px-10">
        <div className="mx-auto w-full max-w-[1180px]">
          <Composer
            compact
            value={input}
            onChange={setInput}
            onSend={onSend}
            disabled={streaming}
            accent={accent}
            onAccent={onAccent}
            deepResearch={deepResearch}
            onDeepResearch={onDeepResearch}
            policy={policy}
            mode={mode}
            onMode={onMode}
          />
        </div>
      </div>
    </div>
  );
}
