import type { Metadata } from "next";
import { Suspense } from "react";
import AuthGate from "@/components/AuthGate";
import TasksConsole from "@/components/tasks/TasksConsole";

export const metadata: Metadata = {
  title: "Task Management — Ask Anything",
  description:
    "Papan kerja developer: seluruh task rencana RAG & platform, dengan id task ASK-NNN yang dipakai sebagai nama branch GitLab, sinkronisasi git, checklist, dan komentar.",
};

export default function TasksPage() {
  return (
    <AuthGate>
      <Suspense
        fallback={
          <div className="grid min-h-screen place-items-center bg-[#f7f7f8] text-sm text-zinc-400">
            Memuat papan…
          </div>
        }
      >
        <TasksConsole />
      </Suspense>
    </AuthGate>
  );
}
