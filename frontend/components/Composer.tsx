"use client";
import { useEffect, useRef, useState } from "react";

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
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled?: boolean;
  accent: string;
  onAccent: (a: string) => void;
  compact?: boolean;
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
        placeholder={compact ? "Lanjutkan percakapan …" : "Tanyakan apa pun — browsing, diagram, analisis …"}
        className="w-full resize-none bg-transparent text-[15px] leading-6 text-zinc-800 placeholder-zinc-400 outline-none"
      />
      <div className="mt-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            title="Tools aktif: web_search, fetch_url, create_diagram, calculator"
            className="flex cursor-help items-center gap-1.5 rounded-lg border border-zinc-200 bg-zinc-50 px-2.5 py-1.5 text-xs text-zinc-500"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L4 17v3h3l5.3-5.3a4 4 0 0 0 5.4-5.4l-2.9 2.9-2.1-2.1 2.9-2.9z" />
            </svg>
            4 tools
          </span>
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
