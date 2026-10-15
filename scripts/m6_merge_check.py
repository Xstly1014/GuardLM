# -*- coding: utf-8 -*-
"""M6-1 merge_check: adapter 推理 vs 合并权重推理，逐条比对输出。

验证目标：LoRA 合并（W = W_base + BA）引入的数值扰动应为零或近零。
方法：50 条 T1 样本，greedy 解码（do_sample=False，确定性），同 batch 划分，
阶段1 加载 base+adapter 推理 -> 释放 -> 阶段2 加载 merged 推理 -> 逐条比对。
硬验收：50/50 输出一致；若有个别差异，逐条确认属于合并数值扰动并记录。

用法 (WSL venv):
  /root/guardlm-venv/bin/python /mnt/e/workspace_work/GuardLM/scripts/m6_merge_check.py
"""
import gc
import json
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

ADAPTER = "/root/saves/Qwen3-1.7B/guardlm-grpo-v1"
BASE = "/root/saves/Qwen3-1.7B/guardlm-dpo-v2-merged"
MERGED = "/root/models/guardlm-final"
EVAL = "/mnt/e/workspace_work/GuardLM/data/eval/t1.jsonl"
OUT = "/mnt/e/workspace_work/GuardLM/reports/m6_merge_check.json"
N = 50
BATCH = 10
MAX_NEW = 64


def build_prompts():
    rows = []
    with open(EVAL, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    rows = rows[:N]
    return [(r["instruction"], r["input"]) for r in rows]


def chat_text(tok, instruction, text):
    return tok.apply_chat_template(
        [{"role": "user", "content": f"{instruction}\n{text}"}],
        tokenize=False, add_generation_prompt=True, enable_thinking=False)


@torch.no_grad()
def greedy_infer(tok, model, prompts):
    outs = []
    for i in range(0, len(prompts), BATCH):
        chunk = prompts[i:i + BATCH]
        texts = [chat_text(tok, ins, txt) for ins, txt in chunk]
        enc = tok(texts, return_tensors="pt", padding=True,
                  truncation=True, max_length=512).to("cuda")
        gen = model.generate(
            **enc, max_new_tokens=MAX_NEW, do_sample=False,
            pad_token_id=tok.pad_token_id or tok.eos_token_id)
        for j in range(len(chunk)):
            new_ids = gen[j][enc["input_ids"].shape[1]:]
            outs.append(tok.decode(new_ids, skip_special_tokens=True))
        print(f"  batch {i}-{i+len(chunk)} done")
    return outs


def load_adapter_mode():
    tok = AutoTokenizer.from_pretrained(BASE)
    tok.padding_side = "left"
    base = AutoModelForCausalLM.from_pretrained(
        BASE, torch_dtype=torch.bfloat16, device_map="cuda",
        attn_implementation="eager")
    model = PeftModel.from_pretrained(base, ADAPTER)
    model.eval()
    return tok, model


def load_merged_mode():
    tok = AutoTokenizer.from_pretrained(MERGED)
    tok.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        MERGED, torch_dtype=torch.bfloat16, device_map="cuda",
        attn_implementation="eager")
    model.eval()
    return tok, model


def release(tok, model):
    del model
    gc.collect()
    torch.cuda.empty_cache()


def main():
    prompts = build_prompts()
    print(f"samples={len(prompts)}")

    print("[stage 1] adapter inference (dpo-v2-merged + grpo-v1)")
    t0 = time.time()
    tok1, m1 = load_adapter_mode()
    outs_adapter = greedy_infer(tok1, m1, prompts)
    print(f"  stage1 {time.time()-t0:.1f}s")
    release(tok1, m1)

    print("[stage 2] merged inference (guardlm-final)")
    t0 = time.time()
    tok2, m2 = load_merged_mode()
    outs_merged = greedy_infer(tok2, m2, prompts)
    print(f"  stage2 {time.time()-t0:.1f}s")
    release(tok2, m2)

    same = sum(1 for a, b in zip(outs_adapter, outs_merged) if a == b)
    diffs = [{"i": i, "adapter": outs_adapter[i], "merged": outs_merged[i]}
             for i in range(len(prompts)) if outs_adapter[i] != outs_merged[i]]

    result = {
        "n": len(prompts), "match": same,
        "match_rate": same / len(prompts),
        "label_consistent": None,
        "diffs": diffs,
    }
    # 标签层面一致性（即使文本有微小差异，判定标签是否一致）
    import sys
    sys.path.insert(0, "/mnt/e/workspace_work/GuardLM")
    from harness.parse import parse_pred
    lab_same = 0
    for a, b in zip(outs_adapter, outs_merged):
        la, _ = parse_pred(a)
        lb, _ = parse_pred(b)
        if (la or {}).get("label") == (lb or {}).get("label"):
            lab_same += 1
    result["label_consistent"] = lab_same

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"match: {same}/{len(prompts)} (text)")
    print(f"match: {lab_same}/{len(prompts)} (label)")
    print(f"result -> {OUT}")
    if diffs:
        print("---- text diffs (first 5) ----")
        for d in diffs[:5]:
            print(f"[{d['i']}] adapter : {d['adapter'][:120]}")
            print(f"[{d['i']}] merged  : {d['merged'][:120]}")


if __name__ == "__main__":
    main()
