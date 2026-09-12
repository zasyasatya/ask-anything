"use client";
import { useState } from "react";
import type { SettingsInfo } from "@/lib/types";
import { updateSettings } from "@/lib/api";

export default function SettingsModal({
  settings,
  onSaved,
  onClose,
}: {
  settings: SettingsInfo | null;
  onSaved: (s: SettingsInfo) => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState({
    provider: settings?.provider || "huggingface",
    hf_base_url: settings?.hf_base_url || "",
    hf_model: settings?.hf_model || "",
    openai_base_url: settings?.openai_base_url || "",
    openai_model: settings?.openai_model || "",
    temperature: settings?.temperature ?? 0.7,
  });
  const [busy, setBusy] = useState(false);

  const set = (k: string, v: string | number) => setForm((f) => ({ ...f, [k]: v }));

  async function save() {
    setBusy(true);
    try {
      const s = await updateSettings(form);
      onSaved(s);
      onClose();
    } finally {
      setBusy(false);
    }
  }

  const input =
    "w-full rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm text-zinc-700 outline-none focus:border-accent focus:ring-2 focus:ring-accent-ring";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/30 backdrop-blur-sm" onClick={onClose}>
      <div className="w-[440px] rounded-2xl border border-zinc-200 bg-white p-5 shadow-card" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-1 text-base font-semibold text-zinc-900">Provider settings</h2>
        <p className="mb-4 text-xs text-zinc-500">
          Default: HuggingFace lokal (llama.cpp). OpenAI API & mode mock juga didukung.
        </p>

        <label className="mb-1 block text-xs font-medium text-zinc-500">Provider</label>
        <div className="mb-3 grid grid-cols-3 gap-2">
          {["huggingface", "openai", "mock"].map((p) => (
            <button
              key={p}
              onClick={() => set("provider", p)}
              className={`rounded-lg border px-2 py-1.5 text-sm capitalize transition ${
                form.provider === p
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-zinc-200 text-zinc-600 hover:bg-zinc-50"
              }`}
            >
              {p}
            </button>
          ))}
        </div>

        {form.provider !== "mock" && (
          <>
            <label className="mb-1 block text-xs font-medium text-zinc-500">
              {form.provider === "huggingface" ? "Base URL (llama-server)" : "OpenAI base URL"}
            </label>
            <input
              className={input}
              value={form.provider === "huggingface" ? form.hf_base_url : form.openai_base_url}
              onChange={(e) => set(form.provider === "huggingface" ? "hf_base_url" : "openai_base_url", e.target.value)}
            />
            <label className="mb-1 mt-3 block text-xs font-medium text-zinc-500">Model</label>
            <input
              className={input}
              value={form.provider === "huggingface" ? form.hf_model : form.openai_model}
              onChange={(e) => set(form.provider === "huggingface" ? "hf_model" : "openai_model", e.target.value)}
            />
          </>
        )}

        <label className="mb-1 mt-3 block text-xs font-medium text-zinc-500">
          Temperature: {form.temperature}
        </label>
        <input
          type="range"
          min={0}
          max={1.5}
          step={0.1}
          value={form.temperature}
          onChange={(e) => set("temperature", Number(e.target.value))}
          className="w-full accent-[var(--accent)]"
        />

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50">
            Cancel
          </button>
          <button onClick={save} disabled={busy} className="rounded-lg bg-zinc-900 px-4 py-1.5 text-sm text-white hover:bg-zinc-800 disabled:opacity-50">
            {busy ? "Menyimpan…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
