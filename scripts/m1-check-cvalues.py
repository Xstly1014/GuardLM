# -*- coding: utf-8 -*-
"""M1-T1 辅助: CValues prompt 重复情况核查。"""
import json
from collections import Counter

BASE = "data/raw/cvalues.jsonl"
prompts = Counter()
with open(BASE, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        prompts[r["prompt"]] += 1
dup_rows = sum(c for c in prompts.values() if c > 1)
print("total rows: 116536")
print("unique prompts:", len(prompts))
print("rows whose prompt occurs >1 time:", dup_rows)
print("top dup prompt counts:", [c for _, c in prompts.most_common(5)])
