import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "Ask Anything — Agentic AI Chatbot",
  description:
    "AI agent dengan browsing, diagram alir & graph, plus mechanistic interpreter. HuggingFace lokal + OpenAI API.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className="font-sans">
        {/* Sesi login tersedia untuk semua halaman (halaman /login pun butuh
            tahu mode auth yang aktif). */}
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
