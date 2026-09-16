import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { AppSplash, ThinkingIndicator } from "./LoadingScreen";

afterEach(cleanup);

describe("AppSplash — loading screen startup", () => {
  it("menampilkan spinner + status saat data belum dimuat", () => {
    render(<AppSplash />);
    expect(screen.getByTestId("app-splash")).toBeTruthy();
    expect(screen.getByText(/Menyiapkan Ask Anything/)).toBeTruthy();
  });

  it("menampilkan error + tombol retry bila backend mati", () => {
    const onRetry = vi.fn();
    render(<AppSplash error="chat → HTTP 500" onRetry={onRetry} />);
    expect(screen.getByText(/Backend tidak bisa dihubungi/)).toBeTruthy();
    const btn = screen.getByRole("button", { name: /Coba lagi/ });
    fireEvent.click(btn);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("tanpa error tidak ada tombol retry", () => {
    render(<AppSplash />);
    expect(
      screen.queryByRole("button", { name: /Coba lagi/ })
    ).toBeNull();
  });
});

describe("ThinkingIndicator — status sebelum token pertama", () => {
  it("menampilkan label 'Model sedang berpikir'", () => {
    render(<ThinkingIndicator />);
    expect(screen.getByText(/Model sedang berpikir/)).toBeTruthy();
  });
});
