import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import FeedbackButtons from "./FeedbackButtons";

vi.mock("@/lib/api", () => ({
  sendFeedback: vi.fn().mockResolvedValue({
    feedback: { id: "f1", rating: "down" },
    auto_guidance: true,
  }),
}));

import { sendFeedback } from "@/lib/api";

afterEach(cleanup);

describe("FeedbackButtons (👍/👎 di ruang chat)", () => {
  it("tidak merender apa pun tanpa message id", () => {
    const { container } = render(
      <FeedbackButtons conversationId="c1" messageId="" />
    );
    expect(container.firstChild).toBeNull();
  });

  it("👍 langsung terkirim dengan conversation & message id", async () => {
    render(<FeedbackButtons conversationId="c1" messageId="m1" />);
    fireEvent.click(screen.getByTitle("Jawaban membantu"));
    await waitFor(() =>
      expect(sendFeedback).toHaveBeenCalledWith({
        rating: "up",
        conversation_id: "c1",
        message_id: "m1",
        comment: undefined,
      })
    );
    expect(await screen.findByText(/Masukan tercatat/)).toBeTruthy();
  });

  it("👎 tanpa komentar memunculkan kolom komentar dulu, kirim menyusul", async () => {
    render(<FeedbackButtons conversationId="c1" messageId="m1" />);
    fireEvent.click(screen.getByTitle("Jawaban kurang tepat"));
    // kolom komentar muncul, belum ada POST
    expect(sendFeedback).not.toHaveBeenCalled();
    fireEvent.change(
      screen.getByPlaceholderText(/terlalu panjang/i),
      { target: { value: "terlalu bertele-tele" } }
    );
    fireEvent.click(screen.getByText("Kirim masukan"));
    await waitFor(() =>
      expect(sendFeedback).toHaveBeenCalledWith({
        rating: "down",
        conversation_id: "c1",
        message_id: "m1",
        comment: "terlalu bertele-tele",
      })
    );
  });
});
