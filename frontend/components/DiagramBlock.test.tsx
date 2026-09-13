import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor , cleanup } from "@testing-library/react";
import { useEffect } from "react";

/* Mermaid asli berat & butuh DOM lengkap; untuk test mode kita mock:
   sumber berisi "!!broken" dianggap gagal render seperti mermaid sungguhan. */
vi.mock("./Mermaid", () => ({
  default: function MockMermaid(props: {
    source: string;
    onError?: (m: string | null) => void;
  }) {
    useEffect(() => {
      if (props.source.includes("!!broken")) {
        props.onError?.("Parse error on line 2: expected END");
      } else {
        props.onError?.(null);
      }
    }, [props.source]);
    return <div data-testid="mermaid-legacy">{props.source}</div>;
  },
}));

import DiagramBlock from "./DiagramBlock";

afterEach(cleanup);

const OK_SRC = ["flowchart TD", "A[Mulai] --> B[Selesai]"].join("\n");
const BAD_SRC = [
  "flowchart TD",
  "A[Mulai] --> B[Proses",
  "B --> C{Cek}",
  "ini bukan baris mermaid",
  'E["catatan !!broken"] --> C',
].join("\n");

beforeEach(() => {
  window.localStorage.clear();
});

describe("DiagramBlock — mode render", () => {
  it("default = mode graph interaktif", async () => {
    render(<DiagramBlock source={OK_SRC} />);
    expect(await screen.findByTestId("graph-node-A")).toBeTruthy();
    expect(screen.getByTestId("mode-graph").getAttribute("aria-checked")).toBe("true");
    expect(screen.queryByTestId("mermaid-legacy")).toBeNull();
  });

  it("preferensi tersimpan di localStorage dan dibaca ulang", async () => {
    window.localStorage.setItem("aa:diagram-mode", "mermaid");
    render(<DiagramBlock source={OK_SRC} />);
    expect(await screen.findByTestId("mermaid-legacy")).toBeTruthy();
    expect(screen.queryByTestId("graph-node-A")).toBeNull();
  });

  it("toggle Graph → Mermaid → Graph bekerja dan menyimpan preferensi", async () => {
    render(<DiagramBlock source={OK_SRC} />);
    await screen.findByTestId("graph-node-A");
    fireEvent.click(screen.getByTestId("mode-mermaid"));
    expect(screen.getByTestId("mermaid-legacy")).toBeTruthy();
    expect(window.localStorage.getItem("aa:diagram-mode")).toBe("mermaid");
    fireEvent.click(screen.getByTestId("mode-graph"));
    expect(await screen.findByTestId("graph-node-A")).toBeTruthy();
    expect(window.localStorage.getItem("aa:diagram-mode")).toBe("graph");
  });

  it("mermaid rusak tetap dirender sebagai graph + badge baris dilewati", async () => {
    render(<DiagramBlock source={BAD_SRC} />);
    expect(await screen.findByTestId("graph-node-A")).toBeTruthy();
    expect(screen.getByTitle(/Baris yang dilewati parser/)).toBeTruthy();
  });

  it("saat Mermaid error muncul tombol fallback ke mode graph", async () => {
    window.localStorage.setItem("aa:diagram-mode", "mermaid");
    render(<DiagramBlock source={BAD_SRC} />);
    await screen.findByTestId("mermaid-legacy");
    expect(await screen.findByText(/Mermaid gagal dirender/)).toBeTruthy();
    fireEvent.click(screen.getByTestId("fallback-to-graph"));
    await waitFor(() => expect(screen.getByTestId("graph-node-A")).toBeTruthy());
    expect(window.localStorage.getItem("aa:diagram-mode")).toBe("graph");
  });

  it("sumber tanpa node menampilkan sumber apa adanya (tidak crash)", async () => {
    render(<DiagramBlock source={"hanya prosa tanpa graph"} />);
    await waitFor(() =>
      expect(screen.getByText(/tidak mengandung node/)).toBeTruthy(),
    );
  });
});
