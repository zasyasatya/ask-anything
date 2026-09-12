"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { HFModel, HFModelsResponse, SettingsInfo } from "@/lib/types";
import {
  deleteHFModel,
  downloadHFModel,
  listHFModels,
  stopHFRuntime,
  useHFModel,
} from "@/lib/api";

function fmtBytes(n: number): string {
  if (!n) return "—";
  const gib = n / 1024 ** 3;
  return gib >= 1 ? `${gib.toFixed(2)} GiB` : `${(n / 1024 ** 2).toFixed(0)} MiB`;
}

function fmtSpeed(bps: number): string {
  if (!bps) return "—";
  return `${(bps / 1024 ** 2).toFixed(1)} MB/s`;
}

export default function HFModelManager({
  settings,
  onSaved,
}: {
  settings: SettingsInfo | null;
  onSaved: (s: SettingsInfo) => void;
}) {
  const [data, setData] = useState<HFModelsResponse | null>(null);
  const [thinking, setThinking] = useState<boolean>(settings?.thinking ?? true);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await listHFModels());
    } catch {
      /* backend belum siap */
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll only while something is downloading or the server is booting.
  useEffect(() => {
    const downloading = data?.models.some(
      (m) => m.download?.status === "downloading"
    );
    if (!downloading) {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
      return;
    }
    if (!pollRef.current) {
      pollRef.current = window.setInterval(() => refresh(), 1200);
    }
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [data, refresh]);

  async function act(id: string, fn: () => Promise<Record<string, unknown>>) {
    setBusy(id);
    setMessage(null);
    try {
      const r = await fn();
      if (r.error) setMessage(String(r.error));
      if (r.settings) onSaved(r.settings as unknown as SettingsInfo);
      await refresh();
    } catch (e) {
      setMessage(String(e));
    } finally {
      setBusy(null);
    }
  }

  const rt = data?.runtime;

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-[11px] text-zinc-600">
        Model GGUF diunduh ke folder project{" "}
        <code className="rounded bg-white px-1 text-zinc-800">
          {data?.models_dir || settings?.models_dir || "models/"}
        </code>{" "}
        dari {data?.endpoint || "huggingface.co"}. Pilih model → otomatis
        terunduh → <b>Pakai</b> (opsional <b>Jalankan</b> llama-server) →
        thinking bisa dinyalakan.
      </div>

      {message && (
        <div className="whitespace-pre-line rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
          {message}
        </div>
      )}

      <label className="flex items-center justify-between gap-3 rounded-lg border border-zinc-200 px-3 py-2">
        <span>
          <span className="block text-xs font-medium text-zinc-700">
            Thinking (reasoning) untuk model lokal
          </span>
          <span className="block text-[11px] text-zinc-500">
            Dikirim sebagai <code>chat_template_kwargs.enable_thinking</code> —
            tampil di panel Mechanistic Interpreter.
          </span>
        </span>
        <input
          type="checkbox"
          checked={thinking}
          onChange={(e) => setThinking(e.target.checked)}
          className="h-4 w-4 accent-[var(--accent)]"
        />
      </label>

      <div className="max-h-[46vh] space-y-2 overflow-auto pr-1">
        {(data?.models || []).map((m) => (
          <ModelRow
            key={m.id}
            m={m}
            active={data?.active?.hf_model === m.filename}
            runningHere={Boolean(rt?.running && rt.model_path?.endsWith(m.filename))}
            canRun={Boolean(rt?.available)}
            busy={busy === m.id}
            onDownload={() => act(m.id, () => downloadHFModel(m.id))}
            onDelete={() => act(m.id, () => deleteHFModel(m.id))}
            onUse={() => act(m.id, () => useHFModel(m.id, { thinking }))}
            onRun={() => act(m.id, () => useHFModel(m.id, { thinking, run: true }))}
          />
        ))}
      </div>

      <div className="rounded-lg border border-zinc-200 px-3 py-2 text-[11px] text-zinc-600">
        <p className="mb-1 font-medium text-zinc-700">llama.cpp runtime</p>
        {rt?.running ? (
          <div className="flex items-center justify-between gap-2">
            <span>
              berjalan · pid {rt.pid} · port {rt.port} ·{" "}
              <code>{rt.base_url}</code>
            </span>
            <button
              onClick={() => act("__runtime", () => stopHFRuntime())}
              disabled={busy === "__runtime"}
              className="rounded-md border border-zinc-300 px-2 py-0.5 text-[11px] hover:bg-zinc-50"
            >
              Stop
            </button>
          </div>
        ) : (
          <span>
            {rt?.available
              ? `llama-server: ${rt.binary} — pakai tombol “Jalankan” pada model yang sudah terunduh.`
              : "llama-server belum ter-install; tombol “Jalankan” akan menampilkan petunjuk install. Model tetap bisa dipakai bila Anda menjalankan llama-server sendiri."}
          </span>
        )}
      </div>
    </div>
  );
}

function ModelRow({
  m,
  active,
  runningHere,
  canRun,
  busy,
  onDownload,
  onDelete,
  onUse,
  onRun,
}: {
  m: HFModel;
  active: boolean;
  runningHere: boolean;
  canRun: boolean;
  busy: boolean;
  onDownload: () => void;
  onDelete: () => void;
  onUse: () => void;
  onRun: () => void;
}) {
  const dl = m.download;
  const downloading = dl?.status === "downloading";
  const ready = m.local.exists;
  const btn =
    "rounded-md border px-2 py-1 text-[11px] font-medium transition disabled:opacity-50";

  return (
    <div
      className={`rounded-lg border p-2.5 ${
        active ? "border-accent bg-accent-soft/40" : "border-zinc-200"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-zinc-800">
            {m.name}
            {m.recommended && (
              <span className="ml-1.5 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                rekomendasi 8 GB
              </span>
            )}
            {active && (
              <span className="ml-1.5 rounded bg-accent px-1.5 py-0.5 text-[10px] font-medium text-white">
                aktif
              </span>
            )}
            {runningHere && (
              <span className="ml-1.5 rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-medium text-sky-700">
                server jalan
              </span>
            )}
          </p>
          <p className="mt-0.5 font-mono text-[10.5px] text-zinc-500">
            {m.repo_id ? `${m.repo_id} · ` : ""}
            {m.quant || m.filename} · {m.params || "—"} · {fmtBytes(m.size_bytes)}{" "}
            · RAM {m.ram}
          </p>
          <p className="mt-0.5 text-[11px] text-zinc-500">{m.note}</p>
          <p className="mt-0.5 flex flex-wrap gap-1 text-[10px] text-zinc-500">
            <span className="rounded bg-zinc-100 px-1.5 py-0.5">
              thinking: {m.thinking ? "ya" : "tidak"}
            </span>
            <span className="rounded bg-zinc-100 px-1.5 py-0.5">
              tool call: {m.tools ? "ya" : "terbatas"}
            </span>
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          {!ready && !downloading && (
            <button
              onClick={onDownload}
              disabled={busy}
              className={`${btn} border-zinc-900 bg-zinc-900 text-white hover:bg-zinc-800`}
            >
              {busy ? "…" : "Download"}
            </button>
          )}
          {downloading && (
            <span className="text-[11px] text-zinc-500">
              {dl?.percent ?? 0}% · {fmtBytes(dl?.downloaded || 0)} /{" "}
              {fmtBytes(dl?.total || 0)} · {fmtSpeed(dl?.speed_bps || 0)}
            </span>
          )}
          {ready && (
            <>
              <button
                onClick={onUse}
                disabled={busy}
                className={`${btn} border-accent bg-accent text-white hover:opacity-90`}
              >
                {busy ? "…" : "Pakai"}
              </button>
              <button
                onClick={onRun}
                disabled={busy || !canRun}
                title={
                  canRun
                    ? "Jalankan llama-server dengan model ini"
                    : "llama-server belum ter-install"
                }
                className={`${btn} border-zinc-300 text-zinc-700 hover:bg-zinc-50`}
              >
                Jalankan
              </button>
              <button
                onClick={onDelete}
                disabled={busy}
                className={`${btn} border-zinc-200 text-zinc-500 hover:bg-zinc-50`}
              >
                Hapus
              </button>
            </>
          )}
        </div>
      </div>

      {(downloading || dl?.status === "error") && (
        <div className="mt-2">
          <div className="h-1.5 w-full overflow-hidden rounded bg-zinc-200">
            <div
              className={`h-full ${
                dl?.status === "error" ? "bg-red-500" : "bg-accent"
              }`}
              style={{ width: `${dl?.percent ?? 0}%` }}
            />
          </div>
          {dl?.status === "error" && (
            <p className="mt-1 text-[11px] text-red-600">{dl.error}</p>
          )}
        </div>
      )}

      {ready && (
        <p className="mt-1 font-mono text-[10px] text-zinc-400">{m.local.path}</p>
      )}
    </div>
  );
}
