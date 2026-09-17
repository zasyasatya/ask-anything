"use client";
/* Tab Memori: CRUD memori jangka panjang (admin / AI / feedback) — semua
   entri aktif otomatis masuk system prompt run berikutnya. */
import { useState } from "react";
import {
  adminCreateMemory,
  adminDeleteMemory,
  adminUpdateMemory,
} from "@/lib/api";
import type { MemoryItem } from "@/lib/types";
import { Card, fmtTime } from "./ui";

const SOURCE_META: Record<string, { label: string; tone: string }> = {
  admin: { label: "admin", tone: "bg-indigo-100 text-indigo-700" },
  ai: { label: "AI", tone: "bg-sky-100 text-sky-700" },
  feedback: { label: "feedback", tone: "bg-amber-100 text-amber-700" },
  user: { label: "user", tone: "bg-zinc-200 text-zinc-600" },
};

export default function MemoryTab({
  memories,
  onChanged,
}: {
  memories: MemoryItem[];
  onChanged: () => void;
}) {
  const [content, setContent] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);

  async function add() {
    if (!content.trim() || busy) return;
    setBusy(true);
    try {
      await adminCreateMemory("", {
        scope: "global",
        key: key.trim(),
        content: content.trim(),
        enabled: true,
      });
      setContent("");
      setKey("");
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <Card
        title={`Memori (${memories.length})`}
        subtitle="Dipakai ulang setiap run: blok MEMORI + PEDOMAN FEEDBACK di system prompt."
      >
        {memories.length === 0 ? (
          <p className="rounded-xl border border-dashed border-zinc-200 px-3 py-6 text-center text-[13px] text-zinc-400">
            Belum ada memori. Tambahkan kebijakan produk, tone, atau batasan —
            atau biarkan AI menyimpannya via tool save_memory.
          </p>
        ) : (
          <ul className="space-y-2" data-testid="memory-list">
            {memories.map((m) => {
              const src = SOURCE_META[m.source] || SOURCE_META.user;
              return (
                <li
                  key={m.id}
                  className={`rounded-xl border px-3 py-2.5 ${
                    m.enabled
                      ? "border-zinc-200 bg-white"
                      : "border-zinc-100 bg-zinc-50 opacity-60"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    {m.key && (
                      <span className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[10.5px] text-zinc-500">
                        {m.key}
                      </span>
                    )}
                    <span className={`rounded px-1.5 py-0.5 text-[10.5px] font-medium ${src.tone}`}>
                      {src.label}
                    </span>
                    <span className="ml-auto text-[10.5px] text-zinc-400">
                      {fmtTime(m.updated_at)}
                    </span>
                  </div>
                  <p className="mt-1 text-[13px] leading-5 text-zinc-700">
                    {m.content}
                  </p>
                  <div className="mt-1.5 flex gap-1.5">
                    <button
                      onClick={async () => {
                        await adminUpdateMemory("", m.id, { enabled: !m.enabled });
                        onChanged();
                      }}
                      className="rounded border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-[11px] text-zinc-600 hover:bg-zinc-100"
                    >
                      {m.enabled ? "Nonaktifkan" : "Aktifkan"}
                    </button>
                    <button
                      onClick={async () => {
                        await adminDeleteMemory("", m.id);
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

      <Card
        title="Tambah memori"
        subtitle="Contoh: “Selalu jawab dalam Bahasa Indonesia formal”, “Produk kami bernama X”."
      >
        <input
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="Label (opsional) — mis. tone"
          className="w-full rounded-lg border border-zinc-200 px-2.5 py-1.5 text-[13px] outline-none focus:border-indigo-300"
        />
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={4}
          placeholder="Isi memori…"
          className="mt-2 w-full resize-none rounded-lg border border-zinc-200 px-2.5 py-1.5 text-[13px] outline-none focus:border-indigo-300"
        />
        <button
          onClick={add}
          disabled={busy || !content.trim()}
          className="mt-2 w-full rounded-lg bg-accent px-3 py-2 text-[13px] font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          Simpan memori
        </button>
        <p className="mt-2 text-[11.5px] leading-4 text-zinc-400">
          Memori dari feedback 👎 akan muncul di sini dengan badge
          <span className="mx-1 rounded bg-amber-100 px-1 py-0.5 text-[10px] text-amber-700">
            feedback
          </span>
          sehingga asal-usulnya selalu terlacak.
        </p>
      </Card>
    </div>
  );
}
