"use client";
import { useEffect, useRef } from "react";
import Markdown from "@/lib/markdown";
import Logo from "./Logo";
import Composer from "./Composer";

export interface DispMsg {
  role: string;
  content: string;
  meta?: Record<string, unknown>;
}

export interface LiveState {
  answer: string;
  thinking: string;
  tools: { name: string; status: string; summary?: string }[];
}

function ToolChips({ tools }: { tools: { name: string; status: string; summary?: string }[] }) {
  if (!tools.length) return null;
  return (
    <div className="mb-2 flex flex-wrap gap-1.5">
      {tools.map((t, i) => (
        <span
          key={i}
          title={t.summary}
          className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-mono text-[10.5px] ${
            t.status === "running"
              ? "animate-pulse border-sky-200 bg-sky-50 text-sky-600"
              : "border-emerald-200 bg-emerald-50 text-emerald-600"
          }`}
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L4 17v3h3l5.3-5.3a4 4 0 0 0 5.4-5.4l-2.9 2.9-2.1-2.1 2.9-2.9z" />
          </svg>
          {t.name}
          {t.status === "running" ? "…" : " ✓"}
        </span>
      ))}
    </div>
  );
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
}: {
  messages: DispMsg[];
  live: LiveState;
  streaming: boolean;
  input: string;
  setInput: (v: string) => void;
  onSend: () => void;
  accent: string;
  onAccent: (a: string) => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, live.answer, live.tools.length]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-6 py-8">
          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="mb-6 flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-md bg-accent-soft px-4 py-2.5 text-[15px] leading-7 text-zinc-800">
                  {m.content}
                </div>
              </div>
            ) : m.role === "assistant_toolcalls" ? (
              <div key={i} className="mb-4 flex items-start gap-3">
                <div className="mt-1 shrink-0"><Logo size={18} /></div>
                <ToolChips
                  tools={((m.meta?.tool_calls as Array<{ name: string }>) || []).map((t) => ({
                    name: t.name,
                    status: "done",
                  }))}
                />
              </div>
            ) : (
              <div key={i} className="mb-6 flex items-start gap-3">
                <div className="mt-1 shrink-0"><Logo size={18} /></div>
                <div className="min-w-0 max-w-[92%] flex-1">
                  <Markdown text={m.content} />
                </div>
              </div>
            )
          )}

          {streaming && (
            <div className="mb-6 flex items-start gap-3">
              <div className="mt-1 shrink-0"><Logo size={18} /></div>
              <div className="min-w-0 max-w-[92%] flex-1">
                {live.thinking && !live.answer && (
                  <p className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 font-mono text-[11px] leading-5 text-amber-700">
                    💭 {live.thinking}
                  </p>
                )}
                <ToolChips tools={live.tools} />
                {live.answer ? (
                  <>
                    <Markdown text={live.answer} />
                    <span className="ml-0.5 inline-block h-4 w-[7px] animate-pulse rounded-sm bg-accent align-middle" />
                  </>
                ) : (
                  !live.tools.length && (
                    <span className="inline-block h-4 w-[7px] animate-pulse rounded-sm bg-accent" />
                  )
                )}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="border-t border-zinc-200/70 bg-[#f7f7f8]/80 px-6 py-4 backdrop-blur">
        <div className="mx-auto w-full max-w-3xl">
          <Composer
            compact
            value={input}
            onChange={setInput}
            onSend={onSend}
            disabled={streaming}
            accent={accent}
            onAccent={onAccent}
          />
        </div>
      </div>
    </div>
  );
}
