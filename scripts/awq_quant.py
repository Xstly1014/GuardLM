# -*- coding: utf-8 -*-
"""M6-5 AWQ 量化：guardlm-final -> guardlm-awq（4bit）。

AWQ 核心：按激活幅度识别 ~1% 显著权重并缩放保护，其余压 4bit。
校准集分布必须贴近线上分布——用评测集 prompt（instruction+input）。

用法 (WSL serve-venv):
  /root/serve-venv/bin/python /mnt/e/workspace_work/GuardLM/scripts/awq_quant.py \
      --model /root/models/guardlm-final --out /root/models/guardlm-awq
"""
import argparse
import json
import os

from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer

BASE = "/mnt/e/workspace_work/GuardLM"


def build_calib(n=128):
    """校准集：评测集 prompt（T1 为主 + T2/T3 少量，贴近线上分布）。"""
    files = ["t1.jsonl", "t2_variants.jsonl", "t3.jsonl"]
    texts = []
    for fname in files:
        path = os.path.join(BASE, "data/eval", fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    texts.append(f"{r['instruction']}\n{r['input']}")
    # 均匀打散后取前 n（覆盖三档而非只取 T1 头部）
    step = max(1, len(texts) // n)
    sampled = texts[::step][:n]
    print(f"calib: {len(sampled)} prompts from {len(texts)}")
    return sampled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="/root/models/guardlm-final")
    ap.add_argument("--out", default="/root/models/guardlm-awq")
    ap.add_argument("--n-calib", type=int, default=128)
    args = ap.parse_args()

    calib = build_calib(args.n_calib)

    print(f"loading {args.model} ...")
    model = AutoAWQForCausalLM.from_pretrained(args.model)
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)

    quant_config = {
        "zero_point": True,
        "q_group_size": 128,
        "w_bit": 4,
        "version": "GEMM",
    }
    print("quantizing (AWQ 4bit, GEMM) ...")
    model.quantize(tokenizer, quant_config=quant_config, calib_data=calib)

    print(f"saving -> {args.out}")
    model.save_quantized(args.out)
    tokenizer.save_pretrained(args.out)
    print("done. size:")
    os.system(f"du -sh {args.out}")


if __name__ == "__main__":
    main()
