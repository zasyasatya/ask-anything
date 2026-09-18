"use client";
/* Konsol Admin Ask Anything — mengatur pipeline sebelum dipublish ke user:
   ringkasan, mode & tool, memori, artifact, feedback, dokumentasi.

   Auth: bila backend diset `ASK_ADMIN_TOKEN`, header X-Admin-Token wajib —
   token disimpan di localStorage browser ini saja (tidak pernah dikirim ke
   tempat lain). Tanpa token di backend, konsol terbuka (mode lokal/demo). */
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  adminArtifacts,
  adminFeedback,
  adminMemories,
  adminOverview,
} from "@/lib/api";
import type {
  ArtifactItem,
  FeedbackItem,
  FullPolicy,
  MemoryItem,
} from "@/lib/types";
import PipelineTab from "./PipelineTab";
import MemoryTab from "./MemoryTab";
import ArtifactTab from "./ArtifactTab";
import FeedbackTab from "./FeedbackTab";
import { Card, Stat, fmtBytes } from "./ui";

const TABS = [
  { id: "overview", label: "Ringkasan" },
  { id: "pipeline", label: "Pipeline" },
  { id: "memory", label: "Memori" },
  { id: "artifacts", label: "Artifact" },
  { id: "feedback", label: "Feedback" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function AdminConsole() {
  const [tab, setTab] = useState<TabId>("overview");
  const [overview, setOverview] = useState<Awaited<
    ReturnType<typeof adminOverview>
  > | null>(null);
  const [policy, setPolicy] = useState<FullPolicy | null>(null);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([]);
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);
  const [fbStats, setFbStats] = useState<{
    total: number;
    up: number;
    down: number;
    ratio_up: number | null;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, mem, art, fb] = await Promise.all([
        adminOverview(""),
        adminMemories(""),
        adminArtifacts(""),
        adminFeedback(""),
      ]);
      setOverview(ov);
      setPolicy(ov.policy);
      setMemories(mem);
      setArtifacts(art);
      setFeedback(fb.feedback);
      setFbStats(fb.stats as typeof fbStats);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  const counts = overview?.counts;

  return (
    <div className="min-h-screen bg-[#f7f7f8]">
      {/* Topbar */}
      <header className="sticky top-0 z-20 border-b border-zinc-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-5 py-3">
          <Link
            href="/"
            className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50"
          >
            ← Chat
          </Link>
          <h1 className="text-[15px] font-semibold text-zinc-800">
            Admin — Pipeline &amp; Governance
          </h1>
          <span
            className={`ml-auto rounded-lg border px-2.5 py-1 text-xs font-medium ${
              overview?.admin_protected
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-amber-200 bg-amber-50 text-amber-700"
            }`}
            title="Set ASK_ADMIN_TOKEN di backend untuk melindungi konsol di deployment publik"
          >
            {overview?.admin_protected
              ? "🔒 Dilindungi token"
              : "⚠️ Terbuka (set ASK_ADMIN_TOKEN)"}
          </span>
          <button
            onClick={refreshAll}
            className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50"
          >
            {loading ? "Memuat…" : "⟳ Muat ulang"}
          </button>
        </div>
        <nav className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-5 pb-2">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`rounded-lg px-3 py-1.5 text-[13px] font-medium transition ${
                tab === t.id
                  ? "bg-accent-soft text-accent"
                  : "text-zinc-500 hover:bg-zinc-100"
              }`}
            >
              {t.label}
            </button>
          ))}
          <Link
            href="/tasks"
            className="ml-auto rounded-lg px-3 py-1.5 text-[13px] font-medium text-zinc-500 hover:bg-zinc-100"
          >
            🗂️ Tasks
          </Link>
          <a
            href="/slides/slides-admin-pipeline.html"
            target="_blank"
            rel="noreferrer"
            className="rounded-lg px-3 py-1.5 text-[13px] font-medium text-zinc-500 hover:bg-zinc-100"
          >
            📊 Docs cara kerja ↗
          </a>
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-6">
        {error && (
          <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
            {error} — pastikan backend berjalan.
          </p>
        )}

        {tab === "overview" && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Stat
                label="Percakapan"
                value={counts?.conversations ?? "—"}
                hint={`${counts?.messages ?? 0} pesan`}
              />
              <Stat
                label="Event interpreter"
                value={counts?.trace_events ?? "—"}
                hint="semua langkah terecord (always-on)"
                tone="indigo"
              />
              <Stat
                label="Feedback"
                value={counts?.feedback_total ?? "—"}
                hint={`${counts?.feedback_up ?? 0} 👍 · ${
                  counts?.feedback_down ?? 0
                } 👎`}
                tone={
                  (overview?.feedback.ratio_up ?? 1) >= 0.7
                    ? "green"
                    : counts?.feedback_total
                    ? "amber"
                    : "zinc"
                }
              />
              <Stat
                label="Artifact"
                value={counts?.artifacts ?? "—"}
                hint={fmtBytes(counts?.artifact_bytes ?? 0)}
              />
              <Stat
                label="Dokumen RAG siap"
                value={counts?.rag_documents_ready ?? "—"}
                hint={`${counts?.rag_documents ?? 0} total terunggah`}
              />
              <Stat
                label="Memori aktif"
                value={counts?.memories ?? "—"}
                hint="admin / AI / feedback"
              />
              <Stat
                label="Provider"
                value={overview?.provider ?? "—"}
                hint={overview?.model}
              />
              <Stat
                label="Mode aktif"
                value={
                  policy
                    ? Object.values(policy.modes).filter(Boolean).length
                    : "—"
                }
                hint="dari 6 mode pipeline"
                tone="green"
              />
            </div>

            <Card
              title="Siap publish? Checklist cepat"
              subtitle="Kebijakan minimum sebelum user eksternal dipakai masuk."
            >
              <ul className="space-y-1.5 text-[13px] text-zinc-600">
                <li>
                  {(overview?.admin_protected && "✅") || "⬜"} Konsol admin
                  dilindungi <code>ASK_ADMIN_TOKEN</code>
                </li>
                <li>
                  ✅ Interpreter selalu-on — setiap langkah terecord di SQLite
                  ({counts?.trace_events ?? 0} event)
                </li>
                <li>
                  {(counts?.feedback_total ?? 0) > 0 ? "✅" : "⬜"} Feedback
                  👍/👎 sudah terisi & ditinjau (rasio positif{" "}
                  {overview?.feedback.ratio_up != null
                    ? `${Math.round(overview.feedback.ratio_up * 100)}%`
                    : "—"}
                  )
                </li>
                <li>
                  {(counts?.rag_documents_ready ?? 0) > 0 ? "✅" : "⬜"} Minimal
                  satu dokumen RAG siap
                </li>
                <li>
                  ⬜ Review tab <b>Pipeline</b>: matikan mode/tool yang belum
                  mau dipublish
                </li>
              </ul>
            </Card>
          </div>
        )}

        {tab === "pipeline" && policy && (
          <PipelineTab policy={policy} onPolicyChange={setPolicy} />
        )}

        {tab === "memory" && (
          <MemoryTab memories={memories} onChanged={refreshAll} />
        )}

        {tab === "artifacts" && (
          <ArtifactTab artifacts={artifacts} onChanged={refreshAll} />
        )}

        {tab === "feedback" && (
          <FeedbackTab
            feedback={feedback}
            stats={fbStats}
            onChanged={refreshAll}
          />
        )}
      </main>
    </div>
  );
}
