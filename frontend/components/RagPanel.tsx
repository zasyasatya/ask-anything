"use client";
/* Panel RAG: upload PDF → pipeline parsing → chunking → embedding → siap.
   Dokumen ready bisa ditanya lewat mode RAG di composer; seluruh tahap
   (embed query → retrieval + skor → generate + sitasi) terekord di
   Mechanistic Interpreter seperti jalur chat biasa. */
import { useCallback, useEffect, useRef, useState } from "react";
import { ragDeleteDocument, ragDocuments, ragUploadPdf } from "@/lib/api";
import type { RagDocument } from "@/lib/types";

const STAGES = ["uploaded", "parsing", "chunking", "embedding", "ready"] as const;
const STAGE_LABEL: Record<string, string> = {
  uploaded: "Terunggah",
  parsing: "Parsing PDF",
  chunking: "Chunking",
  embedding: "Embedding",
  ready: "Siap ditanya",
  error: "Gagal",
};

function fmtBytes(n: number): string {
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(n / 1024))} KB`;
}

export default function RagPanel({
  maxUploadMb,
  onDocsChange,
}: {
  maxUploadMb?: number;
  onDocsChange?: (docs: RagDocument[]) => void;
}) {
  const [docs, setDocs] = useState<RagDocument[]>([]);
  const [busy, setBusy] = useState(false);
  const [uploadStage, setUploadStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const d = await ragDocuments();
      setDocs(d.documents);
      onDocsChange?.(d.documents);
    } catch {
      /* panel bisa dipakai offline; daftar tetap yang terakhir */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleUpload(file: File) {
    setError(null);
    setBusy(true);
    // Visual progres per tahap sementara upload berjalan (backend memproses
    // seluruh pipeline sekali jalan; status final diambil dari server).
    setUploadStage("parsing");
    const ticker = window.setInterval(() => {
      setUploadStage((s) =>
        s === "parsing"
          ? "chunking"
          : s === "chunking"
          ? "embedding"
          : s
      );
    }, 700);
    try {
      await ragUploadPdf(file);
      await refresh();
      setUploadStage("ready");
    } catch (e) {
      setError(String(e));
      setUploadStage(null);
    } finally {
      window.clearInterval(ticker);
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const readyCount = docs.filter((d) => d.status === "ready").length;

  return (
    <div
      data-testid="rag-panel"
      className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-card"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-zinc-800">
            📚 Pipeline RAG — tanya dokumen
          </h3>
          <p className="text-[12px] text-zinc-500">
            Upload PDF → parsing → chunking → embedding → retrieval → generate.
            Semua tahap terekord di Mechanistic Interpreter.
          </p>
        </div>
        <span className="rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
          {readyCount}/{docs.length} dokumen siap
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleUpload(f);
          }}
        />
        <button
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          className="rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50"
        >
          {busy ? "Memproses…" : "⬆️ Upload PDF"}
          {maxUploadMb ? ` (maks ${maxUploadMb} MB)` : ""}
        </button>
        {uploadStage && !error && (
          <span className="flex items-center gap-1 text-[12px] text-zinc-500">
            {STAGES.slice(0, 5).map((st, i) => {
              const idxCurrent = STAGES.indexOf(
                (uploadStage as (typeof STAGES)[number]) || "parsing"
              );
              const done = uploadStage === "ready" || i < idxCurrent;
              const active = !done && i === idxCurrent;
              return (
                <span
                  key={st}
                  className={`rounded px-1.5 py-0.5 ${
                    done
                      ? "bg-emerald-100 text-emerald-700"
                      : active
                      ? "bg-accent-soft text-accent animate-pulse"
                      : "bg-zinc-100 text-zinc-400"
                  }`}
                >
                  {done ? "✓" : active ? "●" : "○"} {STAGE_LABEL[st]}
                </span>
              );
            })}
          </span>
        )}
        {error && (
          <span className="text-[12px] text-red-600">
            {error.replace(/^Error: /, "")}
          </span>
        )}
      </div>

      {docs.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {docs.map((d) => (
            <li
              key={d.id}
              className="flex flex-wrap items-center gap-2 rounded-xl border border-zinc-100 bg-zinc-50/60 px-3 py-2"
            >
              <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-zinc-700">
                📄 {d.filename}
              </span>
              {d.status === "error" ? (
                <span
                  title={d.error}
                  className="rounded bg-red-100 px-1.5 py-0.5 text-[10.5px] text-red-700"
                >
                  ✗ Gagal: {d.error.slice(0, 60)}
                </span>
              ) : d.status === "ready" ? (
                <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10.5px] text-emerald-700">
                  ✓ {d.chunks} chunk · {d.pages} hal · {fmtBytes(d.size_bytes)}
                </span>
              ) : (
                <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10.5px] text-amber-700">
                  ● {STAGE_LABEL[d.status] || d.status}
                </span>
              )}
              <button
                onClick={async () => {
                  await ragDeleteDocument(d.id).catch(() => undefined);
                  refresh();
                }}
                className="rounded border border-zinc-200 bg-white px-1.5 py-0.5 text-[11px] text-zinc-400 hover:text-red-600"
                title="Hapus dokumen + index-nya"
              >
                Hapus
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
