import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen , cleanup } from "@testing-library/react";
import GraphView from "./GraphView";
import { parseMermaid } from "@/lib/graph/parseMermaid";

afterEach(cleanup);

const SRC = [
  "flowchart TD",
  'A["Pertanyaan user"] --> B[Reasoning]',
  "B -->|butuh fakta| C[web_search]",
  "C --> D[create_diagram]",
  "B --> D",
].join("\n");

const model = () => parseMermaid(SRC);

function worldTransform(el: HTMLElement): { x: number; y: number; k: number } {
  const m = /translate\(([-\d.]+)px, ([-\d.]+)px\) scale\(([-\d.]+)\)/.exec(
    el.style.transform,
  );
  return { x: Number(m?.[1]), y: Number(m?.[2]), k: Number(m?.[3]) };
}

describe("GraphView", () => {
  it("merender semua node sebagai elemen interaktif", () => {
    render(<GraphView model={model()} />);
    for (const id of ["A", "B", "C", "D"]) {
      const node = screen.getByTestId(`graph-node-${id}`);
      expect(node.tagName).toBe("BUTTON");
    }
    expect(screen.getByTestId("graph-node-A")).toHaveProperty("tabIndex", 0);
  });

  it("klik node membuka inspektur relasi", () => {
    render(<GraphView model={model()} />);
    expect(screen.queryByTestId("graph-inspector")).toBeNull();
    const b = screen.getByTestId("graph-node-B");
    fireEvent.pointerDown(b, { button: 0, clientX: 10, clientY: 10, pointerId: 1 });
    fireEvent.pointerUp(screen.getByTestId("graph-canvas"), { pointerId: 1 });
    const inspector = screen.getByTestId("graph-inspector");
    expect(inspector.textContent).toContain("Reasoning");
    expect(inspector.textContent).toContain("web_search");
  });

  it("klik latar menutup inspektur", () => {
    render(<GraphView model={model()} />);
    const b = screen.getByTestId("graph-node-B");
    fireEvent.pointerDown(b, { button: 0, clientX: 10, clientY: 10, pointerId: 1 });
    fireEvent.pointerUp(screen.getByTestId("graph-canvas"), { pointerId: 1 });
    expect(screen.getByTestId("graph-inspector")).toBeTruthy();
    const canvas = screen.getByTestId("graph-canvas");
    fireEvent.pointerDown(canvas, { button: 0, clientX: 300, clientY: 300, pointerId: 2 });
    fireEvent.pointerUp(canvas, { pointerId: 2 });
    expect(screen.queryByTestId("graph-inspector")).toBeNull();
  });

  it("tombol zoom mengubah skala world", () => {
    render(<GraphView model={model()} />);
    const world = screen.getByTestId("graph-world");
    const before = worldTransform(world).k;
    fireEvent.click(screen.getByLabelText("Perbesar"));
    const after = worldTransform(world).k;
    expect(after).toBeGreaterThan(before);
    fireEvent.click(screen.getByLabelText("Perkecil"));
    expect(worldTransform(world).k).toBeLessThan(after);
  });

  it("drag node memindahkan node tanpa mengubah zoom", () => {
    render(<GraphView model={model()} />);
    const node = screen.getByTestId("graph-node-C");
    const leftBefore = Number(node.style.left.replace("px", ""));
    fireEvent.pointerDown(node, { button: 0, clientX: 100, clientY: 100, pointerId: 3 });
    fireEvent.pointerMove(screen.getByTestId("graph-canvas"), { clientX: 160, clientY: 140, pointerId: 3 });
    fireEvent.pointerUp(screen.getByTestId("graph-canvas"), { pointerId: 3 });
    const leftAfter = Number(node.style.left.replace("px", ""));
    expect(leftAfter).not.toBe(leftBefore);
    // drag node = klik tidak terjadi (inspektur tidak terbuka karena bergerak)
    expect(screen.queryByTestId("graph-inspector")).toBeNull();
  });

  it("drag latar = pan (translasi berubah, skala tetap)", () => {
    render(<GraphView model={model()} />);
    const world = screen.getByTestId("graph-world");
    const canvas = screen.getByTestId("graph-canvas");
    const t0 = worldTransform(world);
    fireEvent.pointerDown(canvas, { button: 0, clientX: 200, clientY: 200, pointerId: 4 });
    fireEvent.pointerMove(canvas, { clientX: 260, clientY: 230, pointerId: 4 });
    fireEvent.pointerUp(canvas, { pointerId: 4 });
    const t1 = worldTransform(world);
    expect(t1.x).not.toBe(t0.x);
    expect(t1.k).toBe(t0.k);
  });

  it("toggle arah LR me-layout ulang", () => {
    render(<GraphView model={model()} />);
    const a = screen.getByTestId("graph-node-A");
    const d = screen.getByTestId("graph-node-D");
    const dyBefore = Number(d.style.top.replace("px", "")) - Number(a.style.top.replace("px", ""));
    fireEvent.click(screen.getByTitle("Kiri → kanan"));
    const dxAfter =
      Number(d.style.left.replace("px", "")) - Number(a.style.left.replace("px", ""));
    expect(dxAfter).toBeGreaterThan(0);
    expect(dyBefore).toBeGreaterThan(0);
  });

  it("wheel zoom tidak melempar dan mengubah skala", () => {
    render(<GraphView model={model()} />);
    const canvas = screen.getByTestId("graph-canvas");
    const world = screen.getByTestId("graph-world");
    const k0 = worldTransform(world).k;
    fireEvent.wheel(canvas, { deltaY: -240, clientX: 50, clientY: 50 });
    expect(worldTransform(world).k).not.toBe(k0);
  });

  it("keyboard: Enter memilih node, Escape menutup", () => {
    render(<GraphView model={model()} />);
    const b = screen.getByTestId("graph-node-B");
    fireEvent.keyDown(b, { key: "Enter" });
    fireEvent.click(b, { detail: 0 }); // klik sintetis keyboard
    expect(screen.getByTestId("graph-inspector")).toBeTruthy();
    fireEvent.keyDown(screen.getByTestId("graph-canvas"), { key: "Escape" });
    expect(screen.queryByTestId("graph-inspector")).toBeNull();
  });

  it("model kosong menampilkan pesan, bukan crash", () => {
    const spy = vi.fn();
    render(
      <GraphView model={parseMermaid("%% hanya komentar\nstyle A fill:#f00")} onNodeCount={spy} />,
    );
    expect(screen.getByText(/Tidak ada node/)).toBeTruthy();
    expect(spy).toHaveBeenCalledWith(0);
  });
});

/* ---------------------------------------------------------------------------
   Proporsi kanvas: mode auto memilih arah yang paling mengisi kanvas, dan
   skala fit punya lantai baca. jsdom tidak punya layout, jadi ukuran container
   di-stub seperti kanvas nyata (lebar besar, tinggi sedang).
   --------------------------------------------------------------------------- */
function stubCanvas(width: number, height: number) {
  class FakeRO {
    constructor(private cb: () => void) {}
    observe() {
      this.cb();
    }
    unobserve() {}
    disconnect() {}
  }
  (globalThis as unknown as Record<string, unknown>).ResizeObserver = FakeRO;
  Object.defineProperty(HTMLElement.prototype, "clientWidth", {
    configurable: true,
    get: () => width,
  });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", {
    configurable: true,
    get: () => height,
  });
}

function clearCanvasStub() {
  delete (globalThis as unknown as Record<string, unknown>).ResizeObserver;
  delete (HTMLElement.prototype as unknown as Record<string, unknown>).clientWidth;
  delete (HTMLElement.prototype as unknown as Record<string, unknown>).clientHeight;
}

const LONG_CHAIN = parseMermaid(
  ["flowchart TD", ...Array.from({ length: 9 }, (_, i) => `N${i}[langkah ${i}] --> N${i + 1}[langkah ${i + 1}]`)].join(
    "\n",
  ),
);

const left = (id: string) => Number(screen.getByTestId(`graph-node-${id}`).style.left.replace("px", ""));
const top = (id: string) => Number(screen.getByTestId(`graph-node-${id}`).style.top.replace("px", ""));

describe("GraphView — proporsi kanvas", () => {
  afterEach(clearCanvasStub);

  it("rantai panjang di kanvas lebar diputar otomatis ke LR (tidak jadi garis tipis)", () => {
    stubCanvas(1200, 420);
    render(<GraphView model={LONG_CHAIN} />);
    // arah LR: node terakhir bergeser ke kanan, bukan ke bawah
    expect(left("N9")).toBeGreaterThan(left("N0"));
    expect(top("N9")).toBeCloseTo(top("N0"), 0);
    expect(screen.getByTestId("dir-auto").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("dir-auto").textContent).toContain("auto →");
  });

  it("arah dari sumber Mermaid tetap dipakai bila kanvasnya tinggi", () => {
    stubCanvas(520, 1200);
    render(<GraphView model={LONG_CHAIN} />);
    expect(top("N9")).toBeGreaterThan(top("N0"));
    expect(screen.getByTestId("dir-auto").textContent).toContain("auto ↓");
  });

  it("tombol TD/LR mengunci arah (auto dilepas)", () => {
    stubCanvas(1200, 420);
    render(<GraphView model={LONG_CHAIN} />);
    fireEvent.click(screen.getByTitle("Atas → bawah"));
    expect(top("N9")).toBeGreaterThan(top("N0"));
    expect(
      screen.getByTitle("Atas → bawah").getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("skala fit punya lantai baca dan statusnya dijelaskan", () => {
    stubCanvas(300, 240); // diagram 10 rank: fit ideal jauh di bawah 0.5
    render(<GraphView model={LONG_CHAIN} />);
    const k = Number(
      /scale\(([-\d.]+)\)/.exec(screen.getByTestId("graph-world").style.transform)?.[1],
    );
    expect(k).toBeGreaterThanOrEqual(0.5);
    expect(screen.getByTestId("graph-floored").textContent).toContain("terbaca");
  });
});
