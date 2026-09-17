"use client";
/* Kartu artifact (gambar / PPTX) hasil tool generatif.
   Live: dari event `artifact` (via reducer live.ts). Riwayat: dari meta
   pesan assistant — sama-sama memakai URL /api/artifacts/{id}/download. */
/** Menerima bentuk live (dari event trace) maupun riwayat (meta pesan). */
export interface ArtifactRef {
  id: string;
  kind: string;
  title: string;
  url: string;
  tool?: string;
  size_bytes?: number;
}

const KIND_META: Record<string, { icon: string; label: string; tone: string }> =
  {
    image: { icon: "🖼️", label: "Gambar", tone: "border-sky-200 bg-sky-50/60" },
    pptx: {
      icon: "📊",
      label: "Deck PPT",
      tone: "border-orange-200 bg-orange-50/60",
    },
    document: {
      icon: "📄",
      label: "Dokumen",
      tone: "border-zinc-200 bg-zinc-50",
    },
    data: { icon: "📦", label: "Data", tone: "border-zinc-200 bg-zinc-50" },
  };

export default function ArtifactCards({
  artifacts,
}: {
  artifacts: ArtifactRef[];
}) {
  if (!artifacts?.length) return null;
  return (
    <div className="my-2 space-y-1.5" data-testid="artifact-cards">
      {artifacts.map((a, i) => {
        const meta = KIND_META[a.kind] || KIND_META.data;
        return (
          <div
            key={a.id || i}
            className={`flex items-center gap-3 rounded-xl border px-3 py-2 ${meta.tone}`}
          >
            {a.kind === "image" && a.url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={a.url}
                alt={a.title}
                className="h-14 w-24 shrink-0 rounded-lg border border-white object-cover shadow-sm"
              />
            ) : (
              <span className="text-xl">{meta.icon}</span>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium text-zinc-700">
                {a.title || meta.label}
              </p>
              <p className="text-[11px] text-zinc-500">
                {meta.label}
                {a.tool ? ` · via ${a.tool}` : ""}
                {a.size_bytes ? ` · ${(a.size_bytes / 1024).toFixed(0)} KB` : ""}
              </p>
            </div>
            <a
              href={a.url}
              target="_blank"
              rel="noreferrer"
              className="shrink-0 rounded-lg border border-zinc-300 bg-white px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
            >
              Buka / unduh ↗
            </a>
          </div>
        );
      })}
    </div>
  );
}
