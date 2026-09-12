import Link from "next/link";
import type { ReactNode } from "react";

/* Kerangka halaman dokumentasi in-app (/panduan & /developer).
   Desain mengikuti design system aplikasi: zinc + aksen indigo. */

export function DocNav({ active }: { active: "panduan" | "developer" }) {
  const item = (href: string, label: string, on: boolean) => (
    <Link
      href={href}
      className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
        on ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100"
      }`}
    >
      {label}
    </Link>
  );
  return (
    <header className="sticky top-0 z-20 border-b border-zinc-200/80 bg-white/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-[15px] font-semibold tracking-tight text-zinc-900">
            ask-anything
          </Link>
          <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-500">
            docs
          </span>
        </div>
        <nav className="flex items-center gap-1">
          {item("/panduan", "Panduan Pengguna", active === "panduan")}
          {item("/developer", "Docs Developer", active === "developer")}
          <a
            href="/slides/slides-cara-kerja.html"
            target="_blank"
            rel="noreferrer"
            className="rounded-lg px-3 py-1.5 text-sm font-medium text-zinc-600 transition hover:bg-zinc-100"
          >
            Slides →
          </a>
          {item("/", "← Aplikasi", false)}
        </nav>
      </div>
    </header>
  );
}

export function DocShell({
  active,
  title,
  subtitle,
  toc,
  children,
}: {
  active: "panduan" | "developer";
  title: string;
  subtitle: string;
  toc: Array<[string, string]>;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#f7f7f8] text-zinc-900">
      <DocNav active={active} />
      <div className="mx-auto flex max-w-6xl gap-10 px-6 py-10">
        <aside className="hidden w-56 shrink-0 lg:block">
          <nav className="sticky top-24 space-y-1">
            <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
              Daftar isi
            </p>
            {toc.map(([id, label]) => (
              <a
                key={id}
                href={`#${id}`}
                className="block rounded-md px-2 py-1 text-[13px] text-zinc-600 transition hover:bg-zinc-100 hover:text-zinc-900"
              >
                {label}
              </a>
            ))}
          </nav>
        </aside>
        <main className="min-w-0 flex-1">
          <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-2 text-[15px] leading-7 text-zinc-500">{subtitle}</p>
          <div className="mt-8 space-y-10">{children}</div>
          <footer className="mt-16 border-t border-zinc-200 pt-6 text-xs text-zinc-400">
            Dokumen ini bagian dari repo — sunting via{" "}
            <code className="rounded bg-zinc-100 px-1">frontend/app/{active}/page.tsx</code> dan{" "}
            <code className="rounded bg-zinc-100 px-1">docs/</code>. Screenshot dihasilkan ulang dengan{" "}
            <code className="rounded bg-zinc-100 px-1">scripts/capture_screenshots.py</code>.
          </footer>
        </main>
      </div>
    </div>
  );
}

export function H2({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h2 id={id} className="scroll-mt-24 text-xl font-semibold tracking-tight text-zinc-900">
      {children}
    </h2>
  );
}

export function H3({ children }: { children: ReactNode }) {
  return <h3 className="text-[15px] font-semibold text-zinc-800">{children}</h3>;
}

export function P({ children }: { children: ReactNode }) {
  return <p className="text-[14.5px] leading-7 text-zinc-600">{children}</p>;
}

export function UL({ items }: { items: ReactNode[] }) {
  return (
    <ul className="list-disc space-y-1.5 pl-5 text-[14.5px] leading-6 text-zinc-600 marker:text-zinc-300">
      {items.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ul>
  );
}

export function OL({ items }: { items: ReactNode[] }) {
  return (
    <ol className="list-decimal space-y-1.5 pl-5 text-[14.5px] leading-6 text-zinc-600 marker:text-zinc-400">
      {items.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ol>
  );
}

export function Code({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded-xl border border-zinc-200 bg-zinc-900 p-4 font-mono text-[12.5px] leading-5 text-zinc-100">
      {children}
    </pre>
  );
}

export function Shot({ src, alt, caption }: { src: string; alt: string; caption: string }) {
  return (
    <figure className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-card">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} className="w-full" />
      <figcaption className="border-t border-zinc-100 bg-zinc-50/70 px-4 py-2.5 text-[12.5px] leading-5 text-zinc-500">
        {caption}
      </figcaption>
    </figure>
  );
}

export function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
      <table className="w-full border-collapse text-left text-[13px] leading-5">
        <thead>
          <tr className="border-b border-zinc-200 bg-zinc-50/80">
            {head.map((h) => (
              <th key={h} className="px-3.5 py-2.5 font-semibold text-zinc-700">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-zinc-100 last:border-0">
              {r.map((c, j) => (
                <td key={j} className="px-3.5 py-2.5 align-top text-zinc-600">
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function C({ children }: { children: ReactNode }) {
  return <code className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[12.5px] text-zinc-700">{children}</code>;
}

export function Note({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 px-4 py-3 text-[13.5px] leading-6 text-indigo-900">
      {children}
    </div>
  );
}
