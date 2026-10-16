# -*- coding: utf-8 -*-
"""M4-2: 合并 dpo-v2 adapter → guardlm-dpo-v2-merged（GRPO 起点 + KL 锚）。

用 peft merge_and_unload（不依赖 LLaMA-Factory——venv 的 trl 已升级至 0.21，LF 依赖已破坏）。
用法:
  python scripts/m4_merge_dpo.py
"""
import os

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = "/root/saves/Qwen3-1.7B/guardlm-sft-v1-merged"
ADAPTER = "/root/saves/Qwen3-1.7B/guardlm-dpo-v2"
OUT = "/root/saves/Qwen3-1.7B/guardlm-dpo-v2-merged"

print(f"loading base: {BASE}")
model = AutoModelForCausalLM.from_pretrained(
    BASE, torch_dtype=torch.bfloat16, device_map="cpu")
print(f"loading adapter: {ADAPTER}")
model = PeftModel.from_pretrained(model, ADAPTER)
print("merging ...")
model = model.merge_and_unload()
os.makedirs(OUT, exist_ok=True)
model.save_pretrained(OUT, safe_serialization=True)
tok = AutoTokenizer.from_pretrained(BASE)
tok.save_pretrained(OUT)
print(f"saved -> {OUT}")
