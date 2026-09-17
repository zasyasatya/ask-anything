"use client";
/* Tab Feedback: seluruh 👍/👎 + komentar user, statistiknya, dan alur
   feedback → pedoman (mengatur ulang perilaku AI). */
import { useState } from "react";
import {
  adminApplyFeedback,
  adminDeleteFeedback,
  adminSetFeedbackStatus,
} from "@/lib/api";
import type { FeedbackItem } from "@/lib/types";
import { Card, fmtTime } from "./ui";

const STATUS_META: Record<string, { label: string; tone: string }> = {
  new: { label: "baru", tone: "bg-sky-100 text-sky-700" },
  reviewed: { label: "direview", tone: "bg-zinc-200 text-zinc-600" },
  applied: { label: "jadi pedoman", tone: "bg-emerald-100 text-emerald-700" },
  dismissed: { label: "diabaikan", tone: "bg-zinc-100 text-zinc-400" },
};

export default function FeedbackTab({
  feedback,
  stats,
  onChanged,
}: {
  feedback: FeedbackItem[];
  stats: {
    total: number;
    up: number;
    down: number;
    ratio_up: number | null;
  } | null;
  onChanged: () => void;
}) {
  const [filter, setFilter] = useState<"all" | "up" | "down" | "new">("all");
  const shown = feedback.filter((f) =>
    filter === "all"
      ? true
      : filter === "new"
      ? f.status === "new"
      : f.rating === filter
  );

  const ratio = stats?.ratio_up;
  const barWidth = ratio == null ? 0 : Math.round(ratio * 100);

  return (
    <div className="space-y-4">
      <Card
        title="Statistik feedback"
        subtitle="Angka ini yang dibaca admin untuk menilai kualitas jawaban sebelum publish."
      >
        <div className="flex flex-wrap items-center gap-4">
          <div className="min-w-[220px] flex-1">
            <div className="flex h-3 w-full overflow-hidden rounded-full bg-zinc-100">
              <div
                className="h-full bg-emerald-400"
                style={{ width: `${barWidth}%` }}
              />
              <div
                className="h-full bg-amber-400"
                style={{ width: `${100 - barWidth}%` }}
              />
            </div>
            <p className="mt-1 text-[11.5px] text-zinc-500">
              {ratio == null
                ? "Belum ada feedback"
                : `${Math.round(ratio * 100)}% positif`}
            </p>
          </div>
          <span className="rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
            👍 {stats?.up ?? 0}
          </span>
          <span className="rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
            👎 {stats?.down ?? 0}
          </span>
          <span className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1 text-xs text-zinc-500">
            total {stats?.total ?? 0}
          </span>
        </div>
      </Card>

      <Card
        title={`Daftar feedback (${shown.length})`}
        subtitle="Komentar 👎 bisa dijadikan pedoman permanen → masuk system prompt (badge feedback di tab Memori)."
        right={
          <div className="flex gap-1">
            {(["all", "new", "up", "down"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`rounded-lg border px-2 py-1 text-[11.5px] font-medium transition ${
                  filter === f
                    ? "border-accent bg-accent-soft text-accent"
                    : "border-zinc-200 bg-white text-zinc-500 hover:bg-zinc-50"
                }`}
              >
                {f === "all" ? "Semua" : f === "new" ? "Baru" : f === "up" ? "👍" : "👎"}
              </button>
            ))}
          </div>
        }
      >
        {shown.length === 0 ? (
          <p className="rounded-xl border border-dashed border-zinc-200 px-3 py-8 text-center text-[13px] text-zinc-400">
            Belum ada feedback dengan filter ini.
          </p>
        ) : (
          <ul className="space-y-2" data-testid="feedback-list">
            {shown.map((f) => {
              const st = STATUS_META[f.status] || STATUS_META.new;
              return (
                <li
                  key={f.id}
                  className="rounded-xl border border-zinc-200 bg-white px-3 py-2.5"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${
                        f.rating === "up"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-amber-100 text-amber-700"
                      }`}
                    >
                      {f.rating === "up" ? "👍 suka" : "👎 kurang"}
                    </span>
                    <span className={`rounded px-1.5 py-0.5 text-[10.5px] font-medium ${st.tone}`}>
                      {st.label}
                    </span>
                    {f.context?.mode && (
                      <span className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[10.5px] text-zinc-500">
                        mode: {f.context.mode}
                      </span>
                    )}
                    {f.context?.tools_used?.length ? (
                      <span className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[10.5px] text-zinc-500">
                        tools: {f.context.tools_used.join(", ")}
                      </span>
                    ) : null}
                    <span className="ml-auto text-[10.5px] text-zinc-400">
                      {fmtTime(f.created_at)}
                    </span>
                  </div>
                  {f.comment && (
                    <p className="mt-1.5 text-[13px] leading-5 text-zinc-700">
                      “{f.comment}”
                    </p>
                  )}
                  {f.context?.answer_snippet && (
                    <p className="mt-1 truncate rounded bg-zinc-50 px-2 py-1 text-[11.5px] text-zinc-400">
                      jawaban: {f.context.answer_snippet.slice(0, 140)}…
                    </p>
                  )}
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {f.status !== "applied" && (
                      <button
                        onClick={async () => {
                          await adminApplyFeedback("", f.id);
                          onChanged();
                        }}
                        title="Ubah feedback ini menjadi memori pedoman (source=feedback) yang di-inject ke system prompt"
                        className="rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 hover:bg-emerald-100"
                      >
                        ✓ Jadikan pedoman
                      </button>
                    )}
                    <button
                      onClick={async () => {
                        await adminSetFeedbackStatus("", f.id, "reviewed");
                        onChanged();
                      }}
                      className="rounded border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-[11px] text-zinc-600 hover:bg-zinc-100"
                    >
                      Tandai direview
                    </button>
                    <button
                      onClick={async () => {
                        await adminSetFeedbackStatus("", f.id, "dismissed");
                        onChanged();
                      }}
                      className="rounded border border-zinc-200 bg-white px-2 py-0.5 text-[11px] text-zinc-400 hover:bg-zinc-50"
                    >
                      Abaikan
                    </button>
                    <button
                      onClick={async () => {
                        await adminDeleteFeedback("", f.id);
                        onChanged();
                      }}
                      className="rounded border border-zinc-200 bg-white px-2 py-0.5 text-[11px] text-zinc-400 hover:border-red-200 hover:text-red-600"
                    >
                      Hapus
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}
