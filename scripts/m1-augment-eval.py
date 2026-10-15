# -*- coding: utf-8 -*-
"""
M1-T5a 补充: 为 T2 评测母本生成"评测专属变体"。

关键约束: 这些变体只进 T2 评测，母本已从训练池移除——训练集从未见过
该母本的任何形态（防泄漏铁律）。

扰动类型按 index 轮换，保证五种子表各 ~1/5 覆盖（手册坑表:
"T2 分扰动子表按类型配额抽样而非全量随机"）。

用法: python scripts/m1-augment-eval.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from augment import (PERTURBERS, find_risk_spans, harmless_perturb)  # noqa: E402

import random
random.seed(2026)

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MOTHERS = os.path.join(BASE, "data", "eval", "t2_mothers.jsonl")
OUT = os.path.join(BASE, "data", "eval", "t2_variants.jsonl")

MODES = ["pinyin", "homophone", "emoji", "split", "fan"]


def main():
    recs = []
    with open(MOTHERS, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                recs.append(json.loads(line))

    n_out = 0
    by_mode = {}
    with open(OUT, "w", encoding="utf-8") as fout:
        for i, m in enumerate(recs):
            text = m["input"]
            gold = m["gold"]
            # 每条母本产 1 个变体，模式轮换；命中不了换 fan 兜底
            mode = MODES[i % len(MODES)]
            spans = find_risk_spans(text)
            new_text = None
            if mode != "fan" and spans:
                new_text = PERTURBERS[mode](text, spans)
            if not new_text or new_text == text:
                new_text = PERTURBERS["fan"](text, None)
                mode = "fan"
            if not new_text or new_text == text:
                continue
            # 繁体若也与原文相同（说明文本无简繁差异），跳过
            variant = {
                "id": f"{m['id']}:aug",
                "instruction": m["instruction"],
                "input": new_text,
                "gold": gold,
                "source": "aug",
                "tier": "T2",
                "origin_id": m["id"],   # 隔离校验靠它
                "perturb": mode,
                "mother_text": text,
            }
            fout.write(json.dumps(variant, ensure_ascii=False) + "\n")
            by_mode[mode] = by_mode.get(mode, 0) + 1
            n_out += 1

    print(f"[t2-variants] {n_out} variants from {len(recs)} mothers")
    print("by_mode:", json.dumps(by_mode, ensure_ascii=False))
    print(f"written -> {OUT}")


if __name__ == "__main__":
    main()
