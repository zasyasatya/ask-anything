"use client";
import { useMemo, useState } from "react";
import type { TraceEvent } from "@/lib/types";

const TABS = ["Timeline", "Prompt", "Tokens", "Metrics"] as const;

const TYPE_STYLE: Record<string, { dot: string; label: string }> = {
  meta: { dot: "bg-zinc-400", label: "meta" },
  thinking: { dot: "bg-amber-400", label: "thinking" },
  logprobs: { dot: "bg-violet-400", label: "logprobs" },
  tool_call: { dot: "bg-sky-500", label: "tool_call" },
  tool_result: { dot: "bg-emerald-500", label: "tool_result" },
  usage: { dot: "bg-zinc-400", label: "usage" },
  note: { dot: "bg-orange-400", label: "note" },
  done: { dot: "bg-emerald-600", label: "done" },
  error: { dot: "bg-red-500", label: "error" },
};

function Json({ data }: { data: unknown }) {
  return (
    <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-zinc-900 p-2.5 font-mono text-[10.5px] leading-4 text-zinc-100">
      {JSON.stringify(data, null, 2)}
    </pre>
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
  const [tab, setTab] = useState<(typeof TABS)[number]>("Timeline");

  const timeline = trace.filter((e) => e.type !== "prompt" && e.type !== "delta");
  const prompt = trace.find((e) => e.type === "prompt");
  const tokens = useMemo(
    () => trace.filter((e) => e.type === "logprobs").flatMap((e) => (e.items as Array<Record<string, unknown>>) || []),
    [trace]
  );
  const meta = trace.find((e) => e.type === "meta");
  const usage = [...trace].reverse().find((e) => e.type === "usage");
  const done = [...trace].reverse().find((e) => e.type === "done");
  const errors = trace.filter((e) => e.type === "error");

  return (
    <aside className="flex h-full w-[400px] shrink-0 flex-col border-l border-zinc-200/80 bg-white">
      <div className="flex items-center justify-between border-b border-zinc-200/80 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${streaming ? "animate-pulse bg-accent" : "bg-zinc-300"}`} />
          <h2 className="text-sm font-semibold text-zinc-900">Mechanistic Interpreter</h2>
        </div>
        <button onClick={onClose} className="rounded-md px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700">
          ✕
        </button>
      </div>

      <div className="flex gap-1 border-b border-zinc-200/80 px-3 py-2">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
              tab === t ? "bg-zinc-900 text-white" : "text-zinc-500 hover:bg-zinc-100"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {tab === "Timeline" && (
          <div className="space-y-1.5">
            {timeline.length === 0 && (
              <p className="px-1 pt-4 text-center text-xs text-zinc-400">
                Belum ada event. Kirim pesan untuk melihat seluruh proses agent.
              </p>
            )}
            {timeline.map((e, i) => {
              const st = TYPE_STYLE[e.type] || { dot: "bg-zinc-400", label: e.type };
              const detail =
                e.type === "thinking" ? { text: e.text } :
                e.type === "tool_call" ? { name: e.name, arguments: e.arguments, id: e.id } :
                e.type === "tool_result" ? { name: e.name, summary: e.summary, data: e.data } :
                e.type === "logprobs" ? { tokens: (e.items as unknown[] || []).length } :
                e;
              return (
                <details key={i} className="group rounded-lg border border-zinc-100 bg-zinc-50/60 open:bg-white">
                  <summary className="flex cursor-pointer items-center gap-2 px-2.5 py-1.5 text-[11px] text-zinc-600">
                    <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${st.dot}`} />
                    <span className="font-mono font-medium">{st.label}</span>
                    <span className="truncate text-zinc-400">
                      {e.type === "thinking" ? String(e.text || "").slice(0, 60)
                        : e.type === "tool_call" ? String(e.name || "")
                        : e.type === "tool_result" ? String(e.summary || "").slice(0, 60)
                        : e.type === "done" ? String(e.answer || "").slice(0, 60)
                        : ""}
                    </span>
                  </summary>
                  <div className="px-2.5 pb-2.5">
                    <Json data={detail} />
                  </div>
                </details>
              );
            })}
          </div>
        )}

        {tab === "Prompt" && (
          prompt ? (
            <div className="space-y-2">
              <p className="text-[11px] font-medium text-zinc-500">SYSTEM PROMPT</p>
              <Json data={prompt.system} />
              <p className="text-[11px] font-medium text-zinc-500">MESSAGES → LLM</p>
              <Json data={prompt.messages} />
              <p className="text-[11px] font-medium text-zinc-500">TOOLS TERSEDIA</p>
              <Json data={prompt.tools} />
            </div>
          ) : (
            <p className="pt-4 text-center text-xs text-zinc-400">Prompt assembly belum tersedia.</p>
          )
        )}

        {tab === "Tokens" && (
          <div className="space-y-1">
            {tokens.length === 0 && (
              <p className="pt-4 text-center text-xs text-zinc-400">
                Belum ada logprobs (provider harus mendukungnya).
              </p>
            )}
            {tokens.slice(0, 400).map((t, i) => {
              const p = Math.exp(Number(t.logprob || 0));
              return (
                <div key={i} className="flex items-start gap-2 rounded-md border border-zinc-100 px-2 py-1">
                  <span className="min-w-[70px] rounded bg-violet-50 px-1.5 font-mono text-[11px] font-medium text-violet-700">
                    {String(t.token)}
                  </span>
                  <div className="flex-1">
                    <div className="h-1.5 rounded bg-zinc-100">
                      <div className="h-1.5 rounded bg-violet-400" style={{ width: `${Math.round(p * 100)}%` }} />
                    </div>
                    <p className="mt-0.5 truncate font-mono text-[9.5px] text-zinc-400">
                      p={p.toFixed(3)} · alt: {((t.top as Array<Record<string, unknown>>) || []).slice(1).map((a) => String(a.token)).join(", ") || "—"}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {tab === "Metrics" && (
          <div className="space-y-2 font-mono text-[11px] text-zinc-600">
            <div className="rounded-lg border border-zinc-200 p-3">
              <p className="mb-2 text-zinc-400">RUN</p>
              <p>provider : {String(meta?.provider ?? "—")}</p>
              <p>model    : {String(meta?.model ?? "—")}</p>
              <p>temp     : {String(meta?.temperature ?? "—")}</p>
              <p>max_steps: {String(meta?.max_steps ?? "—")}</p>
              <p>thinking : {String(meta?.thinking ?? "—")}</p>
              <p>steps    : {String(done?.steps ?? "—")}</p>
              <p>latency  : {String(done?.latency_ms ?? usage ? `${(done as any)?.latency_ms ?? "—"} ms` : "—")}</p>
            </div>
            <div className="rounded-lg border border-zinc-200 p-3">
              <p className="mb-2 text-zinc-400">TOKENS</p>
              <p>prompt    : {String(usage?.prompt_tokens ?? "—")}</p>
              <p>completion: {String(usage?.completion_tokens ?? "—")}</p>
              <p>total     : {String(usage?.total_tokens ?? "—")}</p>
            </div>
            <div className="rounded-lg border border-zinc-200 p-3">
              <p className="mb-2 text-zinc-400">EVENTS</p>
              <p>total    : {trace.length}</p>
              <p>tools    : {trace.filter((e) => e.type === "tool_call").length}</p>
              <p>logprobs : {trace.filter((e) => e.type === "logprobs").length}</p>
              <p className={errors.length ? "text-red-500" : ""}>errors   : {errors.length}</p>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
