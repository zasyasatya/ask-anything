"""Local HuggingFace inference — dijalankan dengan model sungguhan.

The Hub is not reachable from CI, so a *tiny but real* causal LM (2 layers,
19-token vocab) is built with `transformers` and saved to disk exactly like a
downloaded model would be. Everything after that — `engine.load`, the chat
template, `model.generate`, the `TextIteratorStreamer` thread bridge, the SSE
endpoint and the agent loop — is the production code path.
"""
import json

import pytest

from app import hf_hub
from app.config import settings
from app.local_inference import engine, extract_tool_calls, dependencies
from app.providers import HFLocalProvider, build_provider
from app.streamtags import TOOL_CALL_TAGS, THINK_TAGS, TagStreamParser

pytestmark = pytest.mark.skipif(
    not dependencies()["available"],
    reason="torch/transformers tidak ter-install (backend/requirements-local.txt)")

TAG_OPEN, TAG_CLOSE = TOOL_CALL_TAGS


@pytest.fixture(scope="module")
def tiny_model(tmp_path_factory):
    """Build a real (tiny) HF model folder: config + tokenizer + safetensors."""
    import torch
    from tokenizers import Tokenizer, decoders, pre_tokenizers
    from tokenizers.models import BPE
    from tokenizers.trainers import BpeTrainer
    from transformers import (LlamaConfig, LlamaForCausalLM,
                              PreTrainedTokenizerFast)

    path = tmp_path_factory.mktemp("tiny") / "ask-anything" / "TinyLlama-Test"
    path.mkdir(parents=True)

    # BPE byte-level: decode(encode(x)) == x persis, jadi tag tool call tidak
    # dirusak spasi (WordLevel menyisipkan spasi antar token).
    tok = Tokenizer(BPE(unk_token="[UNK]"))
    tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tok.decoder = decoders.ByteLevel()
    trainer = BpeTrainer(vocab_size=600,
                         special_tokens=["[UNK]", "[PAD]", "[BOS]", "[EOS]"])
    # Korpus harus memuat kata-kata yang dipakai tool call, kalau tidak semua
    # token jadi [UNK] (special → dibuang saat decode) dan teksnya hilang.
    tool_text = (f'{TAG_OPEN}{{"name": "web_search", '
                 f'"arguments": {{"query": "harga emas"}}}}{TAG_CLOSE}')
    tok.train_from_iterator(
        ["halo dunia apa kabar saya model kecil yang senang menjawab " * 30,
         "the quick brown fox jumps over the lazy dog and says hello " * 30,
         (tool_text + " ") * 20],
        trainer)
    fast = PreTrainedTokenizerFast(
        tokenizer_object=tok, unk_token="[UNK]", pad_token="[PAD]",
        bos_token="[BOS]", eos_token="[EOS]")
    fast.chat_template = (
        "{% for m in messages %}{{ m['role'] + ': ' + (m['content'] or '') + '\\n' }}"
        "{% endfor %}{% if add_generation_prompt %}assistant: {% endif %}")
    fast.save_pretrained(str(path))

    # Seed tetap: bobot (dan karena itu keluaran greedy) sama di setiap run,
    # supaya assert pada isi stream tidak jadi flaky antar mesin.
    torch.manual_seed(1234)
    cfg = LlamaConfig(vocab_size=len(fast), hidden_size=64,
                      intermediate_size=128, num_hidden_layers=2,
                      num_attention_heads=4, num_key_value_heads=2,
                      max_position_embeddings=512,
                      eos_token_id=fast.eos_token_id,
                      pad_token_id=fast.pad_token_id)
    LlamaForCausalLM(cfg).save_pretrained(str(path))
    (path / hf_hub.MANIFEST_NAME).write_text(json.dumps(
        {"repo_id": "ask-anything/TinyLlama-Test", "complete": True}))
    return path


@pytest.fixture()
async def loaded(tiny_model, monkeypatch):
    """Load the tiny model into the shared engine, unload it afterwards."""
    monkeypatch.setattr(settings, "provider", "huggingface")
    monkeypatch.setattr(settings, "hf_mode", "local")
    monkeypatch.setattr(settings, "hf_model", "ask-anything/TinyLlama-Test")
    monkeypatch.setattr(settings, "max_tokens", 8)
    monkeypatch.setattr(settings, "hf_dtype", "float32")
    await engine.load(tiny_model)
    yield engine
    await engine.unload()


# ---------------------------------------------------------------------------
# dependency report
# ---------------------------------------------------------------------------
def test_dependencies_are_reported():
    deps = dependencies()
    assert deps["available"] is True
    assert deps["torch"] and deps["transformers"]
    assert deps["device"] in ("cpu",) or deps["device"].startswith(("cuda", "mps"))


def test_status_is_actionable_when_nothing_is_loaded():
    st = engine.status()
    assert set(st) >= {"state", "available", "hint", "install_hint", "device"}


# ---------------------------------------------------------------------------
# tool-call extraction (bentuk yang benar-benar dikeluarkan chat template)
# ---------------------------------------------------------------------------
def test_extract_tagged_tool_call():
    text = (f'{TAG_OPEN}{{"name": "web_search", '
            f'"arguments": {{"query": "harga emas"}}}}{TAG_CLOSE}')
    calls, answer = extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "web_search"
    assert calls[0].arguments == {"query": "harga emas"}
    assert answer == "", "blok tool call tidak boleh bocor ke jawaban"


def test_extract_tool_call_with_leading_text():
    text = (f'Saya cari dulu ya.\n{TAG_OPEN}{{"name": "calculator", '
            f'"arguments": {{"expression": "2+2"}}}}{TAG_CLOSE}')
    calls, answer = extract_tool_calls(text)
    assert calls[0].name == "calculator"
    assert calls[0].arguments == {"expression": "2+2"}
    assert "cari dulu" in answer


def test_extract_bare_json_array_tool_call():
    """Llama-3.1 style: no tags, just a JSON array."""
    text = '[{"name": "create_diagram", "arguments": {"code": "graph TD; A-->B"}}]'
    calls, _ = extract_tool_calls(text)
    assert len(calls) == 1 and calls[0].name == "create_diagram"
    assert calls[0].arguments["code"].startswith("graph TD")


def test_arguments_may_be_a_json_string():
    text = f'{TAG_OPEN}{{"name": "web_search", "arguments": "{{\\"q\\": 1}}"}}{TAG_CLOSE}'
    calls, _ = extract_tool_calls(text)
    assert calls[0].arguments == {"q": 1}


def test_plain_answer_has_no_calls():
    calls, answer = extract_tool_calls("Ibu kota Prancis adalah Paris.")
    assert calls == [] and answer == "Ibu kota Prancis adalah Paris."


def test_tag_parser_survives_tags_split_across_chunks():
    parser = TagStreamParser({"think": THINK_TAGS, "tool_call": TOOL_CALL_TAGS})
    out = []
    for piece in ("Halo ", "<too", "l_call>", '{"name": "x", ',
                  '"arguments": {}}', "</tool_", "call>", "Selesai."):
        out += parser.feed(piece)
    out += parser.flush()
    kinds = [k for k, _ in out]
    text = "".join(c for k, c in out if k == "text")
    assert "tool_call" in kinds and "think" not in kinds
    assert text == "Halo Selesai.", text
    assert "<too" not in text


# ---------------------------------------------------------------------------
# engine: load + stream (kode produksi, model nyata)
# ---------------------------------------------------------------------------
async def test_engine_loads_a_downloaded_model(loaded):
    assert loaded.ready() is True
    st = loaded.status()
    assert st["state"] == "ready" and st["running"] is True
    assert st["device"] == "cpu"
    assert st["repo_id"] == "ask-anything/TinyLlama-Test", "repo id dari manifest"
    assert st["params"] and st["params"] > 0


async def test_engine_refuses_a_folder_that_is_not_a_model(tmp_path):
    with pytest.raises(FileNotFoundError):
        await engine.load(tmp_path)


async def test_stream_produces_deltas_usage_and_done(loaded):
    events = [e async for e in loaded.stream(
        [{"role": "user", "content": "halo dunia"}], [],
        temperature=0.0, max_new_tokens=6)]
    types = [e.type for e in events]
    assert "delta" in types, types
    assert "usage" in types and "done" in types
    assert types[0] == "note", "langkah lokal harus terlihat di Interpreter"
    usage = next(e for e in events if e.type == "usage").data
    assert usage["prompt_tokens"] > 0 and usage["device"] == "cpu"
    assert next(e for e in events if e.type == "done").data["finish_reason"] == "stop"


async def test_stream_errors_helpfully_without_a_loaded_model():
    provider = HFLocalProvider(settings)
    events = [e async for e in provider.stream([{"role": "user", "content": "hi"}], [])]
    assert [e.type for e in events] == ["error"]
    assert "Model offline" in events[0].data["message"]


async def test_provider_label_shows_local_model(loaded):
    provider = build_provider(settings)
    assert isinstance(provider, HFLocalProvider)
    assert provider.model_label() == "ask-anything/TinyLlama-Test (lokal)"


# ---------------------------------------------------------------------------
# tool calling: model "memanggil tool" → agent loop benar-benar menjalankannya
# ---------------------------------------------------------------------------
class _FakeModel:
    """Pengganti `model.generate`: mendorong teks tertentu ke streamer.

    `TextStreamer.put` menerima *token id* (bukan teks) dan — dengan
    `skip_prompt=True` — membuang `put` pertama sebagai prompt, persis seperti
    `generate` sungguhan.
    """

    def __init__(self, text: str, tokenizer) -> None:
        self.text = text
        self.tokenizer = tokenizer

    def generate(self, *args, **kwargs):
        import torch

        streamer = kwargs["streamer"]
        streamer.put(kwargs["input_ids"])            # prompt → dilewati
        ids = self.tokenizer(self.text, add_special_tokens=False)["input_ids"]
        for i in range(0, len(ids), 2):
            streamer.put(torch.tensor([ids[i:i + 2]]))
        streamer.end()


async def test_local_tool_call_runs_the_tool(loaded, monkeypatch):
    """End-to-end: teks tool-call dari model lokal → tool dijalankan → jawaban."""
    from app.tools import get_tool
    from app.tools.base import ToolResult

    async def fake_run(args, ctx):
        assert args == {"query": "harga emas"}
        return ToolResult(summary="1 hasil", data={"results": [
            {"title": "Harga emas hari ini", "url": "https://x.test",
             "snippet": "Rp 1.200.000"}]})

    monkeypatch.setattr(get_tool("web_search"), "run", fake_run)
    monkeypatch.setattr(loaded, "model", _FakeModel(
        f'{TAG_OPEN}{{"name": "web_search", '
        f'"arguments": {{"query": "harga emas"}}}}{TAG_CLOSE}',
        loaded.tokenizer))

    events = [e async for e in loaded.stream(
        [{"role": "user", "content": "berapa harga emas?"}],
        [{"type": "function", "function": {"name": "web_search"}}],
        temperature=0.0, max_new_tokens=32)]
    types = [e.type for e in events]
    assert "tool_calls" in types, types
    call = next(e for e in events if e.type == "tool_calls").data["calls"][0]
    assert call["name"] == "web_search"
    assert call["arguments"] == {"query": "harga emas"}
    assert not any(e.type == "delta" for e in events), \
        "blok tool call tidak boleh tampil sebagai jawaban"


async def test_chat_endpoint_streams_from_the_local_model(client, loaded):
    """SSE `/api/chat` dengan provider huggingface/lokal."""
    with client.stream("POST", "/api/chat",
                       json={"message": "halo dunia apa kabar"}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines()
                  if line.startswith("data: ")]

    types = [e["type"] for e in events]
    assert "start" in types and "meta" in types and "done" in types
    assert "delta" in types, types
    meta = next(e for e in events if e["type"] == "meta")
    assert meta["provider"] == "huggingface"
    assert meta["model"].endswith("(lokal)")
    note = next(e for e in events if e["type"] == "note")
    assert "inference lokal" in note["message"]
    assert next(e for e in events if e["type"] == "agent_done")["answer"]
