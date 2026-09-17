"use client";
import { useEffect, useRef, useState } from "react";
import type { PolicyInfo, PipelineMode } from "@/lib/types";

/** Chip mode pipeline — hanya mode yang diizinkan admin yang aktif. */
export const MODE_ICONS: Record<PipelineMode, string> = {
  text: "💬",
  image: "🖼️",
  diagram: "🔀",
  ppt: "📊",
  rag: "📚",
  research: "🔭",
};

export function ModeChips({
  policy,
  mode,
  onMode,
  disabled,
}: {
  policy: PolicyInfo | null;
  mode: PipelineMode;
  onMode: (m: PipelineMode) => void;
  disabled?: boolean;
}) {
  if (!policy) return null;
  const modes: PipelineMode[] = ["text", "image", "diagram", "ppt", "rag"];
  return (
    <div
      className="flex items-center gap-1"
      data-testid="mode-chips"
      role="radiogroup"
      aria-label="Mode pipeline"
    >
      {modes.map((m) => {
        const allowed = policy.modes?.[m] !== false;
        const active = mode === m;
        const label = policy.labels?.[m] || m;
        return (
          <button
            key={m}
            role="radio"
            aria-checked={active}
            disabled={disabled}
            onClick={() => allowed && onMode(m)}
            title={
              allowed
                ? `Mode ${label}`
                : `Mode ${label} dimatikan admin (halaman Admin → Pipeline)`
            }
            className={`flex items-center gap-1 rounded-lg border px-2 py-1.5 text-xs font-medium transition ${
              !allowed
                ? "cursor-not-allowed border-zinc-200 bg-zinc-50 text-zinc-300"
                : active
                ? "border-accent bg-accent-soft text-accent"
                : "border-zinc-200 bg-white text-zinc-500 hover:bg-zinc-50"
            }`}
          >
            <span>{MODE_ICONS[m]}</span>
            <span className={m === "text" ? "hidden sm:inline" : ""}>
              {allowed ? label : `🔒 ${label}`}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export const ACCENTS: Record<string, { accent: string; soft: string; ring: string }> = {
  indigo: { accent: "#6366f1", soft: "#eef2ff", ring: "#c7d2fe" },
  violet: { accent: "#8b5cf6", soft: "#f5f3ff", ring: "#ddd6fe" },
  orange: { accent: "#f97316", soft: "#fff7ed", ring: "#fed7aa" },
  zinc: { accent: "#52525b", soft: "#f4f4f5", ring: "#d4d4d8" },
};

export default function Composer({
  value,
  onChange,
  onSend,
  disabled,
  accent,
  onAccent,
  compact,
  deepResearch,
  onDeepResearch,
  policy,
  mode = "text",
  onMode,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled?: boolean;
  accent: string;
  onAccent: (a: string) => void;
  compact?: boolean;
  deepResearch?: boolean;
  onDeepResearch?: (v: boolean) => void;
  policy?: PolicyInfo | null;
  mode?: PipelineMode;
  onMode?: (m: PipelineMode) => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = `${Math.min(ref.current.scrollHeight, 180)}px`;
    }
  }, [value]);

  return (
    <div className={`rounded-2xl border border-zinc-200 bg-white shadow-card ${compact ? "p-3" : "p-4"}`}>
      <textarea
        ref={ref}
        rows={compact ? 1 : 2}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (value.trim() && !disabled) onSend();
          }
        }}
        placeholder={
          deepResearch
            ? "Masukkan topik untuk riset mendalam (mis: artificial intelligence, quantum computing)…"
            : mode === "rag"
            ? "Tanyakan apa pun tentang dokumen yang sudah di-upload …"
            : mode === "image"
            ? "Deskripsikan gambar yang ingin dibuat …"
            : mode === "ppt"
            ? "Sebutkan topik deck PPT (mis: rencana rilis produk) …"
            : compact
            ? "Lanjutkan percakapan …"
            : "Tanyakan apa pun — browsing, diagram, analisis …"
        }
        className="w-full resize-none bg-transparent text-[15px] leading-6 text-zinc-800 placeholder-zinc-400 outline-none"
      />
      {onMode && (
        <div className="mt-2.5">
          <ModeChips policy={policy ?? null} mode={mode} onMode={onMode} disabled={disabled} />
        </div>
      )}
      <div className="mt-2 flex items-center justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <span
            title={
              policy
                ? `Tools diizinkan admin: ${Object.entries(policy.tools)
                    .filter(([, on]) => on)
                    .map(([n]) => n)
                    .join(", ") || "(tidak ada)"}`
                : "Tools aktif: web_search, fetch_url, create_diagram, calculator"
            }
            className="flex cursor-help items-center gap-1.5 rounded-lg border border-zinc-200 bg-zinc-50 px-2.5 py-1.5 text-xs text-zinc-500"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L4 17v3h3l5.3-5.3a4 4 0 0 0 5.4-5.4l-2.9 2.9-2.1-2.1 2.9-2.9z" />
            </svg>
            {policy ? Object.values(policy.tools).filter(Boolean).length : 4} tools
          </span>
          {onDeepResearch && (
            <button
              onClick={() => onDeepResearch(!deepResearch)}
              title={
                deepResearch
                  ? "Deep Research ON — Klik untuk matikan (kembali ke mode chat biasa)"
                  : "Deep Research OFF — Klik untuk mengaktifkan mode riset mendalam dengan canvas interaktif"
              }
              className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition ${
                deepResearch
                  ? "border-violet-300 bg-violet-50 text-violet-700"
                  : "border-zinc-200 bg-zinc-50 text-zinc-500 hover:bg-zinc-100"
              }`}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <path d="M21 21l-4.35-4.35" />
                <path d="M11 8v6M8 11h6" />
              </svg>
              {deepResearch ? "Deep Research ✓" : "Deep Research"}
            </button>
          )}
          <div className="flex items-center gap-1 rounded-lg border border-zinc-200 bg-zinc-50 px-2 py-1.5">
            {Object.entries(ACCENTS).map(([name, c]) => (
              <button
                key={name}
                onClick={() => onAccent(name)}
                title={name}
                className={`h-4 w-4 rounded transition ${accent === name ? "ring-2 ring-zinc-400 ring-offset-1" : "hover:scale-110"}`}
                style={{ background: c.accent }}
              />
            ))}
          </div>
        </div>
        <button
          onClick={() => value.trim() && !disabled && onSend()}
          disabled={disabled || !value.trim()}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-zinc-100 px-3.5 py-1.5 text-sm font-medium text-zinc-700 transition hover:bg-zinc-200 disabled:opacity-50"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" />
            <path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z" />
          </svg>
          {disabled ? "Thinking…" : "Ask"}
        </button>
      </div>
    </div>
  );
}
