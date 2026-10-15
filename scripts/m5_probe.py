# -*- coding: utf-8 -*-
"""M5-2: 通用能力探针（防遗忘监控器，手册任务2）。

3 条通用 prompt（闲聊/常识/简单数学），对目标模型生成并落盘。
用法: python scripts/m5_probe.py --model <path> --tag base --out data/cpt/probe_base.json
遗忘在领域 loss 上不可见，探针是唯一预警（手册附录卡）。
"""
import argparse
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

PROBES = [
    ("闲聊", "用一句话介绍一下你自己，并说说今天天气不错适合做什么。"),
    ("常识", "为什么夏天人们喜欢去海边？请用两句话回答。"),
    ("数学", "小明有 15 个苹果，给了小红 7 个，又买了 4 个，现在有几个？请给出计算过程。"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from harness.backend import TransformersBackend
    be = TransformersBackend(model_path=args.model)
    results = []
    for kind, q in PROBES:
        out = be.infer([(q, "")], max_new_tokens=120, temperature=0.3)[0]
        results.append({"kind": kind, "prompt": q, "output": out})
        print(f"[{args.tag}][{kind}] {out[:120]}")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"[产出] {args.out}")


if __name__ == "__main__":
    main()
