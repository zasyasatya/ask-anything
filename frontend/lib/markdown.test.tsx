import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import Markdown from "./markdown";

vi.mock("@/components/DiagramBlock", () => ({
  default: ({ source, provenance }: { source: string; provenance: unknown }) => (
    <div data-testid="diagram" data-provenance={JSON.stringify(provenance ?? null)}>
      {source}
    </div>
  ),
}));

afterEach(cleanup);

const SRC = [
  { index: 1, url: "https://a.test/1", title: "Sumber Satu", tool: "web_search", origin: "browser", snippet: "", read: false, cited: true },
  { index: 2, url: "https://b.test/2", title: "Sumber Dua", tool: "fetch_url", origin: "browser", snippet: "", read: true, cited: false },
];

describe("Markdown — marker sitasi jadi tautan", () => {
  it("[1] berubah jadi chip yang menunjuk URL sumber", () => {
    render(<Markdown text="Harga naik [1] tahun ini." sources={SRC} />);
    const link = screen.getByTitle(/Sumber Satu/);
    expect(link.getAttribute("href")).toBe("https://a.test/1");
    expect(link.textContent).toContain("1");
  });

  it("beberapa nomor dalam satu tanda kurung ikut ditautkan", () => {
    render(<Markdown text="Klaim [1, 2] didukung." sources={SRC} />);
    expect(screen.getAllByRole("link")).toHaveLength(2);
  });

  it("nomor di luar daftar ditandai merah, tidak dihapus", () => {
    const { container } = render(<Markdown text="Klaim [7] tanpa dasar." sources={SRC} />);
    expect(container.textContent).toContain("7");
    expect(screen.getByTitle("Nomor sitasi tidak ada di daftar sumber")).toBeTruthy();
  });

  it("tanpa daftar sumber, marker tetap tampil (jujur, tidak hilang)", () => {
    const { container } = render(<Markdown text="Klaim [1] tanpa sumber." />);
    expect(container.textContent).toContain("[1]");
  });

  it("link markdown biasa tetap ditautkan apa adanya", () => {
    render(<Markdown text="lihat [dokumentasi](https://d.test/x)" sources={SRC} />);
    expect(screen.getByRole("link").getAttribute("href")).toBe("https://d.test/x");
  });
});

describe("Markdown — provenance diagram diteruskan", () => {
  it("fence mermaid menerima provenance dari tool", () => {
    render(
      <Markdown
        text={"```mermaid\nflowchart TD\nA-->B\n```"}
        diagramOrigin={{ tool: "create_diagram", titles: ["Alur"] }}
      />
    );
    const d = screen.getByTestId("diagram");
    expect(JSON.parse(d.getAttribute("data-provenance") || "null")).toEqual({
      tool: "create_diagram",
      titles: ["Alur"],
    });
  });

  it("blok kode non-mermaid tidak jadi diagram", () => {
    const { container } = render(<Markdown text={"```bash\nnpm test\n```"} />);
    expect(screen.queryByTestId("diagram")).toBeNull();
    expect(container.textContent).toContain("npm test");
  });
});
