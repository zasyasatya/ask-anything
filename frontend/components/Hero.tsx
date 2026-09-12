"use client";
import { useState } from "react";
import Composer from "./Composer";

const SAMPLES = [
  { label: "Browsing berita", cat: "Browsing", icon: "🌐", prompt: "Cari berita teknologi terkini minggu ini, rangkum 3 teratas lengkap dengan link sumber." },
  { label: "Diagram alir", cat: "Diagram", icon: "🔀", prompt: "Buatkan diagram alir proses registrasi pengguna dengan langkah validasi email." },
  { label: "Graph relasi", cat: "Diagram", icon: "🕸️", prompt: "Gambarkan graph relasi antar microservice: gateway, auth, billing, catalog, notification." },
  { label: "Rangkum URL", cat: "Browsing", icon: "📄", prompt: "Ringkas halaman https://en.wikipedia.org/wiki/Large_language_model dalam 5 poin." },
  { label: "Kalkulasi", cat: "Tools", icon: "🧮", prompt: "Hitung (1250 * 8) / 100 + 2 ** 5 dan jelaskan urutannya." },
  { label: "Jelaskan + skema", cat: "Diagram", icon: "🧠", prompt: "Jelaskan cara kerja DNS resolution lalu buat diagram alurnya." },
];

const TABS = ["All", "Browsing", "Diagram", "Tools"];

export default function Hero({
  input,
  setInput,
  onSend,
  streaming,
  accent,
  onAccent,
}: {
  input: string;
  setInput: (v: string) => void;
  onSend: () => void;
  streaming: boolean;
  accent: string;
  onAccent: (a: string) => void;
}) {
  const [tab, setTab] = useState("All");
  const shown = SAMPLES.filter((s) => tab === "All" || s.cat === tab);

  return (
    <div className="grid-bg flex-1 overflow-y-auto">
      <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col items-center px-6 pt-[9vh]">
        <span className="mb-5 rounded-md border border-zinc-200 bg-zinc-100/80 px-2.5 py-1 text-xs text-zinc-500">
          Powered by agentic LLM · HF local & OpenAI
        </span>
        <h1 className="text-center text-5xl font-semibold leading-[1.12] tracking-tight text-zinc-800 md:text-6xl">
          Ask Anything,
          <br />
          Agents Do The Rest
        </h1>
        <p className="mt-4 text-center text-[15px] text-zinc-500">
          Browsing web, diagram alir & graph — dengan seluruh proses LLM yang terlihat.
        </p>

        <div className="mt-8 w-full max-w-xl">
          <Composer
            value={input}
            onChange={setInput}
            onSend={onSend}
            disabled={streaming}
            accent={accent}
            onAccent={onAccent}
          />
        </div>

        <div className="mt-5 flex flex-wrap justify-center gap-2">
          {["Browsing →", "Diagram alir →", "Diagram graph →", "Rangkum URL →"].map((c, i) => (
            <button
              key={c}
              onClick={() => setInput(SAMPLES[[0, 1, 2, 3][i]].prompt)}
              className="rounded-lg border border-zinc-300/80 bg-white/60 px-3 py-1.5 text-[13px] text-zinc-600 transition hover:bg-white hover:shadow-card"
            >
              {c}
            </button>
          ))}
        </div>

        <div className="mt-14 w-full max-w-2xl pb-16">
          <div className="mb-3 flex items-baseline gap-2">
            <h2 className="text-lg font-semibold text-zinc-900">Explore</h2>
            <span className="text-xs text-zinc-400">({shown.length})</span>
          </div>
          <div className="mb-4 flex gap-1.5">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-md border px-2.5 py-1 text-xs transition ${
                  tab === t
                    ? "border-zinc-300 bg-zinc-100 font-medium text-zinc-800"
                    : "border-zinc-200 text-zinc-500 hover:bg-white"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {shown.map((s) => (
              <button
                key={s.label}
                onClick={() => setInput(s.prompt)}
                className="group rounded-xl border border-zinc-200 bg-white/70 p-4 text-left transition hover:-translate-y-0.5 hover:bg-white hover:shadow-card"
              >
                <div className="mb-2 text-xl">{s.icon}</div>
                <p className="text-sm font-medium text-zinc-800">{s.label}</p>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-zinc-500">{s.prompt}</p>
                <p className="mt-2 text-[11px] text-accent opacity-0 transition group-hover:opacity-100">
                  Coba prompt ini →
                </p>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
