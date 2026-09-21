import type { Metadata } from "next";
import { Suspense } from "react";
import LoginForm from "@/components/LoginForm";

export const metadata: Metadata = {
  title: "Masuk — Ask Anything",
  description:
    "Halaman masuk: role admin mengelola pipeline, member memakai playground dengan model OpenAI.",
};

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="grid min-h-screen place-items-center bg-[#f7f7f8] text-sm text-zinc-400">
          Memuat…
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
