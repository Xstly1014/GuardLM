# -*- coding: utf-8 -*-
"""M1-T4: 合并多个 unified.jsonl 为 all.unified.jsonl（合成池就位后重跑本脚本即可）。"""
import glob
import json
import os
import sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

INTERIM = os.path.join(BASE, "data", "interim")
OUT = os.path.join(INTERIM, "all.unified.jsonl")

# 按序合并: cold -> sp -> synth(若有)
ORDER = ["cold.unified.jsonl", "sp.unified.jsonl", "synth.unified.jsonl"]

n = 0
with open(OUT, "w", encoding="utf-8") as fout:
    for name in ORDER:
        p = os.path.join(INTERIM, name)
        if not os.path.exists(p):
            print(f"[skip] {name} not present")
            continue
        cnt = 0
        with open(p, encoding="utf-8") as fin:
            for line in fin:
                if line.strip():
                    fout.write(line)
                    cnt += 1
        n += cnt
        print(f"[merge] {name}: {cnt}")
print(f"total {n} -> {OUT}")
