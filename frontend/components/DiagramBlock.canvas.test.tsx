import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import DiagramBlock from "./DiagramBlock";

vi.mock("./Mermaid", () => ({
  default: () => <div data-testid="mermaid-legacy" />,
}));

const SRC = ["flowchart TD", 'A["Mulai"] --> B["Selesai"]'].join("\n");

afterEach(cleanup);
beforeEach(() => window.localStorage.clear());

describe("DiagramBlock — kanvas lebar & layar penuh", () => {
  it("kartu memakai tinggi fleksibel berbasis viewport (bukan 460px mati)", async () => {
    const { container } = render(<DiagramBlock source={SRC} />);
    const card = container.querySelector("[data-testid='diagram-card']") as HTMLElement;
    expect(card).toBeTruthy();
    expect(card.style.height).toContain("clamp(420px, 68vh, 760px)");
    expect(card.style.minHeight).toBe("380px");
    await screen.findByTestId("graph-canvas");
  });

  it("toolbar & kanvas tersusun vertikal — kanvas tidak terjepit di samping tombol", async () => {
    const { container } = render(<DiagramBlock source={SRC} />);
    await screen.findByTestId("graph-canvas");
    const card = container.querySelector("[data-testid='diagram-card']") as HTMLElement;
    // kartu tanpa `flex-col` menempatkan header + kanvas berdampingan (flex row),
    // dan kanvas menyusut jadi kolom sempit.
    expect(card.className).toContain("flex-col");
    const wrap = screen.getByTestId("diagram-canvas");
    expect(wrap.className).toContain("flex-1");
    expect(wrap.className).toContain("min-h-0");
    expect(wrap.contains(screen.getByTestId("graph-canvas"))).toBe(true);
  });

  it("ada tombol layar penuh dengan aria-pressed", async () => {
    render(<DiagramBlock source={SRC} />);
    await screen.findByTestId("graph-node-A");
    const btn = screen.getByTestId("diagram-fullscreen");
    expect(btn.getAttribute("aria-pressed")).toBe("false");
    expect(btn.textContent).toContain("Layar penuh");
  });

  it("tanpa Fullscreen API: fallback focus mode, tetap fullscreen secara visual", async () => {
    // jsdom tidak punya requestFullscreen → jalur fallback diuji apa adanya.
    render(<DiagramBlock source={SRC} />);
    await screen.findByTestId("graph-node-A");
    fireEvent.click(screen.getByTestId("diagram-fullscreen"));
    const card = screen.getByTestId("diagram-card");
    await waitFor(() => expect(card.getAttribute("data-fullscreen")).toBe("true"));
    expect(card.className).toContain("fixed");
    expect(card.className).toContain("inset-0");
    expect(card.className).toContain("z-50");
    expect(screen.getByText(/focus mode/)).toBeTruthy();
    expect(screen.getByTestId("diagram-fullscreen").getAttribute("aria-pressed")).toBe("true");
  });

  it("Esc keluar dari focus mode", async () => {
    render(<DiagramBlock source={SRC} />);
    await screen.findByTestId("graph-node-A");
    fireEvent.click(screen.getByTestId("diagram-fullscreen"));
    await waitFor(() =>
      expect(screen.getByTestId("diagram-card").getAttribute("data-fullscreen")).toBe("true")
    );
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() =>
      expect(screen.getByTestId("diagram-card").getAttribute("data-fullscreen")).toBe("false")
    );
  });

  it("saat fullscreen native tersedia, dipakai (bukan fallback)", async () => {
    const req = vi.fn(function (this: HTMLElement) {
      Object.defineProperty(document, "fullscreenElement", {
        value: this, configurable: true,
      });
      return Promise.resolve();
    });
    const exit = vi.fn(() => {
      Object.defineProperty(document, "fullscreenElement", {
        value: null, configurable: true,
      });
      return Promise.resolve();
    });
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", { value: req, configurable: true });
    Object.defineProperty(document, "exitFullscreen", { value: exit, configurable: true });

    render(<DiagramBlock source={SRC} />);
    await screen.findByTestId("graph-node-A");
    fireEvent.click(screen.getByTestId("diagram-fullscreen"));

    // tunggu flush state (promise .then di luar act) SEBELUM menekan Esc,
    // kalau tidak listener keydown belum terpasang.
    await waitFor(() =>
      expect(screen.getByTestId("diagram-card").getAttribute("data-fullscreen")).toBe("true")
    );
    expect(req).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/fullscreen native/)).toBeTruthy();

    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(exit).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByTestId("diagram-card").getAttribute("data-fullscreen")).toBe("false")
    );
    delete (HTMLElement.prototype as unknown as Record<string, unknown>).requestFullscreen;
  });

  it("payload ditolak browser (mis. iframe tanpa allow) → tetap focus mode + alasan", async () => {
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
      value: () => Promise.reject(new Error("Blocked by iframe policy")),
      configurable: true,
    });
    render(<DiagramBlock source={SRC} />);
    await screen.findByTestId("graph-node-A");
    fireEvent.click(screen.getByTestId("diagram-fullscreen"));
    await waitFor(() =>
      expect(screen.getByTestId("diagram-card").getAttribute("data-fullscreen")).toBe("true")
    );
    expect(screen.getByText(/Blocked by iframe policy/)).toBeTruthy();
    delete (HTMLElement.prototype as unknown as Record<string, unknown>).requestFullscreen;
  });
});

describe("DiagramBlock — badge provenance", () => {
  it("diagram dari tool create_diagram diberi label eksplisit", async () => {
    render(
      <DiagramBlock
        source={SRC}
        provenance={{ tool: "create_diagram", titles: ["Alur"] }}
      />
    );
    const badge = await screen.findByTestId("diagram-provenance");
    expect(badge.textContent).toContain("dari tool create_diagram");
    expect(badge.title).toContain("Bukan sumber web");
  });

  it("tanpa provenance: jujur menyebut ditulis model di jawaban", async () => {
    render(<DiagramBlock source={SRC} />);
    const badge = await screen.findByTestId("diagram-provenance");
    expect(badge.textContent).toContain("ditulis model di jawaban");
    expect(badge.title).toContain("Tidak bisa disitasi");
  });
});
