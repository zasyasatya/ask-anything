"use client";
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import Sidebar from "@/components/Sidebar";
import Hero from "@/components/Hero";
import ChatView, { type DispMsg, type LiveState } from "@/components/ChatView";
import Interpreter from "@/components/Interpreter";
import SettingsModal from "@/components/SettingsModal";
import { ACCENTS } from "@/components/Composer";
import {
  getSettings,
  health,
  listConversations,
  loadConversation,
  streamChat,
  updateSettings,
} from "@/lib/api";
import type { Conversation, SettingsInfo, TraceEvent } from "@/lib/types";

const EMPTY_LIVE: LiveState = { answer: "", thinking: "", tools: [] };

function mapMessages(raw: Array<Record<string, unknown>>): DispMsg[] {
  return raw
    .filter((m) => ["user", "assistant", "assistant_toolcalls"].includes(m.role as string))
    .map((m) => ({
      role: m.role as string,
      content: (m.content as string) || "",
      meta: (m.meta as Record<string, unknown>) || {},
    }));
}

export default function Page() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DispMsg[]>([]);
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [live, setLive] = useState<LiveState>(EMPTY_LIVE);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [showInt, setShowInt] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState<SettingsInfo | null>(null);
  const [llm, setLlm] = useState<boolean | null>(null);
  const [accent, setAccent] = useState("indigo");

  const refresh = useCallback(async () => {
    const [cs, st, h] = await Promise.all([listConversations(), getSettings(), health()]);
    setConversations(cs);
    setSettings(st);
    setLlm(Boolean(h.llm_reachable));
  }, []);

  useEffect(() => {
    refresh().catch(console.error);
  }, [refresh]);

  async function openConversation(id: string) {
    setActiveId(id);
    const d = await loadConversation(id);
    setMessages(mapMessages(d.messages));
    setTrace(d.trace);
    setLive(EMPTY_LIVE);
  }

  function newChat() {
    setActiveId(null);
    setMessages([]);
    setTrace([]);
    setLive(EMPTY_LIVE);
  }

  async function send(textOverride?: string) {
    const text = (textOverride ?? input).trim();
    if (!text || streaming) return;
    setInput("");
    setStreaming(true);
    setShowInt(true);
    setMessages((m) => [...m, { role: "user", content: text }]);
    setLive(EMPTY_LIVE);
    setTrace([]);
    let cid: string | null = activeId;

    try {
      await streamChat(text, cid, (ev) => {
        setTrace((t) => [...t, ev]);
        if (ev.type === "start") {
          cid = ev.conversation_id as string;
          setActiveId(cid);
        } else if (ev.type === "thinking") {
          setLive((l) => ({ ...l, thinking: l.thinking + (ev.text as string) }));
        } else if (ev.type === "delta") {
          setLive((l) => ({ ...l, answer: l.answer + (ev.text as string) }));
        } else if (ev.type === "tool_call") {
          setLive((l) => ({
            ...l,
            tools: [...l.tools, { name: ev.name as string, status: "running" }],
          }));
        } else if (ev.type === "tool_result") {
          setLive((l) => ({
            ...l,
            tools: l.tools.map((t, i) =>
              i === l.tools.length - 1
                ? { ...t, status: "done", summary: ev.summary as string }
                : t
            ),
          }));
        } else if (ev.type === "error") {
          setLive((l) => ({ ...l, answer: l.answer + `\n\n> ⚠️ ${ev.message}` }));
        }
      });
    } catch (e) {
      setLive((l) => ({ ...l, answer: l.answer + `\n\n> ⚠️ ${String(e)}` }));
    }

    setStreaming(false);
    await refresh().catch(() => undefined);
    if (cid) {
      const d = await loadConversation(cid);
      setMessages(mapMessages(d.messages));
      setTrace(d.trace);
    }
    setLive(EMPTY_LIVE);
  }

  const accentVars = {
    "--accent": ACCENTS[accent].accent,
    "--accent-soft": ACCENTS[accent].soft,
    "--accent-ring": ACCENTS[accent].ring,
  } as CSSProperties;

  const inChat = activeId !== null || messages.length > 0 || streaming;

  return (
    <div style={accentVars} className="flex h-screen overflow-hidden text-zinc-900">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={openConversation}
        onNew={newChat}
        onSettings={() => setShowSettings(true)}
        llmReachable={llm}
      />

      <main className="flex min-w-0 flex-1 flex-col bg-[#f7f7f8]">
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-zinc-200/70 bg-white/60 px-4 backdrop-blur">
          <p className="truncate text-sm text-zinc-500">
            {conversations.find((c) => c.id === activeId)?.title || "New chat"}
          </p>
          <div className="flex items-center gap-2">
            {settings && (
              <span className="hidden rounded-md border border-zinc-200 bg-zinc-50 px-2 py-1 font-mono text-[10.5px] text-zinc-500 sm:block">
                {settings.provider} · {settings.model}
              </span>
            )}
            <button
              onClick={() => setShowInt((v) => !v)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                showInt
                  ? "border-zinc-800 bg-zinc-900 text-white"
                  : "border-zinc-300 bg-white/70 text-zinc-600 hover:bg-white"
              }`}
            >
              Mechanistic Interpreter →
            </button>
          </div>
        </header>

        {settings?.provider === "huggingface" && llm === false && (
          <div className="flex items-center justify-between gap-3 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
            <span>
              LLM lokal tidak terjangkau di {settings.hf_base_url}. Jalankan{" "}
              <code className="rounded bg-amber-100 px-1">llama-server</code> atau{" "}
              <code className="rounded bg-amber-100 px-1">python run.py --demo</code>.
            </span>
            <button
              onClick={async () => {
                const s = await updateSettings({ provider: "mock" });
                setSettings(s);
                refresh().catch(() => undefined);
              }}
              className="shrink-0 rounded-md border border-amber-300 bg-white px-2.5 py-1 font-medium text-amber-700 hover:bg-amber-100"
            >
              Pakai mode mock
            </button>
          </div>
        )}

        {inChat ? (
          <ChatView
            messages={messages}
            live={live}
            streaming={streaming}
            input={input}
            setInput={setInput}
            onSend={() => send()}
            accent={accent}
            onAccent={setAccent}
          />
        ) : (
          <Hero
            input={input}
            setInput={setInput}
            onSend={() => send()}
            streaming={streaming}
            accent={accent}
            onAccent={setAccent}
          />
        )}
      </main>

      {showInt && <Interpreter trace={trace} streaming={streaming} onClose={() => setShowInt(false)} />}

      {showSettings && (
        <SettingsModal
          settings={settings}
          onSaved={(s) => {
            setSettings(s);
            refresh().catch(() => undefined);
          }}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  );
}
