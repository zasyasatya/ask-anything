"use client";
import { useCallback, useEffect, useState } from "react";
import type {
  DiagnosticReport,
  ProviderModel,
  SettingsInfo,
} from "@/lib/types";
import { listProviderModels, testProvider, updateSettings } from "@/lib/api";
import HFModelManager from "./HFModelManager";

const TABS = ["provider", "offline"] as const;
const MANUAL = "__manual__";

const PROVIDERS: Array<{ id: string; name: string; desc: string }> = [
  {
    id: "huggingface",
    name: "HuggingFace",
    desc: "model offline di folder models/ (inference lokal) atau server OpenAI-compatible",
  },
  {
    id: "openai",
    name: "OpenAI API",
    desc: "OpenAI atau gateway OpenAI-compatible apa pun (LiteLLM, vLLM, OpenRouter…)",
  },
  { id: "mock", name: "Mock", desc: "demo offline tanpa jaringan" },
];

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
    hf_mode: settings?.hf_mode || "local",
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
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("provider");

  // ---- model list of the probed endpoint ----------------------------------
  const [models, setModels] = useState<ProviderModel[] | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelsNote, setModelsNote] = useState<string | null>(null);
  const [manualModel, setManualModel] = useState(false);
  // ---- diagnostik endpoint ("Test koneksi") -------------------------------
  const [testing, setTesting] = useState(false);
  const [report, setReport] = useState<DiagnosticReport | null>(null);
  // keys the user explicitly wiped, so Save really clears them on the backend
  const [cleared, setCleared] = useState<{ hf: boolean; openai: boolean }>({
    hf: false,
    openai: false,
  });

  const isOpenAI = form.provider === "openai";
  const isHF = form.provider === "huggingface";
  const isServer = isHF && form.hf_mode === "server";
  const needsEndpoint = isOpenAI || isServer;
  const modelField = isHF ? "hf_model" : "openai_model";
  const keyField = isHF ? "hf_api_key" : "openai_api_key";
  const currentModel = (form[modelField as "hf_model" | "openai_model"] || "").trim();
  const maskedKey = isHF ? settings?.hf_api_key_masked : settings?.openai_api_key_masked;

  const set = (k: string, v: string | number | boolean) =>
    setForm((f) => ({ ...f, [k]: v }));

  const probePayload = useCallback(
    () => ({
      provider: form.provider,
      base_url: isHF ? form.hf_base_url : form.openai_base_url,
      model: currentModel || undefined,
      ...((isHF ? form.hf_api_key : form.openai_api_key)
        ? { api_key: isHF ? form.hf_api_key : form.openai_api_key }
        : {}),
    }),
    [form.provider, form.hf_base_url, form.openai_base_url, form.hf_api_key,
     form.openai_api_key, isHF, currentModel]
  );

  const loadModels = useCallback(async () => {
    if (form.provider === "mock") {
      setModels([{ id: "mock-agent", label: "mock-agent (offline demo)" }]);
      setModelsNote("Mode mock memakai model agent offline (tanpa endpoint).");
      return;
    }
    if (isHF && form.hf_mode === "local") {
      setModels(
        form.hf_model ? [{ id: form.hf_model, label: form.hf_model }] : []
      );
      setModelsNote(
        "Mode lokal memakai model dari folder models/ — lihat tab “Model offline”."
      );
      return;
    }
    setLoadingModels(true);
    setModelsNote(null);
    try {
      const r = await listProviderModels(probePayload());
      if (r.ok) {
        setModels(r.models);
        setModelsNote(`${r.count} model di ${r.url}`);
        if (r.models.some((m) => m.id === currentModel)) setManualModel(false);
      } else {
        setModels([]);
        setModelsNote(`${r.error || "gagal memuat"}${r.url ? ` — ${r.url}` : ""}`);
      }
    } catch (e) {
      setModels([]);
      setModelsNote(`gagal memuat daftar model: ${String(e)}`);
    } finally {
      setLoadingModels(false);
    }
  }, [form.provider, form.hf_mode, form.hf_model, isHF, probePayload, currentModel]);

  // probe once per provider/mode switch (and when the modal opens)
  useEffect(() => {
    if (tab !== "provider") return;
    void loadModels();
    setReport(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.provider, form.hf_mode, tab]);

  async function runTest() {
    setTesting(true);
    setReport(null);
    try {
      setReport(await testProvider(probePayload()));
    } catch (e) {
      setReport({ ok: false, checks: [], hint: String(e) });
    } finally {
      setTesting(false);
    }
  }

  async function save() {
    setBusy(true);
    setError(null);
    // Untouched key fields are left out entirely; an explicitly wiped key is
    // sent as "" so the backend really clears it.
    const payload: Record<string, unknown> = { ...form };
    if (!form.hf_api_key && !cleared.hf) delete payload.hf_api_key;
    if (!form.openai_api_key && !cleared.openai) delete payload.openai_api_key;
    try {
      const s = await updateSettings(payload);
      onSaved(s);
      onClose();
    } catch (e) {
      setError(`Gagal menyimpan: ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  const input =
    "w-full rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm text-zinc-700 outline-none focus:border-accent focus:ring-2 focus:ring-accent-ring";
  const label = "mb-1 block text-xs font-medium text-zinc-500";

  const known = models ?? [];
  const activeIsKnown = known.some((m) => m.id === currentModel);
  const showManual = manualModel || (!activeIsKnown && Boolean(currentModel));
  const selectValue = showManual ? MANUAL : currentModel;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/30 backdrop-blur-sm" onClick={onClose}>
      <div className="max-h-[88vh] w-[600px] overflow-auto rounded-2xl border border-zinc-200 bg-white p-5 shadow-card" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-1 text-base font-semibold text-zinc-900">Provider settings</h2>
        <p className="mb-3 text-xs text-zinc-500">
          Tiga mode: <b>HuggingFace</b> (model offline, inference lokal),{" "}
          <b>OpenAI API</b> (OpenAI/gateway OpenAI-compatible), dan{" "}
          <b>Mock</b> (demo tanpa jaringan).
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
              {PROVIDERS.map((p) => (
                <button
                  key={p.id}
                  title={p.desc}
                  onClick={() => {
                    set("provider", p.id);
                    setManualModel(false);
                  }}
                  className={`rounded-lg border px-2 py-1.5 text-sm transition ${
                    form.provider === p.id
                      ? "border-accent bg-accent-soft text-accent"
                      : "border-zinc-200 text-zinc-600 hover:bg-zinc-50"
                  }`}
                >
                  {p.name}
                </button>
              ))}
            </div>

            {isHF && (
              <>
                <label className={label}>Cara menjalankan model</label>
                <div className="mb-3 grid grid-cols-2 gap-2">
                  {([
                    ["local", "Inference lokal", "transformers di proses backend, tanpa llama.cpp"],
                    ["server", "Server OpenAI-compatible", "vLLM / llama.cpp / LM Studio / gateway"],
                  ] as const).map(([id, name, desc]) => (
                    <button
                      key={id}
                      onClick={() => set("hf_mode", id)}
                      title={desc}
                      className={`rounded-lg border px-2 py-1.5 text-left text-xs transition ${
                        form.hf_mode === id
                          ? "border-accent bg-accent-soft text-accent"
                          : "border-zinc-200 text-zinc-600 hover:bg-zinc-50"
                      }`}
                    >
                      <span className="block font-medium">{name}</span>
                      <span className="block text-[10.5px] text-zinc-500">{desc}</span>
                    </button>
                  ))}
                </div>
                {form.hf_mode === "local" && (
                  <div className="mb-3 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-[11px] text-zinc-600">
                    Model aktif:{" "}
                    <code className="rounded bg-white px-1 text-zinc-800">
                      {form.hf_model || "(belum dipilih)"}
                    </code>
                    <button
                      onClick={() => setTab("offline")}
                      className="ml-2 rounded-md border border-zinc-300 bg-white px-2 py-0.5 text-[10.5px] font-medium hover:bg-zinc-50"
                    >
                      Cari / unduh model →
                    </button>
                  </div>
                )}
              </>
            )}

            {needsEndpoint && (
              <>
                <label className={label}>
                  {isHF
                    ? "Base URL (vLLM / llama-server / gateway)"
                    : "Base URL (OpenAI / gateway)"}
                </label>
                <div className="flex gap-2">
                  <input
                    className={input}
                    value={isHF ? form.hf_base_url : form.openai_base_url}
                    onChange={(e) =>
                      set(isHF ? "hf_base_url" : "openai_base_url", e.target.value)
                    }
                    placeholder="https://ai.sumopod.com/v1/chat/completions"
                  />
                  <button
                    onClick={() => void loadModels()}
                    disabled={loadingModels}
                    className="shrink-0 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 disabled:opacity-50"
                    title="GET <base>/models"
                  >
                    {loadingModels ? "…" : "Muat model"}
                  </button>
                </div>
                <p className="mt-1 text-[11px] text-zinc-400">
                  Boleh base (<code>https://host/v1</code>), host saja, atau URL
                  endpoint lengkap dari contoh curl — otomatis dinormalkan ke
                  base + <code>/chat/completions</code>.
                </p>

                <label className={`${label} mt-3`}>
                  Model
                  <span className="ml-1 font-normal text-zinc-400">
                    {models === null
                      ? "(belum dimuat)"
                      : models.length
                        ? `— ${models.length} pilihan dari endpoint`
                        : "(endpoint tidak memberi daftar)"}
                  </span>
                </label>
                {models && models.length > 0 ? (
                  <select
                    className={input}
                    value={selectValue}
                    onChange={(e) => {
                      if (e.target.value === MANUAL) {
                        setManualModel(true);
                        return;
                      }
                      setManualModel(false);
                      set(modelField, e.target.value);
                    }}
                  >
                    {!currentModel && <option value="">— pilih model —</option>}
                    {!activeIsKnown && currentModel && (
                      <option value={MANUAL}>{currentModel} (dipakai sekarang)</option>
                    )}
                    {known.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label === m.id ? m.id : `${m.label}  ·  ${m.id}`}
                      </option>
                    ))}
                    <option value={MANUAL}>✎ Ketik nama model lain…</option>
                  </select>
                ) : (
                  <input
                    className={input}
                    value={currentModel}
                    onChange={(e) => set(modelField, e.target.value)}
                    placeholder="qwen3.7-flash-2026-07-15"
                  />
                )}
                {showManual && models && models.length > 0 && (
                  <input
                    className={`${input} mt-2`}
                    value={currentModel}
                    onChange={(e) => set(modelField, e.target.value)}
                    placeholder="nama model persis seperti di dokumentasi API"
                    autoFocus={manualModel}
                  />
                )}
                {modelsNote && (
                  <p className="mt-1 break-all text-[11px] text-zinc-400">{modelsNote}</p>
                )}

                <label className={`${label} mt-3`}>API key (Bearer token)</label>
                <div className="flex gap-2">
                  <input
                    className={input}
                    type="password"
                    value={isHF ? form.hf_api_key : form.openai_api_key}
                    onChange={(e) => set(keyField, e.target.value)}
                    placeholder={
                      maskedKey ? `tersimpan (${maskedKey})` : "kosong = tanpa auth"
                    }
                  />
                  {maskedKey && (
                    <button
                      onClick={() => {
                        set(keyField, "");
                        setCleared((c) => ({ ...c, [isHF ? "hf" : "openai"]: true }));
                      }}
                      className="shrink-0 rounded-lg border border-rose-200 bg-white px-3 py-1.5 text-xs font-medium text-rose-600 hover:bg-rose-50"
                      title="Hapus key yang tersimpan"
                    >
                      Hapus
                    </button>
                  )}
                </div>

                <div className="mt-3 flex items-center gap-2">
                  <button
                    onClick={() => void runTest()}
                    disabled={testing}
                    className="rounded-lg border border-zinc-900 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
                  >
                    {testing ? "Menguji…" : "Test koneksi"}
                  </button>
                  <span className="text-[11px] text-zinc-400">
                    menjalankan request sungguhan: GET /models + chat
                    non-streaming (bentuk curl) + chat streaming
                  </span>
                </div>
                {report && <DiagnosticView report={report} />}
              </>
            )}

            {isHF && (
              <label className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-zinc-200 px-3 py-2">
                <span>
                  <span className="block text-xs font-medium text-zinc-700">
                    Thinking (reasoning)
                  </span>
                  <span className="block text-[11px] text-zinc-500">
                    {form.hf_mode === "local"
                      ? "Diteruskan ke chat template model sebagai enable_thinking."
                      : "Dikirim sebagai chat_template_kwargs.enable_thinking; otomatis dibuang bila template menolaknya."}
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
                hf_mode: s.hf_mode || f.hf_mode,
                hf_model: s.hf_model,
                hf_base_url: s.hf_base_url,
                thinking: s.thinking ?? f.thinking,
              }));
            }}
          />
        )}

        {error && (
          <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-700">
            {error}
          </p>
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

function DiagnosticView({ report }: { report: DiagnosticReport }) {
  return (
    <div
      className={`mt-2 rounded-lg border px-3 py-2 text-[11px] ${
        report.ok
          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
          : "border-rose-200 bg-rose-50 text-rose-800"
      }`}
    >
      <p className="mb-1 font-medium">
        {report.ok ? "Endpoint menjawab dengan baik" : "Endpoint bermasalah"}
        {report.base_url ? ` · ${report.base_url}` : ""}
      </p>
      <ul className="space-y-1">
        {report.checks.map((c, i) => (
          <li key={i} className="leading-snug">
            <span className="font-medium">
              {c.ok ? "✓" : "✗"} {c.name}
            </span>
            {typeof c.status === "number" && (
              <span className="ml-1 rounded bg-white/70 px-1 font-mono">
                HTTP {c.status}
              </span>
            )}
            {typeof c.latency_ms === "number" && (
              <span className="ml-1 text-[10px] opacity-70">{c.latency_ms} ms</span>
            )}
            {c.detail && (
              <span className="ml-1 break-all opacity-80">{c.detail}</span>
            )}
            {c.error && (
              <span className="ml-1 break-all font-mono">{c.error}</span>
            )}
            {c.hint && !c.ok && (
              <span className="mt-0.5 block break-words opacity-90">→ {c.hint}</span>
            )}
          </li>
        ))}
      </ul>
      {report.hint && !report.ok && (
        <p className="mt-1.5 border-t border-rose-200 pt-1.5 font-medium">
          {report.hint}
        </p>
      )}
    </div>
  );
}
