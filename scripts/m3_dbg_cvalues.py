# -*- coding: utf-8 -*-
"""定位 m3_build_prefs 崩溃点: CValues 过滤循环。"""
import difflib
import faulthandler
import json
import os
import sys

faulthandler.enable()

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
rows = []
with open(os.path.join(BASE, "data/rl/cvalues.pref.jsonl"), encoding="utf-8") as f:
    for l in f:
        if l.strip():
            rows.append(json.loads(l))
print(f"loaded {len(rows)}", flush=True)

ok = 0
for i, r in enumerate(rows):
    ch = (r.get("chosen") or "").strip()
    rj = (r.get("rejected") or "").strip()
    if not ch or not rj:
        continue
    sm = difflib.SequenceMatcher(None, ch, rj)
    if sm.quick_ratio() > 0.95 or sm.ratio() > 0.85:
        continue
    ok += 1
    if i % 5000 == 0:
        print(f"at {i}, ok={ok}, len_ch={len(ch)}, len_rj={len(rj)}", flush=True)

print(f"done ok={ok}", flush=True)
