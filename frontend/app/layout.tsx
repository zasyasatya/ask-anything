import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ask Anything — Agentic AI Chatbot",
  description:
    "AI agent dengan browsing, diagram alir & graph, plus mechanistic interpreter. HuggingFace lokal + OpenAI API.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className="font-sans">{children}</body>
    </html>
  );
}
