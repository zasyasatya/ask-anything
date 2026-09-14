"use client";
/* Mechanistic Interpreter — membuka blackbox, bukan menjelaskan panjang lebar.

   Prinsipnya:
   · LOG = default. Satu baris per langkah: t+, actor, aksi, status, durasi,
     detail teknis. Tidak ada paragraf; prosa (thinking/delta) diringkas jadi
     hitungan dan isi mentahnya tetap bisa dibuka.
   · LLM = permintaan & respons MENTAH per langkah (payload yang benar-benar
     dikirim + teks yang benar-benar keluar, termasuk tool_calls & finish_reason).
   · TOOLS = eksekusi lengkap tiap pemanggilan: argumen, hasil, ok/gagal/0 hasil,
     durasi, provenance (Browser vs Tool diagram vs Kalkulator).
   · SUMBER = daftar sitasi bernomor + status verifikasi per klaim.
   · METRIK = angka mentah (token, latensi, langkah, error).
   Panel bisa dilebarkan lewat drag dan lebarnya dipersist. */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { TraceEvent } from "@/lib/types";
import {
  LEVEL_STYLE,
  STATUS_STYLE,
  buildLog,
  fmtDur,
  fmtT,
  logToText,
} from "@/lib/log";
import {
  SOURCE_BADGE,
  SOURCE_META,
  citationLabel,
  sourceOf,
  type CitationReport,
  type SourceRef,
} from "@/lib/sources";

const TABS = ["Log", "LLM", "Tools", "Sumber", "Metrik"] as const;
type Tab = (typeof TABS)[number];

const W_KEY = "aa:interp-w";
const W_MIN = 380;
const W_MAX = 980;
const W_DEF = 460;

function readW(): number {
  if (typeof window === "undefined") return W_DEF;
  const n = Number(window.localStorage.getItem(W_KEY));
  return Number.isFinite(n) && n >= W_MIN && n <= W_MAX ? n : W_DEF;
}

/** Block JSON ringkas dengan header + tombol salin. */
function Raw({
  label,
  data,
  defaultOpen = false,
  max = "max-h-64",
}: {
  label: string;
  data: unknown;
  defaultOpen?: boolean;
  max?: string;
}) {
  const text = useMemo(() => {
    try {
      return JSON.stringify(data, null, 2) ?? String(data);
    } catch {
      return String(data);
    }
  }, [data]);
  return (
    <details open={defaultOpen} className="group rounded-lg border border-zinc-200 bg-zinc-50/70">
      <summary className="flex cursor-pointer items-center gap-2 px-2 py-1 font-mono text-[10.5px] text-zinc-500 hover:bg-zinc-100">
        <span className="text-zinc-400 transition group-open:rotate-90">▸</span>
        <span className="font-medium">{label}</span>
        <span className="ml-auto opacity-60">{text.length} B</span>
      </summary>
      <div className="relative">
        <pre className={`${max} overflow-auto whitespace-pre-wrap break-words bg-zinc-900 p-2 font-mono text-[10.5px] leading-4 text-zinc-100`}>
          {text}
        </pre>
        <button
          type="button"
          onClick={() => navigator.clipboard?.writeText(text).catch(() => undefined)}
          className="absolute right-1.5 top-1.5 rounded bg-zinc-800/90 px-1.5 py-0.5 font-mono text-[9.5px] text-zinc-300 hover:bg-zinc-700"
        >
          salin
        </button>
      </div>
    </details>
  );
}

function Badge({ children, cls }: { children: React.ReactNode; cls: string }) {
  return (
    <span className={`rounded px-1.5 py-0.5 font-mono text-[9.5px] font-medium ${cls}`}>
      {children}
    </span>
  );
}

function SourceBadge({ source }: { source: string }) {
  const meta = SOURCE_META[sourceOf("", source)] ?? SOURCE_META.compute;
  return (
    <Badge cls={SOURCE_BADGE[meta.label] || "bg-zinc-500/15 text-zinc-400"}>
      {meta.icon} {meta.label}
    </Badge>
  );
}

export default function Interpreter({
  trace,
  streaming,
  onClose,
}: {
  trace: TraceEvent[];
  streaming: boolean;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<Tab>("Log");
  const [width, setWidth] = useState(W_DEF);
  const [openRow, setOpenRow] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const dragging = useRef(false);

  useEffect(() => setWidth(readW()), []);

  // ── drag untuk melebarkan/mempersempit panel ─────────────────────────
  useEffect(() => {
    const move = (e: PointerEvent) => {
      if (!dragging.current) return;
      const w = Math.min(W_MAX, Math.max(W_MIN, window.innerWidth - e.clientX));
      setWidth(w);
    };
    const up = () => {
      if (!dragging.current) return;
      dragging.current = false;
      try {
        window.localStorage.setItem(W_KEY, String(width));
      } catch {
        /* noop */
      }
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [width]);

  const lines = useMemo(() => buildLog(trace), [trace]);

  const requests = trace.filter((e) => e.type === "llm_request");
  const responses = trace.filter((e) => e.type === "llm_response");
  const legacyPrompt = trace.find((e) => e.type === "prompt");
  const toolCalls = trace.filter((e) => e.type === "tool_call");
  const toolResults = trace.filter((e) => e.type === "tool_result");
  const meta = trace.find((e) => e.type === "meta");
  const usage = [...trace].reverse().find((e) => e.type === "usage");
  const done = [...trace].reverse().find((e) => e.type === "done");
  const citEvent = [...trace].reverse().find((e) => e.type === "citations");
  const sourcesEvent = [...trace].reverse().find((e) => e.type === "sources");
  const errors = trace.filter((e) => e.type === "error");
  const notes = trace.filter((e) => e.type === "note");
  const tokens = useMemo(
    () => trace.filter((e) => e.type === "logprobs").flatMap((e) => (e.items as Array<Record<string, unknown>>) || []),
    [trace]
  );

  const sources = (citEvent?.sources ?? sourcesEvent?.items ?? []) as SourceRef[];
  const report = citEvent
    ? ({
        status: citEvent.status,
        total: Number(citEvent.total ?? 0),
        cited: (citEvent.cited as number[]) || [],
        uncited: (citEvent.uncited as number[]) || [],
        invalid: (citEvent.invalid as number[]) || [],
        detail: String(citEvent.detail ?? ""),
      } as CitationReport)
    : null;

  const thinkingByStep = useMemo(() => {
    const m = new Map<number, string>();
    for (const e of trace) {
      if (e.type !== "thinking") continue;
      const s = Number(e.step ?? 0);
      m.set(s, (m.get(s) || "") + String(e.text ?? ""));
    }
    return m;
  }, [trace]);

  const answerByStep = useMemo(() => {
    const m = new Map<number, string>();
    for (const e of trace) {
      if (e.type === "llm_response") m.set(Number(e.step ?? 0), String(e.text ?? ""));
    }
    return m;
  }, [trace]);

  const copyLog = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(logToText(lines));
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard diblokir */
    }
  }, [lines]);

  const browserHits = toolResults.filter((e) => sourceOf(String(e.name), e.source as string) === "browser");
  const browserEmpty = browserHits.filter((e) => Number(e.hits) === 0).length;

  return (
    <aside
      data-testid="interpreter"
      aria-label="Mechanistic Interpreter"
      className="relative flex h-full shrink-0 flex-col border-l border-zinc-200/80 bg-[#0d0f13] text-zinc-200"
      style={{ width }}
    >
      {/* grip resize */}
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Ubah lebar panel interpreter"
        data-testid="interp-resizer"
        title="Drag untuk melebarkan"
        onPointerDown={() => {
          dragging.current = true;
        }}
        className="absolute left-0 top-0 z-10 h-full w-1.5 cursor-col-resize bg-transparent hover:bg-accent/40"
      />

      <header className="flex items-center gap-2 border-b border-white/10 px-3 py-2">
        <span className={`h-2 w-2 shrink-0 rounded-full ${streaming ? "animate-pulse bg-accent" : "bg-zinc-600"}`} />
        <h2 className="text-[12.5px] font-semibold tracking-tight text-zinc-100">
          Mechanistic Interpreter
        </h2>
        <span className="rounded bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
          {String(meta?.model ?? "—")}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={copyLog}
            title="Salin log eksekusi apa adanya"
            className="rounded-md px-2 py-1 font-mono text-[10.5px] text-zinc-400 hover:bg-white/10 hover:text-zinc-100"
          >
            {copied ? "tersalin ✓" : "copy log"}
          </button>
          <button
            onClick={onClose}
            aria-label="Tutup interpreter"
            className="rounded-md px-2 py-1 text-xs text-zinc-400 hover:bg-white/10 hover:text-zinc-100"
          >
            ✕
          </button>
        </div>
      </header>

      {/* strip status: angka, bukan kalimat */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-white/10 bg-black/20 px-3 py-1.5 font-mono text-[10px] text-zinc-400">
        <span>ev <b className="text-zinc-200">{trace.length}</b></span>
        <span>llm <b className="text-violet-300">{requests.length}</b></span>
        <span>tool <b className="text-sky-300">{toolCalls.length}</b></span>
        <span>
          browser{" "}
          <b className={browserEmpty > 0 ? "text-amber-300" : "text-zinc-200"}>
            {browserHits.length - browserEmpty}/{browserHits.length}
          </b>
        </span>
        <span>sumber <b className="text-zinc-200">{report?.total ?? 0}</b></span>
        <span>err <b className={errors.length ? "text-red-300" : "text-zinc-200"}>{errors.length}</b></span>
        {notes.length > 0 && <span>note <b className="text-amber-300">{notes.length}</b></span>}
        <span className="ml-auto">
          {report ? citationLabel(report) : "belum ada run"}
        </span>
      </div>

      <nav className="flex gap-0.5 border-b border-white/10 px-2 py-1.5">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            aria-current={tab === t ? "true" : undefined}
            className={`rounded-md px-2 py-1 text-[11px] font-medium transition ${
              tab === t ? "bg-zinc-100 text-zinc-900" : "text-zinc-400 hover:bg-white/10 hover:text-zinc-100"
            }`}
          >
            {t}
            {t === "Log" && lines.length > 0 && (
              <span className="ml-1 opacity-60">{lines.length}</span>
            )}
            {t === "Tools" && toolCalls.length > 0 && (
              <span className="ml-1 opacity-60">{toolCalls.length}</span>
            )}
            {t === "Sumber" && sources.length > 0 && (
              <span className="ml-1 opacity-60">{sources.length}</span>
            )}
          </button>
        ))}
      </nav>

      <div className="min-h-0 flex-1 overflow-y-auto px-2.5 py-2.5">
        {/* ───────────────────────────────────────────────────── LOG ───── */}
        {tab === "Log" && (
          <div data-testid="interp-log" className="font-mono text-[11px] leading-[1.55]">
            {lines.length === 0 && (
              <p className="px-1 pt-6 text-center text-[11px] text-zinc-500">
                Belum ada event. Kirim pesan — setiap langkah LLM & tool akan muncul di sini
                sebagai baris log, bukan narasi.
              </p>
            )}
            {lines.map((l) => {
              const st = LEVEL_STYLE[l.level];
              const isOpen = openRow === l.key;
              return (
                <div key={l.key} className="group rounded hover:bg-white/5">
                  <button
                    type="button"
                    onClick={() => setOpenRow(isOpen ? null : l.key)}
                    aria-expanded={isOpen}
                    data-testid={`log-row-${l.action}`}
                    className="flex w-full items-start gap-1.5 px-1 py-[3px] text-left"
                  >
                    <span className={`mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full ${st.dot}`} />
                    <span className="w-[62px] shrink-0 tabular-nums text-zinc-500">{fmtT(l.tMs)}</span>
                    <span className="w-[70px] shrink-0 truncate text-zinc-300">{l.actor}</span>
                    <span className={`w-[96px] shrink-0 truncate ${st.text}`}>{l.action}</span>
                    <Badge cls={STATUS_STYLE[l.status] || STATUS_STYLE["n/a"]}>{l.status}</Badge>
                    {l.source && <SourceBadge source={l.source} />}
                    <span className="min-w-0 flex-1 truncate text-zinc-400">{l.detail}</span>
                    {l.durMs != null && (
                      <span className="shrink-0 tabular-nums text-zinc-500">{fmtDur(l.durMs)}</span>
                    )}
                  </button>
                  {isOpen && (
                    <div className="space-y-1 px-2 pb-2 pt-1">
                      <Raw label="payload" data={l.raw} defaultOpen max="max-h-52" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ────────────────────────────────────────────────────── LLM ───── */}
        {tab === "LLM" && (
          <div data-testid="interp-llm" className="space-y-2.5">
            <Raw label="system prompt (apa yang dipaksa patuh pada aturan sitasi)" data={legacyPrompt?.system ?? null} max="max-h-56" />

            {(requests.length ? requests : []).map((req, i) => {
              const step = Number(req.step ?? i);
              const res = responses.find((r) => Number(r.step ?? i) === step);
              const calls = (res?.tool_calls as Array<Record<string, unknown>>) || [];
              return (
                <div key={i} className="rounded-lg border border-white/10 bg-black/25">
                  <div className="flex flex-wrap items-center gap-1.5 border-b border-white/10 px-2 py-1.5 font-mono text-[10.5px]">
                    <Badge cls="bg-violet-500/15 text-violet-300">step {step + 1}</Badge>
                    <span className="text-zinc-400">
                      {String(req.message_count ?? "?")} msg · {String((req.tools as unknown[])?.length ?? "?")} tools
                    </span>
                    {res && (
                      <>
                        <span className="text-zinc-500">→</span>
                        <span className="text-zinc-300">
                          finish={String(res.finish_reason ?? "?")} · {String(res.chars ?? 0)} chars
                        </span>
                        <span className="ml-auto tabular-nums text-zinc-500">{fmtDur(Number(res.duration_ms ?? 0))}</span>
                      </>
                    )}
                  </div>
                  <div className="space-y-1 p-2">
                    <Raw label="→ request messages (persis yang dikirim)" data={req.messages} max="max-h-60" />
                    <Raw label="→ tools schema" data={req.tools} max="max-h-44" />
                    {res && (
                      <>
                        <Raw label="← raw completion (teks mentah)" data={res.text || "(kosong)"} max="max-h-56" />
                        <Raw label="← chain-of-thought <think>" data={thinkingByStep.get(step) || "(tidak ada)"} max="max-h-56" />
                        {calls.length > 0 && (
                          <Raw label="← tool_calls yang diminta model" data={calls} defaultOpen max="max-h-44" />
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}

            {!requests.length && legacyPrompt && (
              <>
                <Raw label="messages → LLM" data={legacyPrompt.messages} max="max-h-72" />
                <Raw label="tools tersedia" data={legacyPrompt.tools} max="max-h-56" />
              </>
            )}
            {!requests.length && !legacyPrompt && (
              <p className="pt-6 text-center text-[11px] text-zinc-500">
                Belum ada permintaan LLM pada run ini.
              </p>
            )}

            {tokens.length > 0 && (
              <div className="rounded-lg border border-white/10 bg-black/25 p-2">
                <p className="mb-1.5 font-mono text-[10.5px] text-zinc-400">
                  token logprobs · {tokens.length} token terakhir {tokens.length > 200 ? "(dibatasi 200)" : ""}
                </p>
                <div className="flex max-h-40 flex-wrap gap-1 overflow-y-auto">
                  {tokens.slice(-200).map((t, i) => {
                    const p = Math.exp(Number(t.logprob || 0));
                    return (
                      <span
                        key={i}
                        title={`p=${p.toFixed(4)} · alt: ${((t.top as Array<Record<string, unknown>>) || []).slice(1).map((a) => String(a.token)).join(", ") || "—"}`}
                        className={`rounded px-1 font-mono text-[10px] ${
                          p > 0.85
                            ? "bg-emerald-500/15 text-emerald-300"
                            : p > 0.55
                              ? "bg-zinc-500/15 text-zinc-300"
                              : "bg-amber-500/15 text-amber-300"
                        }`}
                      >
                        {String(t.token)}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ──────────────────────────────────────────────────── TOOLS ───── */}
        {tab === "Tools" && (
          <div data-testid="interp-tools" className="space-y-2">
            {toolCalls.length === 0 && (
              <p className="pt-6 text-center text-[11px] text-zinc-500">
                Agent tidak memanggil tool apa pun pada run ini.
              </p>
            )}
            {toolCalls.map((call, i) => {
              const id = String(call.id ?? "");
              const res =
                toolResults.find((r) => String(r.id ?? "") === id) ??
                toolResults.filter((r) => r.name === call.name)[i];
              const src = sourceOf(String(call.name), call.source as string);
              const meta2 = SOURCE_META[src];
              const hits = res ? Number(res.hits) : null;
              const failed = res ? res.ok === false : false;
              const running = !res;
              return (
                <div key={i} className="rounded-lg border border-white/10 bg-black/25">
                  <div className="flex flex-wrap items-center gap-1.5 border-b border-white/10 px-2 py-1.5 font-mono text-[10.5px]">
                    <span className="font-semibold text-zinc-100">{String(call.name)}</span>
                    <Badge cls={meta2.needsCitation ? "bg-sky-500/15 text-sky-300" : "bg-violet-500/15 text-violet-300"}>
                      {meta2.icon} {meta2.label}
                    </Badge>
                    <Badge
                      cls={
                        running
                          ? STATUS_STYLE.running
                          : failed
                            ? STATUS_STYLE.failed
                            : hits === 0
                              ? STATUS_STYLE.empty
                              : STATUS_STYLE.ok
                      }
                    >
                      {running ? "running" : failed ? "error" : hits === 0 ? "0 hasil" : "ok"}
                    </Badge>
                    {hits === 0 && !running && (
                      <span className="text-amber-300">
                        {meta2.needsCitation ? "belum ada hasil dari browser" : "tidak menghasilkan data"}
                      </span>
                    )}
                    {res && (
                      <span className="ml-auto tabular-nums text-zinc-500">
                        {fmtDur(Number(res.duration_ms ?? 0))}
                      </span>
                    )}
                  </div>
                  <div className="space-y-1 p-2">
                    <Raw label="arguments (dari model)" data={call.arguments} max="max-h-40" />
                    {res && <Raw label="result payload (mentah)" data={res.data} defaultOpen max="max-h-56" />}
                    {res && (
                      <p className="px-0.5 font-mono text-[10px] text-zinc-500">
                        summary: {String(res.summary ?? "")}
                        {typeof res.new_sources === "number" && res.new_sources > 0
                          ? ` · +${String(res.new_sources)} sumber terdaftar`
                          : ""}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}

            {notes.length > 0 && (
              <div className="rounded-lg border border-amber-400/25 bg-amber-400/5 p-2">
                <p className="mb-1 font-mono text-[10.5px] text-amber-300">
                  catatan provider ({notes.length})
                </p>
                {notes.map((n, i) => (
                  <p key={i} className="font-mono text-[10px] leading-5 text-amber-200/80">
                    · [{String(n.status ?? "note")}] {String(n.message ?? "")}
                  </p>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ─────────────────────────────────────────────────── SUMBER ───── */}
        {tab === "Sumber" && (
          <div data-testid="interp-sources" className="space-y-2">
            {!sources.length && (
              <div className="rounded-lg border border-white/10 bg-black/25 px-3 py-4 text-center">
                <p className="font-mono text-[11px] text-zinc-400">
                  {report?.status === "no-evidence"
                    ? "0 sumber — browser sudah dipanggil tapi tidak menghasilkan hasil"
                    : "Belum ada sumber web pada run ini"}
                </p>
                <p className="mt-1 text-[10.5px] text-zinc-500">
                  {report?.detail ||
                    "Tidak ada klaim yang bisa diverifikasi dari web; jawaban berasal dari model/tool saja."}
                </p>
              </div>
            )}

            {sources.length > 0 && (
              <div className="overflow-hidden rounded-lg border border-white/10">
                <table className="w-full border-collapse font-mono text-[10.5px]">
                  <thead>
                    <tr className="border-b border-white/10 bg-white/5 text-zinc-400">
                      <th className="px-2 py-1 text-left font-medium">#</th>
                      <th className="px-2 py-1 text-left font-medium">asal</th>
                      <th className="px-2 py-1 text-left font-medium">judul / url</th>
                      <th className="px-2 py-1 text-left font-medium">status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sources.map((s) => (
                      <tr key={s.index} className="border-b border-white/5 align-top last:border-0">
                        <td className="px-2 py-1 text-zinc-500">{s.index}</td>
                        <td className="px-2 py-1">
                          <Badge cls="bg-sky-500/15 text-sky-300">🌐 browser</Badge>
                          <p className="mt-0.5 text-[9.5px] text-zinc-500">{s.tool}</p>
                        </td>
                        <td className="max-w-0 px-2 py-1">
                          <p className="truncate text-zinc-200" title={s.title}>{s.title}</p>
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noreferrer"
                            className="block truncate text-zinc-500 underline decoration-dotted hover:text-zinc-300"
                            title={s.url}
                          >
                            {s.url}
                          </a>
                        </td>
                        <td className="px-2 py-1">
                          {s.cited ? (
                            <Badge cls="bg-emerald-500/15 text-emerald-300">✓ dikutip</Badge>
                          ) : (
                            <Badge cls="bg-amber-500/15 text-amber-300">tidak dikutip</Badge>
                          )}
                          {s.read && <p className="mt-0.5 text-[9.5px] text-zinc-500">dibaca penuh</p>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {report && (
              <div className="grid grid-cols-2 gap-1.5 font-mono text-[10.5px]">
                <div className="rounded-lg border border-white/10 bg-black/25 px-2 py-1.5">
                  <p className="text-zinc-500">status verifikasi</p>
                  <p className={report.status === "cited" ? "text-emerald-300" : report.status === "appended" ? "text-amber-300" : "text-zinc-300"}>
                    {report.status}
                  </p>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/25 px-2 py-1.5">
                  <p className="text-zinc-500">dikutip / tak valid</p>
                  <p className="text-zinc-300">
                    {report.cited.length}/{report.total} · invalid {report.invalid.length}
                  </p>
                </div>
              </div>
            )}
            {report && report.invalid.length > 0 && (
              <p className="rounded-lg border border-red-400/25 bg-red-500/5 px-2 py-1.5 font-mono text-[10.5px] text-red-300">
                marker {report.invalid.map((n) => `[${n}]`).join(" ")} tidak ada di daftar sumber —
                sitasi semacam itu tidak valid dan ditandai merah di jawaban.
              </p>
            )}
          </div>
        )}

        {/* ──────────────────────────────────────────────────── METRIK ───── */}
        {tab === "Metrik" && (
          <div data-testid="interp-metrics" className="grid grid-cols-2 gap-1.5 font-mono text-[11px]">
            {[
              ["provider", String(meta?.provider ?? "—")],
              ["model", String(meta?.model ?? "—")],
              ["temperature", String(meta?.temperature ?? "—")],
              ["max_tokens", String(meta?.max_tokens ?? "—")],
              ["max_steps", String(meta?.max_steps ?? "—")],
              ["steps terpakai", String(done?.steps ?? "—")],
              ["stopped_reason", String(done?.stopped_reason ?? "—")],
              ["latency", `${done?.latency_ms ?? "—"} ms`],
              ["prompt tokens", String(usage?.prompt_tokens ?? "—")],
              ["completion tokens", String(usage?.completion_tokens ?? "—")],
              ["total tokens", String(usage?.total_tokens ?? "—")],
              ["logprob tokens", String(tokens.length)],
              ["tool calls", String(toolCalls.length)],
              ["browser hits", `${browserHits.length - browserEmpty}/${browserHits.length}`],
              ["sumber", String(report?.total ?? 0)],
              ["errors / notes", `${errors.length} / ${notes.length}`],
            ].map(([k, v]) => (
              <div key={k} className="rounded-lg border border-white/10 bg-black/25 px-2 py-1.5">
                <p className="text-[9.5px] uppercase tracking-wide text-zinc-500">{k}</p>
                <p className="truncate text-zinc-200" title={v}>{v}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
