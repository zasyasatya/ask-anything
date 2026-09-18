import type { Metadata } from "next";
import TasksConsole from "@/components/tasks/TasksConsole";

export const metadata: Metadata = {
  title: "Task Management — Ask Anything",
  description:
    "Papan kerja developer: seluruh task rencana RAG & platform, dengan id task ASK-NNN yang dipakai sebagai nama branch GitLab, sinkronisasi git, checklist, dan komentar.",
};

export default function TasksPage() {
  return <TasksConsole />;
}
