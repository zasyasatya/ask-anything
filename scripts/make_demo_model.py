#!/usr/bin/env python3
"""Synthesize a Qwen2-architecture demo model into models/.

Digunakan HANYA untuk memverifikasi pipeline inference offline di sandbox CI
(yang tidak bisa menjangkau huggingface.co): model ini memakai arsitektur
`Qwen2ForCausalLM` + layout folder yang sama persis dengan
`Qwen/Qwen2.5-0.5B-Instruct` (config.json, chat template Jinja bergaya Qwen2,
tokenizer BPE, safetensors ter-shard + index, generation_config) — tetapi
bobotnya acak (bukan pretrained), jadi keluarannya tidak koheren. Di mesin
user, model asli (mis. Qwen/Qwen2.5-0.5B-Instruct) lewat jalur kode yang
sama persis.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch
from tokenizers import Tokenizer, decoders, pre_tokenizers
from tokenizers.models import BPE
from tokenizers.trainers import BpeTrainer
from transformers import (AutoConfig, AutoModelForCausalLM,
                          AutoTokenizer, PreTrainedTokenizerFast)

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "models" / "ask-anything" / "Qwen2-Demo-0.1B"
REPO_ID = "ask-anything/Qwen2-Demo-0.1B"

CHAT_TEMPLATE = """{% set loop_messages = messages %}{% for message in loop_messages %}{% if (message['role'] == 'user') != (loop.index0 % 2 == 0) %}{{ '<|im_start|>' + message['role'] + '\\n' + message['content'] + '<|im_end|>\\n' }}{% elif message['role'] == 'system' %}{{ '<|im_start|>system\\n' + message['content'] + '<|im_end|>\\n' }}{% elif message['role'] == 'assistant' %}{{ '<|im_start|>assistant\\n' + message['content'] + '<|im_end|>\\n' }}{% endif %}{% endfor %}{% if add_generation_prompt %}{{ '<|im_start|>assistant\\n' }}{% endif %}"""


def main() -> int:
    # Idempoten: buang hasil run sebelumnya (shard lama berantakan kalau
    # jumlah shard berubah).
    if DEST.is_dir():
        import shutil
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(20260916)

    # ---- tokenizer: BPE byte-level + special tokens gaya Qwen -------------
    special = ["<|im_start|>", "<|im_end|>", "<|endofprompt|>",
               "!" * 7, "<pad>", "<|box_end|>"]
    tok = Tokenizer(BPE(unk_token=special[3]))
    tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tok.decoder = decoders.ByteLevel()
    trainer = BpeTrainer(vocab_size=1200, special_tokens=special)
    korpus = (
        "Halo, saya model demo kecil arsitektur Qwen2 untuk verifikasi pipeline "
        "inference offline Ask Anything. Saya berjalan di CPU dengan PyTorch dan "
        "transformers, token demi token lewat streaming SSE. "
        "The quick brown fox jumps over the lazy dog. "
        "Model kecil ini membuktikan bahwa muat, template, generate, dan "
        "streaming semuanya berfungsi end to end. "
    ) * 200
    tok.train_from_iterator([korpus], trainer)
    fast = PreTrainedTokenizerFast(
        tokenizer_object=tok,
        unk_token=special[3], pad_token=special[4], eos_token=special[1],
        model_max_length=512)
    fast.chat_template = CHAT_TEMPLATE
    fast.save_pretrained(str(DEST))

    # ---- model: Qwen2ForCausalLM skala kecil -------------------------------
    from transformers import Qwen2Config

    qcfg = Qwen2Config(
        vocab_size=len(fast),
        hidden_size=256,
        intermediate_size=640,
        num_hidden_layers=6,
        num_attention_heads=8,
        num_key_value_heads=4,
        max_position_embeddings=512,
        rms_norm_eps=1e-06,
        rope_theta=1000000.0,
        tie_word_embeddings=False,
        bos_token_id=None,
        eos_token_id=fast.eos_token_id,
        use_cache=True,
    )
    model = AutoModelForCausalLM.from_config(qcfg)
    # Shard + index — sama dengan layout model Qwen2.5 asli (2 shard).
    model.save_pretrained(str(DEST), safe_serialization=True,
                          max_shard_size="4MB")

    import transformers

    gen = {
        "bos_token_id": None,
        "eos_token_id": fast.eos_token_id,
        "transformers_version": transformers.__version__,
        "do_sample": True,
        "temperature": 0.7,
        "top_p": 0.9,
        "max_new_tokens": 512,
    }
    (DEST / "generation_config.json").write_text(
        json.dumps(gen, ensure_ascii=False, indent=2), encoding="utf-8")

    # Manifest gaya downloader app (supaya list_local() menganggapnya lengkap).
    files = [p for p in DEST.rglob("*") if p.is_file()]
    (DEST / ".ask-anything.json").write_text(json.dumps({
        "repo_id": REPO_ID,
        "revision": "sandbox-synthetic",
        "downloaded_at": int(time.time()),
        "file_count": len(files),
        "size_bytes": sum(p.stat().st_size for p in files),
        "complete": True,
        "note": ("Model sintesis arsitektur Qwen2 untuk verifikasi pipeline di "
                 "sandbox (huggingface.co tidak terjangkau). Bobot acak — "
                 "bukan pretrained; keluaran tidak koheren."),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- verifikasi: load ulang lewat kode produksi ------------------------
    tok2 = AutoTokenizer.from_pretrained(str(DEST))
    model2 = AutoModelForCausalLM.from_pretrained(str(DEST))
    ids = tok2("halo dunia", return_tensors="pt").input_ids
    with torch.inference_mode():
        out = model2.generate(ids, max_new_tokens=8, do_sample=False)
    print("OK:", REPO_ID, "| params:",
          sum(p.numel() for p in model2.parameters()),
          "| files:", len(list(DEST.glob('*'))),
          "| sample:", repr(tok2.decode(out[0], skip_special_tokens=True)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
