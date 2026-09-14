import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import Sidebar from "./Sidebar";
import type { Conversation } from "@/lib/types";

const DAY = 86400;
const now = () => Date.now() / 1000;

const CONV: Conversation[] = [
  { id: "a", title: "Rangkum AI", created_at: now(), updated_at: now() },
  { id: "b", title: "Diagram DNS", created_at: now() - 3 * DAY, updated_at: now() - 3 * DAY },
];

function setup(over: Partial<React.ComponentProps<typeof Sidebar>> = {}) {
  const props = {
    conversations: CONV,
    activeId: "a",
    onSelect: vi.fn(),
    onNew: vi.fn(),
    onSettings: vi.fn(),
    llmReachable: true,
    ...over,
  };
  return { ...props, ...{ ui: render(<Sidebar {...props} />) } };
}

afterEach(cleanup);
beforeEach(() => window.localStorage.clear());

describe("Sidebar — collapse / expand", () => {
  it("default: expanded, semua label terlihat", async () => {
    setup();
    await waitFor(() =>
      expect(screen.getByTestId("sidebar").getAttribute("data-collapsed")).toBe("false")
    );
    expect(screen.getByText("ask-anything")).toBeTruthy();
    expect(screen.getByText("New chat")).toBeTruthy();
    expect(screen.getByText("Rangkum AI")).toBeTruthy();
    expect(screen.getByText("LLM server terhubung")).toBeTruthy();
    expect(screen.getByTestId("sidebar-toggle").getAttribute("aria-expanded")).toBe("true");
  });

  it("tombol collapse menyembunyikan label & mengecilkan lebar", async () => {
    setup();
    const aside = screen.getByTestId("sidebar");
    fireEvent.click(screen.getByTestId("sidebar-toggle"));
    expect(aside.getAttribute("data-collapsed")).toBe("true");
    expect(aside.style.width).toBe("64px");
    expect(screen.queryByText("ask-anything")).toBeNull();
    expect(screen.queryByText("Rangkum AI")).toBeNull();
    expect(screen.queryByText("LLM server terhubung")).toBeNull();
    expect(screen.getByTestId("sidebar-toggle").getAttribute("aria-expanded")).toBe("false");
  });

  it("lebar expand jauh lebih besar dari rail (ruang chat ikut meluas)", async () => {
    setup();
    const aside = screen.getByTestId("sidebar");
    expect(aside.style.width).toBe("268px");
    fireEvent.click(screen.getByTestId("sidebar-toggle"));
    expect(parseInt(aside.style.width, 10)).toBeLessThan(100);
  });

  it("keadaan collapsed dipertahankan antar-render via localStorage", async () => {
    setup();
    fireEvent.click(screen.getByTestId("sidebar-toggle"));
    expect(window.localStorage.getItem("aa:nav-collapsed")).toBe("1");
    cleanup();

    setup();
    await waitFor(() =>
      expect(screen.getByTestId("sidebar").getAttribute("data-collapsed")).toBe("true")
    );
  });

  it(" collapsed: riwayat tetap bisa dipilih lewat ikon, dan expand mengembalikan label", async () => {
    setup();
    fireEvent.click(screen.getByTestId("sidebar-toggle"));
    fireEvent.click(screen.getByLabelText("Buka percakapan: Diagram DNS"));

    fireEvent.click(screen.getByTestId("sidebar-toggle"));
    await waitFor(() => expect(screen.getByText("Diagram DNS")).toBeTruthy());
  });

  it("collapsed: New chat & Settings tetap berfungsi (ikon)", async () => {
    const { onNew, onSettings } = setup();
    fireEvent.click(screen.getByTestId("sidebar-toggle"));
    fireEvent.click(screen.getByTestId("nav-new-chat"));
    fireEvent.click(screen.getByTestId("nav-settings"));
    expect(onNew).toHaveBeenCalledTimes(1);
    expect(onSettings).toHaveBeenCalledTimes(1);
  });

  it("pintasan Ctrl+B menoggle, dan Escape bukan milik navbar", async () => {
    setup();
    fireEvent.keyDown(window, { key: "b", ctrlKey: true });
    await waitFor(() =>
      expect(screen.getByTestId("sidebar").getAttribute("data-collapsed")).toBe("true")
    );
    fireEvent.keyDown(window, { key: "b", ctrlKey: true });
    await waitFor(() =>
      expect(screen.getByTestId("sidebar").getAttribute("data-collapsed")).toBe("false")
    );
  });

  it("status LLM offline tetap terlihat sebagai titik merah saat collapsed", async () => {
    setup({ llmReachable: false });
    fireEvent.click(screen.getByTestId("sidebar-toggle"));
    const dot = screen.getByTestId("llm-status-dot");
    expect(dot.className).toContain("bg-red-400");
    expect(dot.parentElement?.getAttribute("title")).toBe("LLM server offline");
  });
});
