"use client";
/* Tab Artifact: semua keluaran biner pipeline (gambar, deck PPTX, dokumen)
   dengan asal-usul run-nya — bisa dibuka, diaudit, dihapus. */
import { useMemo, useState } from "react";
import { adminDeleteArtifact } from "@/lib/api";
import type { ArtifactItem } from "@/lib/types";
import { Card, fmtBytes, fmtTime } from "./ui";

const KINDS = [
  { id: "all", label: "Semua" },
  { id: "image", label: "🖼️ Gambar" },
  { id: "pptx", label: "📊 Deck PPT" },
  { id: "diagram", label: "🔀 Diagram" },
  { id: "data", label: "📦 Lainnya" },
];

export default function ArtifactTab({
  artifacts,
  onChanged,
}: {
  artifacts: ArtifactItem[];
  onChanged: () => void;
}) {
  const [kind, setKind] = useState("all");
  const shown = useMemo(
    () => (kind === "all" ? artifacts : artifacts.filter((a) => a.kind === kind)),
    [artifacts, kind]
  );

  return (
    <Card
      title={`Penyimpanan artifact (${shown.length})`}
      subtitle="Registry FIFO dipangkas otomatis melewati batas policy artifacts.max_artifacts."
      right={
        <div className="flex flex-wrap gap-1">
          {KINDS.map((k) => (
            <button
              key={k.id}
              onClick={() => setKind(k.id)}
              className={`rounded-lg border px-2 py-1 text-[11.5px] font-medium transition ${
                kind === k.id
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-zinc-200 bg-white text-zinc-500 hover:bg-zinc-50"
              }`}
            >
              {k.label}
            </button>
          ))}
        </div>
      }
    >
      {shown.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-200 px-3 py-8 text-center text-[13px] text-zinc-400">
          Belum ada artifact. Jalankan mode Gambar atau PPT di chat — hasilnya
          otomatis masuk registry ini.
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {shown.map((a) => (
            <div
              key={a.id}
              className="flex flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white"
              data-testid="artifact-card"
            >
              {a.kind === "image" ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={a.url}
                  alt={a.title}
                  className="h-36 w-full border-b border-zinc-100 bg-zinc-50 object-cover"
                />
              ) : (
                <div className="flex h-36 items-center justify-center border-b border-zinc-100 bg-zinc-50 text-4xl">
                  {a.kind === "pptx" ? "📊" : a.kind === "diagram" ? "🔀" : "📦"}
                </div>
              )}
              <div className="flex min-h-0 flex-1 flex-col p-3">
                <p className="truncate text-[13px] font-medium text-zinc-800">
                  {a.title || a.filename}
                </p>
                <p className="mt-0.5 text-[11px] text-zinc-400">
                  {a.kind} · {fmtBytes(a.size_bytes)} · {fmtTime(a.created_at)}
                </p>
                {(a.meta as { generator?: string })?.generator && (
                  <p className="mt-0.5 truncate text-[11px] text-zinc-400">
                    generator: {(a.meta as { generator?: string }).generator}
                  </p>
                )}
                {a.conversation_id && (
                  <p className="mt-0.5 truncate font-mono text-[10.5px] text-zinc-300">
                    run {a.run_id || "—"} · conv {a.conversation_id}
                  </p>
                )}
                <div className="mt-auto flex gap-1.5 pt-2">
                  <a
                    href={a.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex-1 rounded-lg border border-zinc-200 bg-zinc-50 px-2 py-1 text-center text-[11.5px] font-medium text-zinc-700 hover:bg-zinc-100"
                  >
                    Buka ↗
                  </a>
                  <button
                    onClick={async () => {
                      await adminDeleteArtifact("", a.id);
                      onChanged();
                    }}
                    className="rounded-lg border border-zinc-200 bg-white px-2 py-1 text-[11.5px] text-zinc-400 hover:border-red-200 hover:text-red-600"
                  >
                    Hapus
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
