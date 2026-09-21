import type { Metadata } from "next";
import AuthGate from "@/components/AuthGate";
import InternshipConsole from "@/components/internship/InternshipConsole";

export const metadata: Metadata = {
  title: "Proyek Internship — Ask Anything",
  description:
    "Papan proyek AI chatbot + agent + RAG dari nol untuk anak internship: rencana INT-NNN dari slide rag-agent, materi 01–06, dan task yang ditugaskan ke tiap peserta.",
};

export default function InternshipPage() {
  return (
    <AuthGate>
      <InternshipConsole />
    </AuthGate>
  );
}
