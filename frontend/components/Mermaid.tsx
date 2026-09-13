"use client";
import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

let initialized = false;

export default function Mermaid({
  source,
  title,
  bare,
  onError,
}: {
  source: string;
  title?: string;
  /** tanpa kartu pembungkus (saat dipakai di dalam DiagramBlock) */
  bare?: boolean;
  /** callback status error render (null = sukses) */
  onError?: (msg: string | null) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!initialized) {
      mermaid.initialize({
        startOnLoad: false,
        theme: "neutral",
        securityLevel: "strict",
        flowchart: { useMaxWidth: true, htmlLabels: true },
      });
      initialized = true;
    }
    const id = `mm-${Math.random().toString(36).slice(2, 9)}`;
    let cancelled = false;
    mermaid
      .render(id, source)
      .then(({ svg }) => {
        if (!cancelled && ref.current) {
          ref.current.innerHTML = svg;
          setError(null);
          onError?.(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          const msg = String(e?.message || e);
          setError(msg);
          onError?.(msg);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [source, onError]);

  const body = error ? (
    <pre className="overflow-x-auto font-mono text-xs text-zinc-600">{source}</pre>
  ) : (
    <div ref={ref} className="flex justify-center overflow-x-auto" />
  );

  if (bare) {
    return (
      <div>
        {error && (
          <span className="mb-2 inline-block rounded-md bg-red-50 px-2 py-0.5 text-[11px] text-red-600">
            render error
          </span>
        )}
        {body}
      </div>
    );
  }

  return (
    <div className="my-3 rounded-xl border border-zinc-200 bg-white p-3 shadow-card">
      <div className="mb-2 flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-500">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="7" rx="1.5" />
            <rect x="14" y="14" width="7" height="7" rx="1.5" />
            <path d="M10 6.5h7M6.5 10v7M14 17.5H10" />
          </svg>
          {title || "mermaid diagram"}
        </span>
        {error && (
          <span className="rounded-md bg-red-50 px-2 py-0.5 text-[11px] text-red-600">
            render error
          </span>
        )}
      </div>
      {body}
    </div>
  );
}
