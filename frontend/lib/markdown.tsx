/* Minimal, dependency-free markdown renderer: headings, lists, bold, inline
   code, links, blockquotes and fenced code (mermaid auto-rendered). */
import type { ReactNode } from "react";
import Mermaid from "@/components/Mermaid";

function inline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
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
    } else {
      const mm = /\[([^\]]+)\]\(([^)]+)\)/.exec(tok);
      if (mm) {
        out.push(
          <a key={`${keyBase}-${i++}`} href={mm[2]} target="_blank" rel="noreferrer"
             className="text-accent underline decoration-accent-ring underline-offset-2 hover:opacity-80">
            {mm[1]}
          </a>
        );
      }
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export default function Markdown({ text }: { text: string }) {
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
        blocks.push(<Mermaid key={key++} source={code} />);
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
      blocks.push(<div key={key++} className={cls}>{inline(h[2], `h${key}`)}</div>);
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
            {items.map((it, j) => <li key={j}>{inline(it, `li${key}-${j}`)}</li>)}
          </ol>
        ) : (
          <ul key={key++} className={`${listCls} list-disc`}>
            {items.map((it, j) => <li key={j}>{inline(it, `ul${key}-${j}`)}</li>)}
          </ul>
        )
      );
      continue;
    }

    if (line.startsWith("> ")) {
      blocks.push(
        <blockquote key={key++} className="my-2 border-l-2 border-accent pl-3 text-sm italic text-zinc-500">
          {inline(line.slice(2), `q${key}`)}
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
        {inline(para.join(" "), `p${key}`)}
      </p>
    );
  }

  return <div>{blocks}</div>;
}
