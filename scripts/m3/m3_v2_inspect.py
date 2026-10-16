# -*- coding: utf-8 -*-
"""检查 prefs.jsonl 构成 + FP 样本 raw 输出（v2 构建前置）。"""
import json
from collections import Counter

pairs = [json.loads(l) for l in open(
    "data/rl/prefs.jsonl", encoding="utf-8") if l.strip()]
print("[sources]", dict(Counter(p["source"] for p in pairs)))
print("[err_class]", dict(Counter(p["err_class"] for p in pairs)))
# 方向统计: 判定对里 chosen=风险 vs chosen=none
dec = [p for p in pairs if p["source"] != "cvalues"]
ch_risk = sum(1 for p in dec if '"none"' not in p["chosen"][:30])
print(f"[direction] 判定对 {len(dec)} 中 chosen=风险 {ch_risk} / chosen=none {len(dec) - ch_risk}")

print("\n---- FP 样本 raw（rejected 素材） ----")
preds = [json.loads(l) for l in open(
    "reports/artifacts/m3_mining.pred.jsonl", encoding="utf-8") if l.strip()]
mine = {r["id"]: r for r in [json.loads(l) for l in open(
    "data/interim/m3_mining/t1.jsonl", encoding="utf-8") if l.strip()]}
fp = [p for p in preds if p["pred_label"] not in (None, "none")
      and p["gold_label"] == "none"]
for p in fp[:6]:
    print(f"id={p['id']}")
    print(f"  text: {mine[p['id']]['input'][:60]}")
    print(f"  raw : {p['raw'][:160]}")
