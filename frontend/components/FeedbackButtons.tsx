"use client";
/* Tombol 👍/👎 di bawah jawaban assistant.
   Feedback terecord di backend (POST /api/feedback) lengkap dengan konteks run
   (mode, tool, cuplikan jawaban) dan — bila 👎 + komentar — otomatis menjadi
   pedoman perilaku yang di-inject ke system prompt run berikutnya. */
import { useState } from "react";
import { sendFeedback } from "@/lib/api";

type Sent = "idle" | "sending" | "sent" | "error";

export default function FeedbackButtons({
  conversationId,
  messageId,
  disabled,
}: {
  conversationId: string | null;
  messageId: string;
  disabled?: boolean;
}) {
  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [comment, setComment] = useState("");
  const [showComment, setShowComment] = useState(false);
  const [state, setState] = useState<Sent>("idle");

  if (!messageId || disabled) return null;

  async function submit(next: "up" | "down", withComment: boolean) {
    if (state === "sending" || state === "sent") return;
    setRating(next);
    if (next === "down" && !withComment && !comment.trim()) {
      setShowComment(true); // 👎 tanpa komentar → tawarkan kolom komentar dulu
      return;
    }
    setState("sending");
    try {
      await sendFeedback({
        rating: next,
        conversation_id: conversationId || undefined,
        message_id: messageId,
        comment: comment.trim() || undefined,
      });
      setState("sent");
      setShowComment(false);
    } catch {
      setState("error");
    }
  }

  return (
    <div className="mt-2.5" data-testid="feedback-buttons">
      {state === "sent" ? (
        <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700">
          ✓ Masukan tercatat{rating === "down" && comment.trim()
            ? " — jadi pedoman untuk jawaban berikutnya"
            : ""}
        </span>
      ) : (
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={() => submit("up", true)}
            title="Jawaban membantu"
            aria-label="Jawaban membantu"
            className={`rounded-lg border px-2 py-1 text-xs transition ${
              rating === "up"
                ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                : "border-zinc-200 bg-white text-zinc-400 hover:bg-zinc-50"
            }`}
          >
            👍
          </button>
          <button
            onClick={() => submit("down", false)}
            title="Jawaban kurang tepat"
            aria-label="Jawaban kurang tepat"
            className={`rounded-lg border px-2 py-1 text-xs transition ${
              rating === "down"
                ? "border-amber-300 bg-amber-50 text-amber-700"
                : "border-zinc-200 bg-white text-zinc-400 hover:bg-zinc-50"
            }`}
          >
            👎
          </button>
          {state === "error" && (
            <span className="text-[11px] text-red-600">
              gagal mengirim — coba lagi
            </span>
          )}
        </div>
      )}
      {showComment && state !== "sent" && (
        <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50/60 p-2.5">
          <label className="text-[12px] font-medium text-amber-800">
            Apa yang kurang? (opsional — membantu memperbaiki perilaku AI)
          </label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={2}
            placeholder="mis: terlalu panjang, tidak menjawab pertanyaan, sumber salah …"
            className="mt-1.5 w-full resize-none rounded-lg border border-amber-200 bg-white px-2.5 py-1.5 text-[13px] outline-none focus:border-amber-400"
          />
          <div className="mt-1.5 flex gap-1.5">
            <button
              onClick={() => submit("down", true)}
              className="rounded-lg bg-amber-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-amber-700"
            >
              Kirim masukan
            </button>
            <button
              onClick={() => {
                setShowComment(false);
                setState("idle");
                setRating(null);
              }}
              className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1 text-xs text-zinc-500 hover:bg-zinc-50"
            >
              Nanti saja
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
