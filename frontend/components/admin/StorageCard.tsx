"use client";
/* Kartu "Penyimpanan data" di Ringkasan Admin.

   Menjawab satu pertanyaan yang sebelumnya cuma bisa dijawab lewat SSH:
   apakah database (akun, password hasil reset, task, chat) benar-benar
   mendarat di disk server, atau cuma di lapisan tulis container yang terhapus
   setiap redeploy. `boots` yang naik tiap deploy = bukti data selamat. */
import { useCallback, useEffect, useState } from "react";
import { adminBackupNow, adminStorage } from "@/lib/api";
import type { StorageBackup, StorageStatus } from "@/lib/types";
import { Card, fmtBytes } from "./ui";

function tone(status: StorageStatus | null) {
  if (!status) return "zinc";
  if (!status.writable || status.persistent === false) return "red";
  if (status.persistent === null) return "amber";
  return "green";
}

const BADGE: Record<string, string> = {
  green: "border-emerald-200 bg-emerald-50 text-emerald-700",
  amber: "border-amber-200 bg-amber-50 text-amber-700",
  red: "border-red-200 bg-red-50 text-red-700",
  zinc: "border-zinc-200 bg-zinc-50 text-zinc-500",
};

function label(status: StorageStatus | null) {
  if (!status) return "memuat…";
  if (!status.writable) return "tidak bisa ditulis";
  if (status.persistent === false) return "TIDAK persisten";
  if (status.persistent === null) return "tidak bisa dipastikan";
  return "persisten";
}

export default function StorageCard() {
  const [status, setStatus] = useState<StorageStatus | null>(null);
  const [backups, setBackups] = useState<StorageBackup[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const out = await adminStorage("");
      setStatus(out.storage);
      setBackups(out.backups);
    } catch (e) {
      setNote(String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const backup = async () => {
    setBusy(true);
    setNote(null);
    try {
      const out = await adminBackupNow("");
      setBackups(out.backups);
      setNote(`Backup dibuat: ${out.backup}`);
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  };

  const t = tone(status);

  return (
    <Card
      title="Penyimpanan data"
      subtitle="Database, artifact, arsip RAG, dan model — semuanya di satu direktori data."
      right={
        <span
          className={`rounded-lg border px-2.5 py-1 text-xs font-medium ${BADGE[t]}`}
          title="Persisten = direktori data adalah mount disk server, bukan lapisan container"
        >
          {label(status)}
        </span>
      }
    >
      {status?.warning && (
        <p className="mb-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[12.5px] text-red-700">
          {status.warning}
        </p>
      )}

      <dl className="grid grid-cols-1 gap-x-4 gap-y-1.5 text-[12.5px] sm:grid-cols-2">
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-zinc-500">Direktori data</dt>
          <dd className="min-w-0 break-all font-mono text-zinc-700">
            {status?.data_dir ?? "—"}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-zinc-500">Sumber mount</dt>
          <dd className="min-w-0 break-all font-mono text-zinc-700">
            {status?.mount_source || (status?.in_container ? "—" : "disk lokal")}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-zinc-500">Database</dt>
          <dd className="min-w-0 break-all text-zinc-700">
            {fmtBytes(status?.db_bytes ?? 0)}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-zinc-500">Sisa disk</dt>
          <dd className="text-zinc-700">
            {status?.free_bytes != null ? fmtBytes(status.free_bytes) : "—"}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-zinc-500">Start ke-</dt>
          <dd className="text-zinc-700">
            {status?.boots ?? "—"}
            <span className="ml-1 text-zinc-400">
              (naik tiap redeploy bila data tersimpan)
            </span>
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-zinc-500">Backup</dt>
          <dd className="text-zinc-700">
            {backups.length} salinan
            {backups[0] && (
              <span className="ml-1 text-zinc-400">
                · terbaru {new Date(backups[0].mtime * 1000).toLocaleString("id-ID")}
              </span>
            )}
          </dd>
        </div>
      </dl>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          onClick={backup}
          disabled={busy}
          className="rounded-lg border border-zinc-200 px-2.5 py-1 text-[12px] text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
        >
          {busy ? "Membuat backup…" : "Backup sekarang"}
        </button>
        <button
          onClick={load}
          className="rounded-lg border border-zinc-200 px-2.5 py-1 text-[12px] text-zinc-600 hover:bg-zinc-50"
        >
          Muat ulang
        </button>
        {note && <span className="text-[12px] text-zinc-500">{note}</span>}
      </div>
    </Card>
  );
}
