"use client";
import Link from "next/link";
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import Sidebar from "@/components/Sidebar";
import AuthGate from "@/components/AuthGate";
import ProfileModal from "@/components/ProfileModal";
import Hero from "@/components/Hero";
import ChatView, { type DispMsg, type LiveState } from "@/components/ChatView";
import Interpreter from "@/components/Interpreter";
import SettingsModal from "@/components/SettingsModal";
import { AppSplash, BusyOverlay, Spinner } from "@/components/LoadingScreen";
import { ACCENTS } from "@/components/Composer";
import {
  getPolicy,
  getSettings,
  health,
  listConversations,
  loadConversation,
  streamChat,
  streamDeepResearch,
  streamRagQuery,
  updateSettings,
} from "@/lib/api";
import RagPanel from "@/components/RagPanel";
import DeepResearchCanvas, {
  type ResearchState,
  type ResearchProgress,
} from "@/components/DeepResearchCanvas";
import Composer from "@/components/Composer";
import { EMPTY_LIVE, reduceLive } from "@/lib/live";
import { useAuth } from "@/lib/auth";
import type {
  Conversation,
  PipelineMode,
  PolicyInfo,
  SettingsInfo,
  TraceEvent,
} from "@/lib/types";

/**
 * Riwayat → tampilan.
 *
 * Pesan `role:"tool"` tidak ditampilkan sendiri; hasilnya **dilipat** ke pesan
 * `assistant_toolcalls` pendahulunya sebagai `meta.tool_results`, sehingga chip
 * tool di riwayat menampilkan status yang sama seperti saat run berlangsung
 * (jumlah hasil, gagal, durasi) — bukan sekadar centang.
 */
function mapMessages(raw: Array<Record<string, unknown>>): DispMsg[] {
  const out: DispMsg[] = [];
  for (const m of raw) {
    const role = m.role as string;
    const meta = (m.meta as Record<string, unknown>) || {};
    if (role === "tool") {
      for (let i = out.length - 1; i >= 0; i--) {
        if (out[i].role !== "assistant_toolcalls") continue;
        const prev = out[i].meta || {};
        prev.tool_results = [
          ...((prev.tool_results as unknown[]) || []),
          {
            name: meta.name,
            source: meta.source,
            ok: meta.ok,
            hits: meta.hits,
            summary: meta.summary,
            error: meta.error,
            new_sources: meta.new_sources,
            duration_ms: meta.duration_ms,
            callId: meta.tool_call_id,
          },
        ];
        out[i].meta = prev;
        break;
      }
      continue;
    }
    if (!["user", "assistant", "assistant_toolcalls"].includes(role)) continue;
    out.push({ role, content: (m.content as string) || "", meta });
  }
  return out;
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
  const [showProfile, setShowProfile] = useState(false);
  const [settings, setSettings] = useState<SettingsInfo | null>(null);
  const [llm, setLlm] = useState<boolean | null>(null);
  const [localState, setLocalState] = useState<string | null>(null);
  const [accent, setAccent] = useState("indigo");
  // ---- pipeline governance (policy publik) + mode aktif ----
  const [policy, setPolicy] = useState<PolicyInfo | null>(null);
  const [mode, setMode] = useState<PipelineMode>("text");
  // ---- deep research mode ----
  const [deepResearch, setDeepResearch] = useState(false);
  const [researchState, setResearchState] = useState<ResearchState | null>(null);
  const [researchProgress, setResearchProgress] = useState<ResearchProgress | null>(null);
  const [researchStreaming, setResearchStreaming] = useState(false);
  // ---- loading screen: aplikasi tidak pernah tampil setengah-hidup ----
  const [booting, setBooting] = useState(true);
  const [bootError, setBootError] = useState<string | null>(null);
  const [openingId, setOpeningId] = useState<string | null>(null);

  const { user, capabilities } = useAuth();
  const isAdmin = capabilities?.is_admin ?? false;
  // Member tidak menyentuh model offline/setelan provider: bannernya tidak
  // relevan (dan memang akan ditolak server), jadi jangan ditampilkan.
  const showProviderBanners = isAdmin;

  const refresh = useCallback(async () => {
    const [cs, st, h, pol] = await Promise.all([
      listConversations(),
      getSettings(),
      health(),
      getPolicy().catch(() => null),
    ]);
    setConversations(cs);
    setSettings(st);
    setLlm(Boolean(h.llm_reachable));
    setLocalState(String(h.local_llm_state || "idle"));
    if (pol) setPolicy(pol);
  }, []);

  useEffect(() => {
    // Layar splash tetap tampil sampai data pertama benar-benar selesai
    // dimuat; bila backend mati, splash berubah jadi layar error + retry.
    let cancelled = false;
    (async () => {
      try {
        await refresh();
        if (!cancelled) {
          setBootError(null);
          setBooting(false);
        }
      } catch (e) {
        if (cancelled) return;
        const text = String(e);
        // 401 = belum login (bukan backend mati): biarkan AuthGate mengarahkan
        // ke /login, jangan tampilkan layar "Backend tidak bisa dihubungi".
        if (text.includes("401")) {
          setBootError(null);
          setBooting(false);
        } else {
          setBootError(text);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  // Loading screen model offline: selama engine memuat model, banner &
  // status diperbarui otomatis sampai state-nya berubah (ready/error).
  useEffect(() => {
    if (localState !== "loading") return;
    const t = window.setInterval(() => {
      refresh().catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(t);
  }, [localState, refresh]);

  async function openConversation(id: string) {
    setActiveId(id);
    setOpeningId(id);
    try {
      const d = await loadConversation(id);
      setMessages(mapMessages(d.messages));
      setTrace(d.trace);
      setLive(EMPTY_LIVE);
    } catch (e) {
      console.error(e);
    } finally {
      setOpeningId(null);
    }
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

    const collected: TraceEvent[] = [];
    const useRag = mode === "rag";
    try {
      const stream = useRag
        ? streamRagQuery(text, cid, (ev) => handler(ev))
        : streamChat(text, cid, (ev) => handler(ev), mode);

      function handler(ev: TraceEvent) {
        collected.push(ev);
        setTrace((t) => [...t, ev]);
        if (ev.type === "start") {
          cid = ev.conversation_id as string;
          setActiveId(cid);
        } else {
          // Satu reducer murni (lib/live.ts) untuk seluruh event streaming —
          // termasuk sumber bernomor dan artefak diagram dari tool.
          setLive((l) => reduceLive(l, ev));
        }
      }

      await stream;
    } catch (e) {
      const failure = { type: "error", message: String(e) };
      collected.push(failure);
      setLive((l) => reduceLive(l, failure));
    }

    // Status live yang sama, direkonstruksi dari event yang sudah diterima:
    // dipakai bila run gagal di tengah jalan (tidak ada pesan assistant yang
    // tersimpan) supaya jawaban/kesalahan tidak hilang begitu saja.
    const finalLive = collected.reduce(
      (acc, ev) => reduceLive(acc, ev),
      EMPTY_LIVE
    );

    setStreaming(false);
    await refresh().catch(() => undefined);
    if (cid) {
      const d = await loadConversation(cid);
      const shown = mapMessages(d.messages);
      const persisted = shown.some(
        (m) => m.role === "assistant" && m.content.trim() !== ""
      );
      if (!persisted && finalLive.answer.trim() !== "") {
        shown.push({ role: "assistant", content: finalLive.answer });
      }
      setMessages(shown);
      setTrace(d.trace);
    }
    setLive(EMPTY_LIVE);
  }

  async function sendDeepResearch(topicOverride?: string) {
    const topic = (topicOverride ?? input).trim();
    if (!topic || researchStreaming) return;
    setInput("");
    setResearchStreaming(true);
    setResearchState(null);
    setResearchProgress(null);
    setShowInt(true);
    setTrace([]);

    const toolEvents: Array<Record<string, unknown>> = [];
    const queries: string[] = [];

    try {
      await streamDeepResearch(topic, (ev) => {
        const type = String(ev.type || "");

        if (type === "research_phase") {
          const p: ResearchProgress = {
            phase: String(ev.phase || ""),
            query: ev.query as string | undefined,
            query_index: ev.query_index as number | undefined,
            total_queries: ev.total_queries as number | undefined,
            queries_list: queries.length > 0 ? queries : undefined,
          };
          setResearchProgress(p);
        } else if (type === "research_tool") {
          toolEvents.push(ev);
          const callId = `dr-${toolEvents.length}`;
          setTrace((t) => [
            ...t,
            {
              type: "tool_call",
              name: String(ev.name || ""),
              arguments: { query: ev.query, url: ev.url },
              id: callId,
              source: "browser",
            },
          ]);
          setTrace((t) => [
            ...t,
            {
              type: "tool_result",
              name: String(ev.name || ""),
              id: callId,
              ok: Boolean(ev.ok),
              hits: ev.hits as number | undefined,
              summary: `${ev.name}: ${ev.hits ?? 0} hasil`,
              duration_ms: ev.duration_ms as number,
              source: "browser",
            },
          ]);
        } else if (type === "start") {
          if (ev.queries) {
            queries.push(...(ev.queries as string[]));
          }
          setResearchProgress({
            phase: "expanding",
            queries_list: ev.queries as string[],
          });
        } else if (type === "research_done") {
          const state: ResearchState = {
            topic: String(ev.topic || topic),
            nodes: (ev.nodes as ResearchState["nodes"]) || [],
            groups: (ev.groups as ResearchState["groups"]) || null,
            queries: (ev.queries as string[]) || queries,
            tool_events: (ev.tool_events as ResearchState["tool_events"]) || [],
            summary: String(ev.summary || ""),
            total_nodes: Number(ev.total_nodes || 0),
            total_sources: Number(ev.total_sources || 0),
            elapsed_ms: Number(ev.elapsed_ms || 0),
          };
          setResearchState(state);
        } else if (type === "error") {
          setResearchState({
            topic,
            nodes: [],
            groups: null,
            queries: [],
            tool_events: [],
            summary: `Error: ${ev.message}`,
            total_nodes: 0,
            total_sources: 0,
            elapsed_ms: 0,
          });
        }
      });
    } catch (e) {
      setResearchState({
        topic,
        nodes: [],
        groups: null,
        queries: [],
        tool_events: [],
        summary: `Error: ${String(e)}`,
        total_nodes: 0,
        total_sources: 0,
        elapsed_ms: 0,
      });
    }

    setResearchStreaming(false);
    setResearchProgress(null);
  }

  const accentVars = {
    "--accent": ACCENTS[accent].accent,
    "--accent-soft": ACCENTS[accent].soft,
    "--accent-ring": ACCENTS[accent].ring,
  } as CSSProperties;

  const inChat = activeId !== null || messages.length > 0 || streaming || researchState !== null || researchStreaming;

  // Loading screen penuh sampai startup selesai (atau error + retry).
  // Dibungkus AuthGate juga: tanpa sesi, splash tidak perlu muncul sama sekali
  // — AuthGate langsung mengalihkan ke halaman login.
  if (booting) {
    return (
      <AuthGate>
        <div style={accentVars}>
          <AppSplash
            error={bootError}
            onRetry={bootError ? () => {
              setBootError(null); // splash kembali ke mode spinner
              refresh()
                .then(() => setBooting(false))
                .catch((e) => setBootError(String(e)));
            } : undefined}
          />
        </div>
      </AuthGate>
    );
  }

  return (
    <AuthGate>
    <div style={accentVars} className="flex h-screen overflow-hidden text-zinc-900">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={openConversation}
        onNew={newChat}
        onSettings={() => (isAdmin ? setShowSettings(true) : setShowProfile(true))}
        llmReachable={llm}
        user={user}
        capabilities={capabilities}
      />

      <main className="relative flex min-w-0 flex-1 flex-col bg-[#f7f7f8]">
        {openingId && <BusyOverlay label="Membuka percakapan…" />}
        <header className="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-zinc-200/70 bg-white/60 px-4 backdrop-blur">
          <p className="min-w-0 flex-1 truncate text-sm text-zinc-500">
            {conversations.find((c) => c.id === activeId)?.title || "New chat"}
          </p>
          {/* shrink-0 + nowrap: saat Interpreter membuka (460px hilang), tombol
              tidak boleh menimpa judul atau bertumpuk satu sama lain. */}
          <div className="flex shrink-0 items-center gap-2">
            {settings &&
              (isAdmin ? (
                <span
                  title={`${settings.provider} · ${settings.model}`}
                  className="hidden max-w-[190px] truncate whitespace-nowrap rounded-md border border-zinc-200 bg-zinc-50 px-2 py-1 font-mono text-[10.5px] text-zinc-500 sm:block"
                >
                  {settings.provider} · {settings.model}
                </span>
              ) : (
                // Member: provider dikunci ke OpenAI oleh policy role — model
                // offline & setelan provider ditolak server (403).
                <span
                  data-testid="member-provider-badge"
                  title="Role member memakai model OpenAI; model offline dan setelan provider hanya untuk admin."
                  className="hidden max-w-[190px] truncate whitespace-nowrap rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 font-mono text-[10.5px] text-emerald-700 sm:block"
                >
                  openai · akses member
                </span>
              ))}
            <Link
              href="/panduan"
              className="hidden shrink-0 rounded-lg border border-zinc-300 bg-white/70 px-3 py-1.5 text-xs font-medium text-zinc-600 transition hover:bg-white sm:block"
            >
              Panduan
            </Link>
            <Link
              href="/developer"
              className="hidden shrink-0 rounded-lg border border-zinc-300 bg-white/70 px-3 py-1.5 text-xs font-medium text-zinc-600 transition hover:bg-white lg:block"
            >
              Developer
            </Link>
            <a
              href="/slides/slides-cara-kerja.html"
              target="_blank"
              rel="noreferrer"
              className="hidden shrink-0 whitespace-nowrap rounded-lg border border-zinc-300 bg-white/70 px-3 py-1.5 text-xs font-medium text-zinc-600 transition hover:bg-white xl:block"
            >
              Docs & Slides →
            </a>
            <button
              onClick={() => setShowInt((v) => !v)}
              className={`shrink-0 whitespace-nowrap rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                showInt
                  ? "border-zinc-800 bg-zinc-900 text-white"
                  : "border-zinc-300 bg-white/70 text-zinc-600 hover:bg-white"
              }`}
            >
              Mechanistic Interpreter →
            </button>
          </div>
        </header>

        {showProviderBanners &&
          settings &&
          settings.provider === "huggingface" &&
          settings.hf_mode !== "server" &&
          localState === "loading" && (
          <div className="flex items-center justify-between gap-3 border-b border-sky-200 bg-sky-50 px-4 py-2 text-xs text-sky-800">
            <span className="flex items-center gap-2">
              <Spinner size={13} className="shrink-0 text-sky-600" />
              Model offline
              {settings.hf_model ? (
                <>
                  {" "}
                  <code className="rounded bg-sky-100 px-1">{settings.hf_model}</code>
                </>
              ) : null}{" "}
              sedang dimuat ke memori — jawaban akan dimulai otomatis begitu
              model siap. Kamu sudah bisa menulis pertanyaan sekarang.
            </span>
          </div>
        )}

        {showProviderBanners &&
          settings &&
          llm === false &&
          !(
            settings.provider === "huggingface" &&
            settings.hf_mode !== "server" &&
            localState === "loading"
          ) && (
          <div className="flex items-center justify-between gap-3 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
            <span>
              {settings.provider === "huggingface" && settings.hf_mode !== "server" ? (
                <>
                  Belum ada model offline yang dimuat
                  {settings.hf_model ? (
                    <>
                      {" "}(<code className="rounded bg-amber-100 px-1">{settings.hf_model}</code>)
                    </>
                  ) : null}
                  . Buka <b>Settings → Model offline (HuggingFace)</b>, unduh model,
                  lalu klik <b>Pakai &amp; muat</b>.
                </>
              ) : settings.provider === "huggingface" ? (
                <>
                  Server LLM tidak terjangkau di{" "}
                  <code className="rounded bg-amber-100 px-1">{settings.hf_base_url}</code>.
                  Jalankan server OpenAI-compatible-nya, atau pindah ke inference
                  lokal lewat Settings.
                </>
              ) : (
                <>
                  Endpoint <code className="rounded bg-amber-100 px-1">{settings.openai_base_url}</code>{" "}
                  tidak menjawab. Buka <b>Settings → Test koneksi</b> untuk melihat
                  status &amp; pesan server apa adanya.
                </>
              )}
            </span>
            <span className="flex shrink-0 gap-2">
              <button
                onClick={() => setShowSettings(true)}
                className="rounded-md border border-amber-300 bg-white px-2.5 py-1 font-medium text-amber-700 hover:bg-amber-100"
              >
                Buka Settings
              </button>
              <button
                onClick={async () => {
                  const s = await updateSettings({ provider: "mock" });
                  setSettings(s);
                  refresh().catch(() => undefined);
                }}
                className="rounded-md border border-amber-300 bg-white px-2.5 py-1 font-medium text-amber-700 hover:bg-amber-100"
              >
                Pakai mode mock
              </button>
            </span>
          </div>
        )}

        {inChat ? (
          deepResearch || researchState || researchStreaming ? (
            <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
              <div className="flex-1 overflow-y-auto">
                <div className="mx-auto w-full max-w-[1180px] px-6 py-6 md:px-10">
                  {/* Topic header */}
                  {researchState && (
                    <div className="mb-4 flex items-center gap-3">
                      <button
                        onClick={() => {
                          setResearchState(null);
                          setResearchProgress(null);
                          setResearchStreaming(false);
                        }}
                        className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-600 transition hover:bg-zinc-50"
                      >
                        ← Kembali
                      </button>
                      <h2 className="text-lg font-semibold text-zinc-900">
                        Deep Research: {researchState.topic}
                      </h2>
                    </div>
                  )}
                  <DeepResearchCanvas
                    state={researchState}
                    progress={researchProgress}
                    streaming={researchStreaming}
                  />
                </div>
              </div>
              {/* Composer for new research */}
              <div className="border-t border-zinc-200/70 bg-[#f7f7f8]/80 px-6 py-4 backdrop-blur md:px-10">
                <div className="mx-auto w-full max-w-[1180px]">
                  <Composer
                    compact
                    value={input}
                    onChange={setInput}
                    onSend={() => sendDeepResearch()}
                    disabled={researchStreaming || streaming}
                    accent={accent}
                    onAccent={setAccent}
                    deepResearch={deepResearch}
                    onDeepResearch={setDeepResearch}
                  />
                </div>
              </div>
            </div>
          ) : (
          <>
            {mode === "rag" && policy?.modes?.rag !== false && (
              <div className="shrink-0 px-4 md:px-6 pt-3">
                <RagPanel maxUploadMb={policy?.rag?.max_upload_mb} />
              </div>
            )}
            <ChatView
              messages={messages}
              live={live}
              streaming={streaming}
              input={input}
              setInput={setInput}
              onSend={() => send()}
              accent={accent}
              onAccent={setAccent}
              deepResearch={deepResearch}
              onDeepResearch={setDeepResearch}
              policy={policy}
              mode={mode}
              onMode={setMode}
              ragMode={mode === "rag"}
              conversationId={activeId}
              feedbackEnabled={policy?.feedback?.enabled !== false}
            />
          </>
          )
        ) : (
          <Hero
            input={input}
            setInput={setInput}
            onSend={() => {
              if (deepResearch) {
                sendDeepResearch();
              } else {
                send();
              }
            }}
            streaming={streaming || researchStreaming}
            accent={accent}
            onAccent={setAccent}
            deepResearch={deepResearch}
            onDeepResearch={setDeepResearch}
            policy={policy}
            mode={mode}
            onMode={setMode}
            showRag={mode === "rag" && policy?.modes?.rag !== false}
          />
        )}
      </main>

      {showInt && <Interpreter trace={trace} streaming={streaming || researchStreaming} onClose={() => setShowInt(false)} />}

      {showSettings && isAdmin && (
        <SettingsModal
          settings={settings}
          onSaved={(s) => {
            setSettings(s);
            refresh().catch(() => undefined);
          }}
          onClose={() => setShowSettings(false)}
        />
      )}

      {showProfile && <ProfileModal onClose={() => setShowProfile(false)} />}
    </div>
    </AuthGate>
  );
}
