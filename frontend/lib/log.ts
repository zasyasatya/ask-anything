/* Derives a compact, machine-readable execution log from interpreter events.
   The interpreter must read like a log, not an essay: one row per meaningful
   step, with timing, status and a short technical detail. Long prose (deltas,
   thinking tokens, logprob payloads) is aggregated into counts instead of
   being dropped, so "the stream produced 412 chunks" stays visible without
   filling the panel with text. */
import type { TraceEvent } from "./types";
import { sourceOf, type ToolOutcome } from "./sources";

export type LogLevel = "info" | "llm" | "tool" | "warn" | "error" | "done";

export interface LogLine {
  key: number;
  /** ms since run start (null for the envelope events). */
  tMs: number | null;
  /** ms the step took, when the event reports one. */
  durMs: number | null;
  step: number | null;
  level: LogLevel;
  /** Who acted: run / llm / tool name. */
  actor: string;
  /** What happened, as a technical verb. */
  action: string;
  status: ToolOutcome | "n/a";
  /** Provenance badge for tool rows. */
  source?: ReturnType<typeof sourceOf>;
  /** One-line technical detail (sizes, ids, counters) — never a paragraph. */
  detail: string;
  /** Payload for the expandable raw-JSON view. */
  raw: Record<string, unknown>;
}

const SKIPPED = new Set(["delta", "logprobs", "thinking", "start", "agent_done"]);

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function bytes(n: number): string {
  return n < 1024 ? `${n} B` : `${(n / 1024).toFixed(1)} kB`;
}

/** Turn trace events into log rows (chronological, one per meaningful step). */
export function buildLog(events: TraceEvent[]): LogLine[] {
  const lines: LogLine[] = [];
  // Streaming fragments are folded into the row of the step that produced them.
  const stream = new Map<number, { deltas: number; chars: number; first: number | null; last: number | null }>();
  const think = new Map<number, { chunks: number; chars: number }>();

  for (const e of events) {
    const step = num(e.step) ?? 0;
    const t = num(e.t_ms);
    if (e.type === "delta") {
      const s = stream.get(step) || { deltas: 0, chars: 0, first: null, last: null };
      s.deltas += 1;
      s.chars += String(e.text ?? "").length;
      s.first = s.first ?? t;
      s.last = t;
      stream.set(step, s);
    } else if (e.type === "thinking") {
      const s = think.get(step) || { chunks: 0, chars: 0 };
      s.chunks += 1;
      s.chars += String(e.text ?? "").length;
      think.set(step, s);
    }
  }

  const seenStream = new Set<number>();
  const seenThink = new Set<number>();

  const push = (l: Omit<LogLine, "key">) => {
    lines.push({ key: lines.length, ...l });
  };

  /** Emit the folded stream row that belongs before the given step's response. */
  const flushBefore = (step: number) => {
    const s = stream.get(step);
    if (s && !seenStream.has(step)) {
      seenStream.add(step);
      push({
        tMs: s.first, step, level: "info", actor: "llm", action: "stream",
        status: "n/a",
        durMs: s.first != null && s.last != null ? Math.round(s.last - s.first) : null,
        detail: `${s.deltas} delta · ${bytes(s.chars)}`,
        raw: { deltas: s.deltas, chars: s.chars },
      });
    }
  };

  for (const e of events) {
    if (SKIPPED.has(e.type) && e.type !== "thinking") continue;
    const step = num(e.step);
    const t = num(e.t_ms);
    const dur = num(e.duration_ms);

    if (e.type === "thinking") {
      const s = think.get(step ?? 0);
      if (!s || seenThink.has(step ?? 0)) continue;
      seenThink.add(step ?? 0);
      push({
        tMs: t, step, durMs: null, level: "info", actor: "llm",
        action: "thinking", status: "n/a",
        detail: `${s.chunks} chunk · ${bytes(s.chars)} (raw di tab LLM)`,
        raw: { chunks: s.chunks, chars: s.chars },
      });
      continue;
    }

    switch (e.type) {
      case "meta":
        push({
          tMs: t, step, durMs: null, level: "info", actor: "run",
          action: "start", status: "n/a",
          detail: `${String(e.provider ?? "?")} · ${String(e.model ?? "?")} · T=${String(e.temperature ?? "?")} · max_steps=${String(e.max_steps ?? "?")}`,
          raw: { ...e },
        });
        break;
      case "prompt":
        push({
          tMs: t, step, durMs: null, level: "llm", actor: "llm",
          action: "prompt.assemble", status: "n/a",
          detail: `${String(e.message_count ?? (Array.isArray(e.messages) ? e.messages.length : "?"))} messages · ${String((e.tools as unknown[])?.length ?? "?")} tools`,
          raw: { message_count: e.message_count, tools: e.tools },
        });
        break;
      case "llm_request": {
        const samp = (e.sampling || {}) as Record<string, unknown>;
        push({
          tMs: t, step, durMs: null, level: "llm", actor: "llm",
          // `step` dari backend sudah 1-based → jangan ditambah lagi.
          action: `request${step != null ? ` #${step}` : ""}`, status: "n/a",
          detail: `${String(e.message_count ?? "?")} msg · temp=${String(samp.temperature ?? "?")} · max=${String(samp.max_tokens ?? "?")} · logprobs=${samp.logprobs ? "on" : "off"}`,
          raw: {
            message_count: e.message_count,
            sampling: samp,
            tools: e.tools,
            messages: e.messages,
          },
        });
        break;
      }
      case "llm_response": {
        // deltas/stream chunks belong to this response → flush just before it
        if (step != null) flushBefore(step);
        const calls = (e.tool_calls as Array<Record<string, unknown>>) || [];
        push({
          tMs: t, step, durMs: dur, level: "llm", actor: "llm",
          action: `response${step != null ? ` #${step}` : ""}`,
          status: calls.length ? "n/a" : "ok",
          detail: `finish=${String(e.finish_reason ?? "?")} · ${bytes(num(e.chars) ?? 0)}${calls.length ? ` · ${calls.length} tool_call` : ""}`,
          raw: { ...e },
        });
        break;
      }
      case "tool_call": {
        const name = String(e.name ?? "?");
        push({
          tMs: t, step, durMs: null, level: "tool", actor: name,
          action: "tool.exec", status: "running",
          source: sourceOf(name, e.source),
          detail: String(e.args_preview ?? JSON.stringify(e.arguments ?? {})),
          raw: { id: e.id, name, arguments: e.arguments },
        });
        break;
      }
      case "tool_result": {
        const name = String(e.name ?? "?");
        const ok = e.ok !== false;
        const hits = num(e.hits);
        const status: ToolOutcome = !ok ? "failed" : hits === 0 ? "empty" : "ok";
        push({
          tMs: t, step, durMs: dur, level: ok ? "tool" : "error",
          actor: name, action: "tool.result", status,
          source: sourceOf(name, e.source),
          detail: `${String(e.summary ?? "")}${hits != null ? ` · ${hits} hasil` : ""}${num(e.new_sources) ? ` · +${e.new_sources} sumber` : ""}`,
          raw: { id: e.id, ok: e.ok, hits: e.hits, error: e.error, data: e.data },
        });
        break;
      }
      case "sources":
        push({
          tMs: t, step, durMs: null, level: "info", actor: "registry",
          action: "sources", status: num(e.total) ? "ok" : "empty",
          detail: `${String(e.total ?? 0)} sumber terdaftar`,
          raw: { total: e.total, items: e.items },
        });
        break;
      case "usage":
        push({
          tMs: t, step, durMs: null, level: "info", actor: "llm",
          action: "usage", status: "n/a",
          detail: `prompt=${String(e.prompt_tokens ?? "?")} · completion=${String(e.completion_tokens ?? "?")} · total=${String(e.total_tokens ?? "?")}`,
          raw: { ...e },
        });
        break;
      case "citations": {
        const total = num(e.total) ?? 0;
        push({
          tMs: t, step, durMs: null,
          level: total ? (e.status === "cited" ? "info" : "warn") : "warn",
          actor: "verify", action: "citations",
          status: total ? (e.status === "cited" ? "ok" : "failed") : "empty",
          detail: `${String(e.status)} · ${((e.cited as number[]) || []).length}/${total} dikutip${((e.invalid as number[]) || []).length ? ` · ${((e.invalid as number[]) || []).length} nomor tak valid` : ""}`,
          raw: { ...e },
        });
        break;
      }
      case "note": {
        const status = String(e.status ?? "note");
        push({
          tMs: t, step, durMs: null, level: "warn", actor: "provider",
          action: `note:${status}`, status: status === "no-results" ? "empty" : "n/a",
          detail: String(e.message ?? ""),
          raw: { ...e },
        });
        break;
      }
      case "error":
        push({
          tMs: t, step, durMs: null, level: "error", actor: "provider",
          action: "error", status: "failed",
          detail: String(e.message ?? JSON.stringify(e)),
          raw: { ...e },
        });
        break;
      case "done":
        push({
          tMs: t, step, durMs: null, level: "done", actor: "run",
          action: "finish", status: "ok",
          detail: `steps=${String(e.steps ?? "?")} · ${String(e.stopped_reason ?? "?")} · ${num(e.latency_ms) ?? "?"} ms · ${bytes(String(e.answer ?? "").length)}`,
          raw: { ...e },
        });
        break;
      default:
        push({
          tMs: t, step, durMs: dur, level: "info", actor: "run",
          action: String(e.type), status: "n/a", detail: "", raw: { ...e },
        });
    }
  }
  return lines;
}

export const LEVEL_STYLE: Record<LogLevel, { text: string; bg: string; dot: string }> = {
  info: { text: "text-zinc-500", bg: "", dot: "bg-zinc-300" },
  llm: { text: "text-violet-300", bg: "", dot: "bg-violet-400" },
  tool: { text: "text-sky-300", bg: "", dot: "bg-sky-400" },
  warn: { text: "text-amber-300", bg: "", dot: "bg-amber-400" },
  error: { text: "text-red-300", bg: "", dot: "bg-red-400" },
  done: { text: "text-emerald-300", bg: "", dot: "bg-emerald-400" },
};

export const STATUS_STYLE: Record<string, string> = {
  ok: "bg-emerald-500/15 text-emerald-300",
  running: "bg-sky-500/15 text-sky-300 animate-pulse",
  empty: "bg-amber-500/15 text-amber-300",
  failed: "bg-red-500/15 text-red-300",
  "n/a": "bg-zinc-500/15 text-zinc-400",
};

/** `t+1.23s` — the left gutter of the log. */
export function fmtT(ms: number | null): string {
  if (ms == null) return "  —  ";
  return `t+${(ms / 1000).toFixed(2)}s`;
}

/** ` 341ms` / `  1.2s` — how long a step took. */
export function fmtDur(ms: number | null): string {
  if (ms == null) return "";
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(2)}s`;
}

/** Plain-text export (copy/download of the whole run log). */
export function logToText(lines: LogLine[]): string {
  return lines
    .map((l) =>
      [
        fmtT(l.tMs).padEnd(10),
        l.actor.padEnd(14),
        l.action.padEnd(16),
        String(l.status).padEnd(8),
        (l.durMs != null ? fmtDur(l.durMs).padStart(8) : "        "),
        l.detail,
      ].join(" ").trimEnd(),
    )
    .join("\n");
}
