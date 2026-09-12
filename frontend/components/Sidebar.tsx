"use client";
import Logo from "./Logo";
import type { Conversation } from "@/lib/types";

const DAY = 86400;

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
  const groups = GROUP_ORDER.map((g) => ({
    name: g,
    items: conversations.filter((c) => groupOf(c) === g),
  })).filter((g) => g.items.length > 0);

  return (
    <aside className="flex h-full w-[264px] shrink-0 flex-col border-r border-zinc-200/80 bg-[#fbfbfc]">
      <div className="flex items-center gap-2 px-5 pb-4 pt-5">
        <Logo />
        <span className="text-[15px] font-semibold tracking-tight text-zinc-900">
          ask-anything
        </span>
      </div>

      <button
        onClick={onNew}
        className="mx-4 mb-3 flex items-center justify-center gap-2 rounded-lg border border-accent-ring bg-accent-soft px-3 py-2 text-sm font-medium text-accent transition hover:brightness-95"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
          <path d="M12 5v14M5 12h14" />
        </svg>
        New chat
      </button>

      <nav className="flex-1 overflow-y-auto px-3 pb-4">
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
      </nav>

      <div className="border-t border-zinc-200/80 p-4">
        <div className="mb-3 flex items-center gap-2 px-1 text-[11px] text-zinc-500">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              llmReachable ? "bg-emerald-500" : llmReachable === false ? "bg-red-400" : "bg-zinc-300"
            }`}
          />
          {llmReachable ? "LLM server terhubung" : llmReachable === false ? "LLM server offline" : "memeriksa LLM…"}
        </div>
        <button
          onClick={onSettings}
          className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50"
        >
          Settings provider
        </button>
        <p className="mt-3 text-center text-[11px] text-zinc-400">
          Privacy Policy&nbsp;&nbsp;|&nbsp;&nbsp;Terms of Service
        </p>
      </div>
    </aside>
  );
}
