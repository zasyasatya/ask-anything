import type { Metadata } from "next";
import AuthGate from "@/components/AuthGate";
import AdminConsole from "@/components/admin/AdminConsole";

export const metadata: Metadata = {
  title: "Admin — Ask Anything",
  description:
    "Konsol admin pipeline: mode & tool, memori, artifact, feedback, RAG, mechanistic interpreter.",
};

export default function AdminPage() {
  return (
    <AuthGate requireAdmin>
      <AdminConsole />
    </AuthGate>
  );
}
