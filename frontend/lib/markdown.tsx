/* Minimal, dependency-free markdown renderer: headings, lists, bold, inline
   code, links, blockquotes and fenced code (mermaid → DiagramBlock:
   graph HTML interaktif secara default, Mermaid sebagai mode alternatif).

   Ditambah dua hal yang membuat jawaban bisa diverifikasi:
   - marker sitasi `[n]` di dalam teks → chip superscript yang tertaut ke URL;
   - provenance diagram diteruskan ke DiagramBlock (badge "dari tool" / "ditulis
     model") supaya visual tidak disalahartikan sebagai sumber web. */
import type { ReactNode } from "react";
import DiagramBlock from "@/components/DiagramBlock";
import type { SourceRef } from "./sources";

export interface DiagramOrigin {
  tool: string;
  titles: string[];
}

function CiteChips({ nums, sources }: { nums: number[]; sources: SourceRef[] }) {
  return (
    <>
      {nums.map((n) => {
        const s = sources.find((x) => x.index === n);
        const inner = (
          <span className="rounded bg-accent-soft px-1 font-mono text-[0.7em] font-semibold text-accent">
            {n}
          </span>
        );
        return s ? (
          <a
            key={`c${n}`}
            href={s.url}
            target="_blank"
            rel="noreferrer"
            title={`${s.title}\n${s.url}\n(${s.tool}${s.read ? ", dibaca penuh" : ", cuplikan"})`}
            className="mx-[1px] align-super no-underline hover:opacity-80"
          >
            [{inner}]
          </a>
        ) : (
          <span
            key={`c${n}`}
            title="Nomor sitasi tidak ada di daftar sumber"
            className="mx-[1px] align-super"
          >
            [<span className="rounded bg-red-50 px-1 font-mono text-[0.7em] font-semibold text-red-600">{n}</span>]
          </span>
        );
      })}
    </>
  );
}

function inline(
  text: string,
  keyBase: string,
  sources: SourceRef[] = []
): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|\[\d{1,3}(?:\s*[,;-]\s*\d{1,3})*\])/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) {
      out.push(<strong key={`${keyBase}-${i++}`} className="font-semibold text-zinc-900">{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("`")) {
      out.push(
        <code key={`${keyBase}-${i++}`} className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-[0.85em] text-zinc-700">
          {tok.slice(1, -1)}
        </code>
      );
    } else if (tok.startsWith("[")) {
      const linkMatch = /\[([^\]]+)\]\(([^)]+)\)/.exec(tok);
      const citeMatch = /^\[(\d{1,3}(?:\s*[,;-]\s*\d{1,3})*)\]$/.exec(tok);
      if (linkMatch) {
        out.push(
          <a key={`${keyBase}-${i++}`} href={linkMatch[2]} target="_blank" rel="noreferrer"
             className="text-accent underline decoration-accent-ring underline-offset-2 hover:opacity-80">
            {linkMatch[1]}
          </a>
        );
      } else if (citeMatch) {
        const nums = citeMatch[1]
          .split(/[,;-]/)
          .map((n) => parseInt(n.trim(), 10))
          .filter((n) => Number.isFinite(n));
        out.push(<CiteChips key={`${keyBase}-${i++}`} nums={nums} sources={sources} />);
      } else {
        out.push(tok);
      }
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export default function Markdown({
  text,
  sources = [],
  diagramOrigin = null,
}: {
  text: string;
  /** Daftar sumber bernomor — dipakai untuk menautkan marker [n]. */
  sources?: SourceRef[];
  /** Provenance diagram pada jawaban ini (tool create_diagram vs ditulis model). */
  diagramOrigin?: DiagramOrigin | null;
}) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        buf.push(lines[i]);
        i++;
      }
      i++; // closing fence
      const code = buf.join("\n");
      if (lang === "mermaid") {
        blocks.push(
          <DiagramBlock key={key++} source={code} provenance={diagramOrigin} />
        );
      } else {
        blocks.push(
          <pre key={key++} className="my-2 overflow-x-auto rounded-xl border border-zinc-200 bg-zinc-50 p-3 font-mono text-xs leading-5 text-zinc-700">
            {code}
          </pre>
        );
      }
      continue;
    }

    const h = /^(#{1,4})\s+(.*)/.exec(line);
    if (h) {
      const level = h[1].length;
      const cls =
        level === 1 ? "mt-4 mb-2 text-xl font-semibold text-zinc-900"
        : level === 2 ? "mt-3 mb-1.5 text-lg font-semibold text-zinc-900"
        : "mt-2 mb-1 text-base font-semibold text-zinc-900";
      blocks.push(<div key={key++} className={cls}>{inline(h[2], `h${key}`, sources)}</div>);
      i++;
      continue;
    }

    if (/^\s*([-*])\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      const ordered = /^\s*\d+\.\s+/.test(line);
      while (i < lines.length && (/^\s*([-*])\s+/.test(lines[i]) || /^\s*\d+\.\s+/.test(lines[i]))) {
        items.push(lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ""));
        i++;
      }
      const listCls = "my-2 list-inside space-y-1 text-[15px] leading-6 text-zinc-700";
      blocks.push(
        ordered ? (
          <ol key={key++} className={`${listCls} list-decimal`}>
            {items.map((it, j) => <li key={j}>{inline(it, `li${key}-${j}`, sources)}</li>)}
          </ol>
        ) : (
          <ul key={key++} className={`${listCls} list-disc`}>
            {items.map((it, j) => <li key={j}>{inline(it, `ul${key}-${j}`, sources)}</li>)}
          </ul>
        )
      );
      continue;
    }

    if (line.startsWith("> ")) {
      blocks.push(
        <blockquote key={key++} className="my-2 border-l-2 border-accent pl-3 text-sm italic text-zinc-500">
          {inline(line.slice(2), `q${key}`, sources)}
        </blockquote>
      );
      i++;
      continue;
    }

    if (line.trim() === "") {
      i++;
      continue;
    }

    const para: string[] = [line];
    i++;
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !lines[i].startsWith("```") &&
      !lines[i].startsWith("#") &&
      !/^\s*([-*]|\d+\.)\s+/.test(lines[i]) &&
      !lines[i].startsWith("> ")
    ) {
      para.push(lines[i]);
      i++;
    }
    blocks.push(
      <p key={key++} className="my-1.5 text-[15px] leading-7 text-zinc-700">
        {inline(para.join(" "), `p${key}`, sources)}
      </p>
    );
  }

  return <div>{blocks}</div>;
}
