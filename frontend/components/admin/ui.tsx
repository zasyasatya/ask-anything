"use client";
/* Atom UI kecil yang dipakai semua tab halaman Admin. */
import type { ReactNode } from "react";

export function Card({
  title,
  subtitle,
  children,
  right,
}: {
  title: string;
  subtitle?: string;
  children?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-zinc-800">{title}</h3>
          {subtitle && (
            <p className="mt-0.5 text-[12px] text-zinc-500">{subtitle}</p>
          )}
        </div>
        {right}
      </div>
      {children && <div className="mt-3">{children}</div>}
    </section>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  hint,
  locked,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  hint?: string;
  locked?: boolean;
}) {
  return (
    <label
      className={`flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5 ${
        locked
          ? "border-zinc-100 bg-zinc-50"
          : "border-zinc-200 bg-white hover:bg-zinc-50"
      }`}
    >
      <span className="min-w-0">
        <span
          className={`block text-[13px] font-medium ${
            checked ? "text-zinc-800" : "text-zinc-500"
          }`}
        >
          {label} {locked && <span title="Dikunci (kontrak produk)">🔒</span>}
        </span>
        {hint && (
          <span className="mt-0.5 block text-[11.5px] leading-4 text-zinc-400">
            {hint}
          </span>
        )}
      </span>
      <button
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={locked}
        onClick={() => !locked && onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition ${
          checked ? "bg-emerald-500" : "bg-zinc-300"
        } ${locked ? "opacity-60" : "cursor-pointer"}`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
            checked ? "left-[22px]" : "left-0.5"
          }`}
        />
      </button>
    </label>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone = "zinc",
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "zinc" | "green" | "amber" | "red" | "indigo";
}) {
  const tones: Record<string, string> = {
    zinc: "border-zinc-200 bg-white",
    green: "border-emerald-200 bg-emerald-50/60",
    amber: "border-amber-200 bg-amber-50/60",
    red: "border-red-200 bg-red-50/60",
    indigo: "border-indigo-200 bg-indigo-50/60",
  };
  return (
    <div className={`rounded-2xl border p-4 shadow-card ${tones[tone]}`}>
      <p className="text-[11.5px] font-medium uppercase tracking-wide text-zinc-400">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold text-zinc-800">{value}</p>
      {hint && <p className="mt-0.5 text-[11.5px] text-zinc-500">{hint}</p>}
    </div>
  );
}

export function fmtBytes(n: number): string {
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  if (n > 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${n} B`;
}

export function fmtTime(ts: number): string {
  try {
    return new Date(ts * 1000).toLocaleString("id-ID", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(ts);
  }
}
