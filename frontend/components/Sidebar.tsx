"use client";
/* Left navbar — bisa di-collapse jadi rail ikon (64px) atau di-expand penuh
   (268px). Keadaan disimpan di localStorage (`aa:nav-collapsed`) dan bisa
   ditoggle dengan Ctrl/Cmd+B. Saat collapsed, semua item tetap reachable:
   ikon + tooltip, dan riwayat ditampilkan sebagai rail titik dengan judul di
   `title`/`aria-label` supaya tetap bisa dipilih lewat keyboard. */
import { useCallback, useEffect, useState } from "react";
import Logo from "./Logo";
import type { Conversation } from "@/lib/types";

const DAY = 86400;
const LS_KEY = "aa:nav-collapsed";

const EXPANDED_W = 268;
const RAIL_W = 64;

function groupOf(c: Conversation): string {
  const now = Date.now() / 1000;
  const age = now - c.updated_at;
  const today = new Date().setHours(0, 0, 0, 0) / 1000;
  if (c.updated_at >= today) return "Today";
  if (age < 2 * DAY) return "Yesterday";
  if (age < 7 * DAY) return "Previous 7 Days";
  if (age < 30 * DAY) return "Previous 30 Days";
  return "Older";
}

const GROUP_ORDER = ["Today", "Yesterday", "Previous 7 Days", "Previous 30 Days", "Older"];

function readCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(LS_KEY) === "1";
  } catch {
    return false;
  }
}

/** Hydration-safe: state awal selalu "expand", disinkronkan di efek pertama. */
export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onSettings,
  llmReachable,
}: {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onSettings: () => void;
  llmReachable: boolean | null;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setCollapsed(readCollapsed());
    setHydrated(true);
  }, []);

  const toggle = useCallback(() => {
    setCollapsed((c) => {
      const next = !c;
      try {
        window.localStorage.setItem(LS_KEY, next ? "1" : "0");
      } catch {
        /* private mode dsb. — toggle tetap jalan, hanya tidak dipersist */
      }
      return next;
    });
  }, []);

  // Pintasan global Ctrl/Cmd+B — panel kanan (interpreter) pakai tombol sendiri.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);

  const groups = GROUP_ORDER.map((g) => ({
    name: g,
    items: conversations.filter((c) => groupOf(c) === g),
  })).filter((g) => g.items.length > 0);

  const statusDot = llmReachable
    ? "bg-emerald-500"
    : llmReachable === false
      ? "bg-red-400"
      : "bg-zinc-300";
  const statusText = llmReachable
    ? "LLM server terhubung"
    : llmReachable === false
      ? "LLM server offline"
      : "memeriksa LLM…";

  return (
    <aside
      data-testid="sidebar"
      data-collapsed={collapsed ? "true" : "false"}
      aria-label="Navigasi kiri"
      className="flex h-full shrink-0 flex-col border-r border-zinc-200/80 bg-[#fbfbfc] transition-[width] duration-200 ease-out"
      // Lebar diset inline supaya transisi halus & tetap konsisten saat
      // halaman dirender ulang (hydrated=false → expanded).
      style={{ width: hydrated && collapsed ? RAIL_W : EXPANDED_W }}
    >
      {/* brand + toggle */}
      <div
        className={`flex items-center gap-2 pb-4 pt-5 ${collapsed ? "justify-center px-2" : "px-5"}`}
      >
        <Logo />
        {!collapsed && (
          <span className="min-w-0 flex-1 truncate text-[15px] font-semibold tracking-tight text-zinc-900">
            ask-anything
          </span>
        )}
        <button
          type="button"
          data-testid="sidebar-toggle"
          onClick={toggle}
          aria-expanded={!collapsed}
          aria-controls="sidebar"
          title={collapsed ? "Expand navbar (Ctrl+B)" : "Collapse navbar (Ctrl+B)"}
          aria-label={collapsed ? "Expand navigasi kiri" : "Collapse navigasi kiri"}
          className="grid h-7 w-7 shrink-0 place-items-center rounded-md border border-zinc-200 bg-white text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-800"
        >
          <svg
            width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            style={{ transform: collapsed ? "rotate(180deg)" : undefined, transition: "transform 200ms" }}
          >
            <path d="M15 6l-6 6 6 6" />
          </svg>
        </button>
      </div>

      {/* new chat */}
      <div className={collapsed ? "px-2" : "px-4"}>
        <button
          onClick={onNew}
          title="New chat"
          aria-label="New chat"
          data-testid="nav-new-chat"
          className={`flex items-center justify-center gap-2 rounded-lg border border-accent-ring bg-accent-soft px-3 py-2 text-sm font-medium text-accent transition hover:brightness-95 ${collapsed ? "h-9 w-9" : "w-full"}`}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
          {!collapsed && "New chat"}
        </button>
      </div>

      {/* admin console */}
      <div className={collapsed ? "px-2 pt-3" : "px-4 pt-3"}>
        <a
          href="/admin"
          title="Konsol admin: mode & tool, memori, artifact, feedback, RAG"
          className={`flex items-center justify-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-600 transition hover:bg-zinc-50 ${collapsed ? "h-9 w-9" : "w-full"}`}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M12 15a3 3 0 100-6 3 3 0 000 6z" />
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33h0a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51h0a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82v0a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z" />
          </svg>
          {!collapsed && "Admin"}
        </a>
      </div>

      {/* riwayat */}
      <nav className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-3 pb-4 pt-3">
        {collapsed ? (
          <ul className="flex flex-col items-center gap-1.5">
            {groups.flatMap((g) => g.items).map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => onSelect(c.id)}
                  title={c.title || "New chat"}
                  aria-label={`Buka percakapan: ${c.title || "New chat"}`}
                  className={`grid h-8 w-8 place-items-center rounded-md transition ${
                    c.id === activeId
                      ? "bg-zinc-200/80 ring-1 ring-zinc-300"
                      : "hover:bg-zinc-100"
                  }`}
                >
                  <span className={`h-2 w-2 rounded-full ${c.id === activeId ? "bg-accent" : "bg-zinc-300"}`} />
                </button>
              </li>
            ))}
            {!groups.length && (
              <li className="pt-3 text-center font-mono text-[10px] text-zinc-300">0</li>
            )}
          </ul>
        ) : (
          <>
            {groups.length === 0 && (
              <p className="px-2 pt-6 text-center text-xs leading-5 text-zinc-400">
                Belum ada percakapan.
                <br />
                Mulai dengan pertanyaan apa pun.
              </p>
            )}
            {groups.map((g) => (
              <div key={g.name} className="mb-4">
                <p className="mb-1 px-2 text-[11px] font-medium text-zinc-400">{g.name}</p>
                {g.items.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => onSelect(c.id)}
                    className={`block w-full truncate rounded-md px-2 py-1.5 text-left text-[13px] transition ${
                      c.id === activeId
                        ? "bg-zinc-200/70 text-zinc-900"
                        : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
                    }`}
                    title={c.title}
                  >
                    {c.title || "New chat"}
                  </button>
                ))}
              </div>
            ))}
          </>
        )}
      </nav>

      {/* status + settings */}
      <div className={`border-t border-zinc-200/80 p-4 ${collapsed ? "px-2" : ""}`}>
        <div
          className={`mb-3 flex items-center text-[11px] text-zinc-500 ${collapsed ? "justify-center" : "gap-2 px-1"}`}
          title={statusText}
        >
          <span data-testid="llm-status-dot" className={`inline-block h-2 w-2 shrink-0 rounded-full ${statusDot}`} />
          {!collapsed && statusText}
        </div>
        <button
          onClick={onSettings}
          title="Settings provider"
          aria-label="Settings provider"
          data-testid="nav-settings"
          className={`w-full rounded-lg border border-zinc-200 bg-white text-sm text-zinc-700 transition hover:bg-zinc-50 ${collapsed ? "grid h-9 w-9 place-items-center !px-0" : "px-3 py-2"}`}
        >
          {collapsed ? (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 8.6 19.3a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.24 15a1.7 1.7 0 0 0-1.55-1H2.6a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.24 8.6a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 8.6 4.24h.06A1.7 1.7 0 0 0 10.2 2.6V2.6a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87v.06a1.7 1.7 0 0 0 1.55 1h.09a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.55 1z" />
            </svg>
          ) : (
            "Settings provider"
          )}
        </button>
        {!collapsed && (
          <p className="mt-3 text-center text-[11px] text-zinc-400">
            Privacy Policy&nbsp;&nbsp;|&nbsp;&nbsp;Terms of Service
          </p>
        )}
      </div>
    </aside>
  );
}
