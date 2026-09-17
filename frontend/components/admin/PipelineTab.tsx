"use client";
/* Tab Pipeline: atur mode & tool yang boleh dipakai user, parameter RAG,
   memori, dan feedback — satu layar governance seperti console admin Claude. */
import { useState } from "react";
import { adminUpdatePolicy } from "@/lib/api";
import type { FullPolicy } from "@/lib/types";
import { Card, Toggle } from "./ui";

const MODE_META: Record<string, { label: string; hint: string }> = {
  text: { label: "Teks", hint: "Chat + agent browsing (mode inti)." },
  image: { label: "Gambar", hint: "Tool generate_image — poster generatif / gateway gambar." },
  diagram: { label: "Diagram", hint: "Flowchart & graph interaktif via create_diagram." },
  ppt: { label: "PPT", hint: "Deck .pptx dari outline via generate_ppt." },
  rag: { label: "RAG", hint: "Upload PDF → parse → chunk → embed → retrieve → generate." },
  research: { label: "Deep Research", hint: "Riset multi-query dengan canvas." },
};

const TOOL_META: Record<string, { label: string; hint: string }> = {
  web_search: { label: "web_search", hint: "Pencarian web (bukti eksternal, wajib sitasi)." },
  fetch_url: { label: "fetch_url", hint: "Baca halaman URL penuh." },
  create_diagram: { label: "create_diagram", hint: "Diagram Mermaid/terstruktur (konten generatif)." },
  calculator: { label: "calculator", hint: "Aritmetika deterministik." },
  generate_image: { label: "generate_image", hint: "Gambar dari prompt (artifact)." },
  generate_ppt: { label: "generate_ppt", hint: "Deck PPTX dari outline (artifact)." },
  save_memory: { label: "save_memory", hint: "Agent menyimpan memori jangka panjang." },
};

function NumberField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
}) {
  return (
    <label className="flex items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white px-3 py-2.5">
      <span className="text-[13px] font-medium text-zinc-700">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) =>
          onChange(
            Math.max(min, Math.min(max, Number(e.target.value) || min))
          )
        }
        className="w-24 rounded-lg border border-zinc-200 px-2 py-1 text-right text-[13px] outline-none focus:border-indigo-300"
      />
    </label>
  );
}

export default function PipelineTab({
  policy,
  onPolicyChange,
}: {
  policy: FullPolicy;
  onPolicyChange: (p: FullPolicy) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function patch(section: string, values: Record<string, unknown>) {
    setSaving(true);
    setSaved(false);
    try {
      const next = await adminUpdatePolicy("", { [section]: values });
      onPolicyChange(next);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 1600);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card
        title="Mode pipeline"
        subtitle="Mode yang tidak dicentang disembunyikan dari user DAN ditolak server-side."
      >
        <div className="space-y-2">
          {Object.keys(MODE_META).map((m) => (
            <Toggle
              key={m}
              label={`${MODE_META[m].label} (${m})`}
              hint={MODE_META[m].hint}
              checked={policy.modes?.[m] !== false}
              onChange={(v) => patch("modes", { [m]: v })}
            />
          ))}
        </div>
      </Card>

      <Card
        title="Tool yang boleh dijalankan"
        subtitle="Tool nonaktif tidak diiklankan ke model; bila model memaksanya, eksekusi ditolak & terecord di interpreter."
      >
        <div className="space-y-2">
          {Object.keys(TOOL_META).map((t) => (
            <Toggle
              key={t}
              label={TOOL_META[t].label}
              hint={TOOL_META[t].hint}
              checked={policy.tools?.[t] !== false}
              onChange={(v) => patch("tools", { [t]: v })}
            />
          ))}
        </div>
      </Card>

      <Card
        title="Pipeline RAG"
        subtitle="Upload PDF otomatis melewati parsing → chunking → embedding → index."
      >
        <div className="space-y-2">
          <NumberField
            label="Ukuran chunk (karakter)"
            value={policy.rag?.chunk_size ?? 1200}
            min={200}
            max={8000}
            onChange={(v) => patch("rag", { chunk_size: v })}
          />
          <NumberField
            label="Overlap antar chunk"
            value={policy.rag?.chunk_overlap ?? 150}
            min={0}
            max={1000}
            onChange={(v) => patch("rag", { chunk_overlap: v })}
          />
          <NumberField
            label="Top-K potongan per pertanyaan"
            value={policy.rag?.top_k ?? 4}
            min={1}
            max={20}
            onChange={(v) => patch("rag", { top_k: v })}
          />
          <NumberField
            label="Batas upload (MB)"
            value={policy.rag?.max_upload_mb ?? 25}
            min={1}
            max={200}
            onChange={(v) => patch("rag", { max_upload_mb: v })}
          />
        </div>
      </Card>

      <div className="space-y-4">
        <Card
          title="Memori"
          subtitle="Memori aktif di-inject ke system prompt setiap run — perubahan langsung mengubah perilaku."
        >
          <div className="space-y-2">
            <Toggle
              label="Injeksi memori aktif"
              hint="Blok MEMORI dikirim ke model setiap run."
              checked={policy.memory?.enabled !== false}
              onChange={(v) => patch("memory", { enabled: v })}
            />
            <Toggle
              label="AI boleh menulis memori (save_memory)"
              hint="Bila mati, panggilan tool save_memory ditolak policy & terecord."
              checked={policy.memory?.allow_ai_write !== false}
              onChange={(v) => patch("memory", { allow_ai_write: v })}
            />
          </div>
        </Card>

        <Card
          title="Feedback & auto-guidance"
          subtitle="👎 + komentar bisa otomatis menjadi pedoman perilaku (memory source=feedback)."
        >
          <div className="space-y-2">
            <Toggle
              label="Tombol 👍/👎 aktif"
              hint="Feedback terecord lengkap dengan konteks run."
              checked={policy.feedback?.enabled !== false}
              onChange={(v) => patch("feedback", { enabled: v })}
            />
            <Toggle
              label="Auto-guidance dari 👎 berkomentar"
              hint="Langsung jadi pedoman tanpa menunggu review admin."
              checked={policy.feedback?.auto_guidance !== false}
              onChange={(v) => patch("feedback", { auto_guidance: v })}
            />
            <NumberField
              label="Maks pedoman feedback di prompt"
              value={policy.feedback?.max_guidance ?? 8}
              min={0}
              max={32}
              onChange={(v) => patch("feedback", { max_guidance: v })}
            />
          </div>
        </Card>

        <Card
          title="Mechanistic Interpreter"
          subtitle="Audit selalu aktif — ini kontrak produk, bukan preferensi."
        >
          <div className="space-y-2">
            <Toggle
              label="Selalu merecord semua langkah"
              hint="Setiap request/response LLM, tool, RAG, artifact, policy — masuk SQLite & bisa di-replay."
              checked={true}
              locked
              onChange={() => undefined}
            />
            <Toggle
              label="Record logprobs per token"
              checked={policy.interpreter?.record_logprobs !== false}
              onChange={(v) => patch("interpreter", { record_logprobs: v })}
            />
            <Toggle
              label="Record payload tool mentah"
              checked={policy.interpreter?.record_tool_payloads !== false}
              onChange={(v) =>
                patch("interpreter", { record_tool_payloads: v })
              }
            />
          </div>
        </Card>
      </div>

      <p className="lg:col-span-2 text-[12px] text-zinc-400" aria-live="polite">
        {saving
          ? "Menyimpan policy…"
          : saved
          ? "✓ Policy tersimpan — berlaku untuk run berikutnya tanpa restart."
          : "Perubahan langsung tersimpan (PUT /api/admin/policy)."}
      </p>
    </div>
  );
}
