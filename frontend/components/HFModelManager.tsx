"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type {
  DownloadState,
  EngineStatus,
  HFModel,
  HFModelsResponse,
  HFSearchHit,
  SettingsInfo,
} from "@/lib/types";
import {
  cancelHFDownload,
  deleteHFModel,
  downloadHFModel,
  listHFModels,
  searchHFModels,
  stopHFEngine,
  updateSettings,
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

function fmtParams(n: number): string {
  if (!n) return "";
  if (n >= 1e9) return `${(n / 1e9).toFixed(n >= 1e10 ? 0 : 1)}B param`;
  return `${(n / 1e6).toFixed(0)}M param`;
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

  // ---- pencarian HuggingFace ---------------------------------------------
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [hits, setHits] = useState<HFSearchHit[] | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const pollRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await listHFModels());
    } catch {
      /* backend belum siap */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Poll selama ada unduhan berjalan atau model sedang dimuat.
  useEffect(() => {
    const active =
      data?.downloads.some((d) => d.status === "downloading") ||
      data?.engine.state === "loading";
    if (!active) {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
      return;
    }
    if (!pollRef.current) {
      pollRef.current = window.setInterval(() => void refresh(), 1200);
    }
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [data?.downloads, data?.engine.state, refresh]);

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

  async function search() {
    const q = query.trim();
    if (!q) return;
    setSearching(true);
    setSearchError(null);
    try {
      const r = await searchHFModels(q);
      if (r.ok) {
        setHits(r.models);
        if (!r.models.length) setSearchError(`Tidak ada hasil untuk “${q}”.`);
      } else {
        setHits([]);
        setSearchError(r.error || "gagal mencari di HuggingFace");
      }
    } catch (e) {
      setHits([]);
      setSearchError(String(e));
    } finally {
      setSearching(false);
    }
  }

  async function saveToken() {
    const s = await updateSettings({ hf_token: token.trim() });
    onSaved(s);
    setToken("");
    setMessage(
      token.trim()
        ? "Token HuggingFace disimpan — repo gated/privat kini bisa diunduh."
        : "Token HuggingFace dihapus."
    );
    await refresh();
  }

  const engine = data?.engine;
  const localModels = data?.models || [];

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-[11px] leading-relaxed text-zinc-600">
        Cari model di <b>HuggingFace</b> (mis.{" "}
        <code className="rounded bg-white px-1 text-zinc-800">
          deepseek-ai/DeepSeek-V4.1-Flash
        </code>{" "}
        atau <code className="rounded bg-white px-1 text-zinc-800">qwen3</code>) →{" "}
        <b>Download</b> ke folder project{" "}
        <code className="rounded bg-white px-1 text-zinc-800">
          {data?.models_dir || settings?.models_dir || "models/"}
        </code>{" "}
        → <b>Pakai &amp; muat</b>. Inference jalan <b>langsung di backend</b>{" "}
        (transformers) — tanpa llama.cpp, tanpa server tambahan. Boleh punya
        banyak model sekaligus dan berganti kapan saja.
      </div>

      {message && (
        <div className="whitespace-pre-line rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
          {message}
        </div>
      )}

      {/* ---- pencarian ---------------------------------------------------- */}
      <div>
        <label className="mb-1 block text-xs font-medium text-zinc-500">
          Cari model di HuggingFace
        </label>
        <div className="flex gap-2">
          <input
            className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-1.5 font-mono text-xs text-zinc-700 outline-none focus:border-accent focus:ring-2 focus:ring-accent-ring"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void search();
            }}
            placeholder="organisasi/nama-model  ·  mis. deepseek-ai/DeepSeek-V4.1-Flash"
          />
          <button
            onClick={() => void search()}
            disabled={searching || !query.trim()}
            className="shrink-0 rounded-lg border border-zinc-900 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
          >
            {searching ? "Mencari…" : "Cari"}
          </button>
        </div>
        {searchError && (
          <p className="mt-1 text-[11px] text-rose-600">{searchError}</p>
        )}
        <details className="mt-1 text-[11px] text-zinc-500">
          <summary className="cursor-pointer">
            Token HuggingFace (untuk repo gated/privat seperti DeepSeek)
            {settings?.has_hf_token ? " · tersimpan" : ""}
          </summary>
          <div className="mt-1 flex gap-2">
            <input
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-1.5 font-mono text-xs outline-none focus:border-accent"
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder={
                settings?.hf_token_masked
                  ? `tersimpan (${settings.hf_token_masked})`
                  : "hf_…"
              }
            />
            <button
              onClick={() => void saveToken()}
              className="shrink-0 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs hover:bg-zinc-50"
            >
              Simpan
            </button>
          </div>
        </details>
      </div>

      {hits && hits.length > 0 && (
        <div className="max-h-56 space-y-1.5 overflow-auto rounded-lg border border-zinc-200 p-2">
          {hits.map((h) => {
            const dl = data?.downloads.find((d) => d.repo_id === h.repo_id);
            const have = localModels.find((m) => m.repo_id === h.repo_id);
            return (
              <div
                key={h.repo_id}
                className="flex items-center justify-between gap-2 rounded-md border border-zinc-100 px-2 py-1.5"
              >
                <div className="min-w-0">
                  <p className="truncate font-mono text-[11px] text-zinc-800">
                    {h.repo_id}
                  </p>
                  <p className="text-[10.5px] text-zinc-500">
                    {[fmtParams(h.params), h.size_bytes ? `≈${fmtBytes(h.size_bytes)}` : "",
                      h.downloads ? `${h.downloads.toLocaleString()} unduhan` : "",
                      h.likes ? `${h.likes} likes` : ""]
                      .filter(Boolean)
                      .join(" · ")}
                    {have?.ready ? " · sudah terunduh" : ""}
                  </p>
                </div>
                <button
                  onClick={() =>
                    void act(h.repo_id, () => downloadHFModel(h.repo_id))
                  }
                  disabled={Boolean(dl?.status === "downloading") || busy === h.repo_id}
                  className="shrink-0 rounded-md border border-zinc-900 bg-zinc-900 px-2 py-1 text-[11px] font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
                >
                  {dl?.status === "downloading"
                    ? `${dl.percent}%`
                    : have?.ready
                      ? "Unduh ulang"
                      : "Download"}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* ---- unduhan berjalan --------------------------------------------- */}
      {(data?.downloads || []).filter((d) => d.status !== "idle").length > 0 && (
        <div className="space-y-2">
          {(data?.downloads || [])
            .filter((d) => d.status === "downloading" || d.status === "error")
            .map((d) => (
              <DownloadRow
                key={d.repo_id}
                d={d}
                busy={busy === d.repo_id}
                onCancel={() => void act(d.repo_id, () => cancelHFDownload(d.repo_id))}
              />
            ))}
        </div>
      )}

      {/* ---- model terunduh ------------------------------------------------ */}
      <div>
        <p className="mb-1 text-xs font-medium text-zinc-500">
          Model di folder <code>{data?.models_dir || "models/"}</code>
          <span className="ml-1 font-normal text-zinc-400">
            ({localModels.length})
          </span>
        </p>
        {localModels.length === 0 ? (
          <p className="rounded-lg border border-dashed border-zinc-200 px-3 py-3 text-[11px] text-zinc-400">
            Belum ada model. Cari di atas lalu klik <b>Download</b> — file
            tersimpan di folder project, bukan di cache tersembunyi.
          </p>
        ) : (
          <div className="max-h-64 space-y-2 overflow-auto pr-1">
            {localModels.map((m) => (
              <ModelRow
                key={m.repo_id}
                m={m}
                active={data?.active?.hf_model === m.repo_id}
                loadedHere={Boolean(
                  engine?.running && engine.repo_id === m.repo_id
                )}
                canLoad={Boolean(engine?.available)}
                thinking={thinking}
                busy={busy === m.repo_id}
                onUse={() =>
                  void act(m.repo_id, () =>
                    useHFModel(m.repo_id, { thinking, load: true })
                  )
                }
                onDelete={() =>
                  void act(m.repo_id, () => deleteHFModel(m.repo_id))
                }
              />
            ))}
          </div>
        )}
      </div>

      <label className="flex items-center justify-between gap-3 rounded-lg border border-zinc-200 px-3 py-2">
        <span>
          <span className="block text-xs font-medium text-zinc-700">
            Thinking (reasoning) untuk model lokal
          </span>
          <span className="block text-[11px] text-zinc-500">
            Diteruskan ke chat template sebagai <code>enable_thinking</code> —
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

      <EngineCard
        engine={engine}
        busy={busy === "__engine"}
        onStop={() => void act("__engine", () => stopHFEngine())}
      />
    </div>
  );
}

function DownloadRow({
  d,
  busy,
  onCancel,
}: {
  d: DownloadState;
  busy: boolean;
  onCancel: () => void;
}) {
  const failed = d.status === "error";
  return (
    <div
      className={`rounded-lg border p-2.5 ${
        failed ? "border-rose-200 bg-rose-50/50" : "border-zinc-200"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="truncate font-mono text-[11px] text-zinc-800">
          {d.repo_id}
        </p>
        <span className="shrink-0 text-[11px] text-zinc-500">
          {failed
            ? "gagal"
            : `${d.percent}% · ${fmtBytes(d.downloaded)} / ${fmtBytes(d.total)} · ${fmtSpeed(d.speed_bps)}`}
        </span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded bg-zinc-200">
        <div
          className={`h-full transition-[width] ${failed ? "bg-rose-500" : "bg-accent"}`}
          style={{ width: `${failed ? 100 : d.percent}%` }}
        />
      </div>
      <div className="mt-1 flex items-center justify-between gap-2">
        <p className="truncate text-[10.5px] text-zinc-500">
          {failed
            ? d.error
            : `${d.stage || "mengunduh"}${
                d.file ? ` · ${d.file}` : ""
              }${d.file_count ? ` · file ${d.file_index}/${d.file_count}` : ""}`}
        </p>
        {!failed && (
          <button
            onClick={onCancel}
            disabled={busy}
            className="shrink-0 rounded-md border border-zinc-200 px-2 py-0.5 text-[10.5px] text-zinc-500 hover:bg-zinc-50 disabled:opacity-50"
          >
            Batalkan
          </button>
        )}
      </div>
    </div>
  );
}

function ModelRow({
  m,
  active,
  loadedHere,
  canLoad,
  thinking,
  busy,
  onUse,
  onDelete,
}: {
  m: HFModel;
  active: boolean;
  loadedHere: boolean;
  canLoad: boolean;
  thinking: boolean;
  busy: boolean;
  onUse: () => void;
  onDelete: () => void;
}) {
  void thinking;
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
          <p className="truncate font-mono text-[11.5px] font-semibold text-zinc-800">
            {m.repo_id}
            {active && (
              <span className="ml-1.5 rounded bg-accent px-1.5 py-0.5 text-[10px] font-medium text-white">
                aktif
              </span>
            )}
            {loadedHere && (
              <span className="ml-1.5 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                termuat di memori
              </span>
            )}
            {m.partial && (
              <span className="ml-1.5 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                belum lengkap
              </span>
            )}
          </p>
          <p className="mt-0.5 text-[10.5px] text-zinc-500">
            {[
              fmtParams(m.params),
              fmtBytes(m.size_bytes),
              m.files ? `${m.files} file` : "",
              m.downloaded_at
                ? `diunduh ${new Date(m.downloaded_at * 1000).toLocaleDateString()}`
                : "",
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <p className="mt-0.5 truncate font-mono text-[10px] text-zinc-400">
            {m.path}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <button
            onClick={onUse}
            disabled={busy || !m.ready}
            title={
              m.ready
                ? "Jadikan model aktif dan muat ke memori"
                : "unduhan belum lengkap"
            }
            className={`${btn} border-accent bg-accent text-white hover:opacity-90`}
          >
            {busy ? "…" : "Pakai & muat"}
          </button>
          <button
            onClick={onDelete}
            disabled={busy}
            className={`${btn} border-zinc-200 text-zinc-500 hover:bg-zinc-50`}
          >
            Hapus
          </button>
        </div>
      </div>
    </div>
  );
}

function EngineCard({
  engine,
  busy,
  onStop,
}: {
  engine?: EngineStatus;
  busy: boolean;
  onStop: () => void;
}) {
  const state = engine?.state || "idle";
  const badge = {
    ready: ["bg-emerald-100 text-emerald-700", "siap"],
    loading: ["bg-sky-100 text-sky-700", "memuat model…"],
    error: ["bg-rose-100 text-rose-700", "error"],
    idle: ["bg-zinc-100 text-zinc-500", "belum ada model dimuat"],
  }[state] as [string, string];

  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2 text-[11px] text-zinc-600">
      <div className="mb-1 flex items-center justify-between gap-2">
        <p className="font-medium text-zinc-700">Inference lokal (transformers)</p>
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${badge[0]}`}>
          {badge[1]}
        </span>
      </div>
      {engine?.available ? (
        <p>
          torch {engine.deps?.torch} · transformers {engine.deps?.transformers} ·
          device <b>{engine.device || "cpu"}</b>
          {engine.running && (
            <>
              {" "}
              · model <b className="font-mono">{engine.model_label}</b> (
              {fmtParams(engine.params || 0)}, {engine.dtype})
            </>
          )}
        </p>
      ) : (
        <pre className="mt-1 whitespace-pre-line rounded bg-amber-50 px-2 py-1.5 text-[10.5px] text-amber-800">
          {engine?.install_hint ||
            "PyTorch + transformers belum ter-install: python run.py --install-local"}
        </pre>
      )}
      {engine?.error && state === "error" && (
        <pre className="mt-1 whitespace-pre-line rounded bg-rose-50 px-2 py-1.5 text-[10.5px] text-rose-700">
          {engine.error}
        </pre>
      )}
      {engine?.running && (
        <div className="mt-1.5 flex items-center justify-between gap-2">
          <span className="text-zinc-500">
            {engine.generating ? "sedang menghasilkan jawaban…" : "siap menerima chat"}
          </span>
          <button
            onClick={onStop}
            disabled={busy}
            className="rounded-md border border-zinc-300 px-2 py-0.5 text-[10.5px] hover:bg-zinc-50 disabled:opacity-50"
          >
            Lepas dari memori
          </button>
        </div>
      )}
    </div>
  );
}
