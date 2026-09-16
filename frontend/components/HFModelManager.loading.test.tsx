import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import HFModelManager from "./HFModelManager";
import type { EngineStatus, HFModelsResponse, SettingsInfo } from "@/lib/types";

const api = vi.hoisted(() => ({
  listHFModels: vi.fn(),
  searchHFModels: vi.fn(),
  downloadHFModel: vi.fn(),
  cancelHFDownload: vi.fn(),
  deleteHFModel: vi.fn(),
  useHFModel: vi.fn(),
  loadHFModelFromPath: vi.fn(),
  stopHFEngine: vi.fn(),
  updateSettings: vi.fn(),
}));

vi.mock("@/lib/api", () => api);

const engine = (over: Partial<EngineStatus> = {}): EngineStatus => ({
  state: "idle",
  running: false,
  available: true,
  model_path: null,
  repo_id: null,
  model_label: null,
  device: "cpu",
  dtype: null,
  params: null,
  max_position: 0,
  loaded_at: null,
  generating: false,
  error: null,
  hint: null,
  install_hint: null,
  ...over,
});

function baseResponse(over: Partial<HFModelsResponse> = {}): HFModelsResponse {
  return {
    models_dir: "models",
    endpoint: "https://huggingface.co",
    models: [],
    downloads: [],
    engine: engine(),
    deps: { available: true, torch: "2", transformers: "5", device: "cpu", install_hint: null },
    active: { provider: "huggingface", hf_mode: "local", hf_model: "", thinking: true },
    ...over,
  };
}

function renderMgr() {
  return render(
    <HFModelManager settings={null as unknown as SettingsInfo} onSaved={vi.fn()} />
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("HFModelManager — loading screen", () => {
  it("spinner 'Memuat model & status engine' sampai data pertama tiba", async () => {
    api.listHFModels.mockImplementation(() => new Promise(() => {}));
    renderMgr();
    expect(screen.getByText(/Memuat model/)).toBeTruthy();
  });

  it("kartu 'Memuat model ke memori' saat engine sedang loading", async () => {
    api.listHFModels.mockResolvedValue(
      baseResponse({
        engine: engine({ state: "loading", model_label: "Qwen/Qwen2.5-0.5B-Instruct" }),
      })
    );
    renderMgr();
    const card = await screen.findByTestId("model-loading-card");
    expect(card.textContent).toContain("Memuat Qwen/Qwen2.5-0.5B-Instruct ke memori");
  });

  it("form 'Muat model dari folder' memanggil endpoint /hf/models/load", async () => {
    api.listHFModels.mockResolvedValue(baseResponse());
    api.loadHFModelFromPath.mockResolvedValue({ ok: true });
    renderMgr();
    await screen.findByText(/Muat model dari folder/);
    const input = screen.getByPlaceholderText(/~/) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "~/models/Qwen/Qwen2.5-0.5B-Instruct" } });
    fireEvent.click(screen.getByRole("button", { name: "Muat" }));
    await waitFor(() =>
      expect(api.loadHFModelFromPath).toHaveBeenCalledWith(
        "~/models/Qwen/Qwen2.5-0.5B-Instruct",
        expect.objectContaining({ thinking: true })
      )
    );
  });
});
