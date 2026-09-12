"use client";
import { useState } from "react";
import type { SettingsInfo } from "@/lib/types";
import { updateSettings } from "@/lib/api";
import HFModelManager from "./HFModelManager";

const TABS = ["provider", "offline"] as const;

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
    hf_api_key: "",
    thinking: settings?.thinking ?? true,
    openai_base_url: settings?.openai_base_url || "",
    openai_model: settings?.openai_model || "",
    openai_api_key: "",
    temperature: settings?.temperature ?? 0.7,
  });
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<(typeof TABS)[number]>("provider");

  const set = (k: string, v: string | number | boolean) =>
    setForm((f) => ({ ...f, [k]: v }));

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
  const label = "mb-1 block text-xs font-medium text-zinc-500";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/30 backdrop-blur-sm" onClick={onClose}>
      <div className="max-h-[88vh] w-[560px] overflow-auto rounded-2xl border border-zinc-200 bg-white p-5 shadow-card" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-1 text-base font-semibold text-zinc-900">Provider settings</h2>
        <p className="mb-3 text-xs text-zinc-500">
          Default: HuggingFace lokal (llama.cpp). OpenAI API, gateway
          OpenAI-compatible apa pun, dan mode mock juga didukung.
        </p>

        <div className="mb-4 grid grid-cols-2 gap-2 rounded-lg bg-zinc-100 p-1">
          {([
            ["provider", "Provider & endpoint"],
            ["offline", "Model offline (HuggingFace)"],
          ] as const).map(([id, name]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`rounded-md px-2 py-1.5 text-xs font-medium transition ${
                tab === id ? "bg-white text-zinc-900 shadow-sm" : "text-zinc-500"
              }`}
            >
              {name}
            </button>
          ))}
        </div>

        {tab === "provider" && (
          <>
            <label className={label}>Provider</label>
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
                <label className={label}>
                  {form.provider === "huggingface"
                    ? "Base URL (llama-server / gateway OpenAI-compatible)"
                    : "Base URL (OpenAI / gateway)"}
                </label>
                <input
                  className={input}
                  value={form.provider === "huggingface" ? form.hf_base_url : form.openai_base_url}
                  onChange={(e) => set(form.provider === "huggingface" ? "hf_base_url" : "openai_base_url", e.target.value)}
                  placeholder="https://ai.sumopod.com/v1/chat/completions"
                />
                <p className="mt-1 text-[11px] text-zinc-400">
                  Boleh base (<code>https://host/v1</code>), host saja, atau URL
                  endpoint lengkap dari contoh curl — otomatis dinormalkan ke
                  base + <code>/chat/completions</code>.
                </p>

                <label className={`${label} mt-3`}>Model</label>
                <input
                  className={input}
                  value={form.provider === "huggingface" ? form.hf_model : form.openai_model}
                  onChange={(e) => set(form.provider === "huggingface" ? "hf_model" : "openai_model", e.target.value)}
                  placeholder="qwen3.7-flash-2026-07-15"
                />

                <label className={`${label} mt-3`}>API key (Bearer token)</label>
                <input
                  className={input}
                  type="password"
                  value={form.provider === "huggingface" ? form.hf_api_key : form.openai_api_key}
                  onChange={(e) => set(form.provider === "huggingface" ? "hf_api_key" : "openai_api_key", e.target.value)}
                  placeholder={
                    form.provider === "huggingface"
                      ? settings?.hf_api_key_masked
                        ? `tersimpan (${settings.hf_api_key_masked})`
                        : "kosong = tanpa auth"
                      : settings?.openai_api_key_masked
                        ? `tersimpan (${settings.openai_api_key_masked})`
                        : "kosong = tanpa auth"
                  }
                />
              </>
            )}

            {form.provider === "huggingface" && (
              <label className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-zinc-200 px-3 py-2">
                <span>
                  <span className="block text-xs font-medium text-zinc-700">
                    Thinking (reasoning)
                  </span>
                  <span className="block text-[11px] text-zinc-500">
                    <code>chat_template_kwargs.enable_thinking</code>
                  </span>
                </span>
                <input
                  type="checkbox"
                  checked={form.thinking}
                  onChange={(e) => set("thinking", e.target.checked)}
                  className="h-4 w-4 accent-[var(--accent)]"
                />
              </label>
            )}

            <label className={`${label} mt-3`}>
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
          </>
        )}

        {tab === "offline" && (
          <HFModelManager
            settings={{ ...settings, thinking: form.thinking } as SettingsInfo}
            onSaved={(s) => {
              onSaved(s);
              setForm((f) => ({
                ...f,
                provider: s.provider,
                hf_model: s.hf_model,
                hf_base_url: s.hf_base_url,
                thinking: s.thinking ?? f.thinking,
              }));
            }}
          />
        )}

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50">
            {tab === "offline" ? "Tutup" : "Cancel"}
          </button>
          <button onClick={save} disabled={busy} className="rounded-lg bg-zinc-900 px-4 py-1.5 text-sm text-white hover:bg-zinc-800 disabled:opacity-50">
            {busy ? "Menyimpan…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
