# -*- coding: utf-8 -*-
"""M1-T1: 从 ModelScope 下载 CValues-Comparison 到 data/raw/cvalues.jsonl"""
import json
import os
import sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
OUT = os.path.join(BASE, "data", "raw", "cvalues.jsonl")

from modelscope.msdatasets import MsDataset

ds = MsDataset.load("iic/CValues-Comparison", split="train")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
n = 0
with open(OUT, "w", encoding="utf-8") as f:
    for r in ds:
        f.write(json.dumps(dict(r), ensure_ascii=False) + "\n")
        n += 1
print(f"written {n} rows -> {OUT}")
