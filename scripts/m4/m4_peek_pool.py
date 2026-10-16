# -*- coding: utf-8 -*-
"""盘点 GRPO prompt 池可用数据源。"""
import json
from collections import Counter


def peek(path, n=1):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    print(f"\n== {path} (n={len(rows)}) ==")
    print("keys:", list(rows[0].keys()))
    for r in rows[:n]:
        print({k: str(v)[:60] for k, v in r.items() if k != "output"} | {"output": str(r.get("output", ""))[:60]})
    return rows


pool = peek("data/interim/train_pool.jsonl")
print("label dist:", Counter(r.get("gold", r.get("label")) for r in pool))
aug = peek("data/interim/train_aug.jsonl")
print("aug perturb dist:", Counter(r.get("perturb") for r in aug).most_common(6))
