# -*- coding: utf-8 -*-
"""M1-T4 debug: 打印基座对探针 prompt 的原始输出。"""
import json
import os

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
INSTRUCTION = "你是内容安全审核员。判定以下文本的风险类别并输出 JSON。"

tok = AutoTokenizer.from_pretrained("/root/models/Qwen3-1.7B")
model = AutoModelForCausalLM.from_pretrained(
    "/root/models/Qwen3-1.7B", torch_dtype=torch.bfloat16, device_map="cuda")

# 取 3 条不同类型样本
pool = []
with open(os.path.join(BASE, "data/interim/train_pool.jsonl"), encoding="utf-8") as f:
    for line in f:
        pool.append(json.loads(line))
texts = []
for want in ["insult", "illegal", "none"]:
    for r in pool:
        if json.loads(r["output"])["label"] == want:
            texts.append(r["input"])
            break

out_log = []
for t in texts:
    msgs = [{"role": "user", "content": f"{INSTRUCTION}\n文本：{t}"}]
    text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                   enable_thinking=False)
    out_log.append("=" * 60)
    out_log.append(f"INPUT: {t}")
    ids = tok(text, return_tensors="pt").to("cuda")
    with torch.no_grad():
        o = model.generate(**ids, max_new_tokens=200, do_sample=False,
                           pad_token_id=tok.eos_token_id)
    gen = tok.decode(o[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
    out_log.append(f"OUTPUT: {gen}")

p = os.path.join(BASE, "reports", "m1_probe_debug.txt")
with open(p, "w", encoding="utf-8") as f:
    f.write("\n".join(out_log))
print("written ->", p)
