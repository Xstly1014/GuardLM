# -*- coding: utf-8 -*-
"""检查 aug 池与 train_pool 的类别分布，决定是否分层抽样。"""
import json
from collections import Counter


def label_of(output):
    try:
        return json.loads(output)["label"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


aug = [json.loads(l) for l in open("data/interim/train_aug.jsonl", encoding="utf-8") if l.strip()]
print("aug 池 label:", Counter(label_of(r["output"]) for r in aug).most_common())
pool = [json.loads(l) for l in open("data/interim/train_pool.jsonl", encoding="utf-8") if l.strip()]
print("train_pool label:", Counter(label_of(r["output"]) for r in pool).most_common())
