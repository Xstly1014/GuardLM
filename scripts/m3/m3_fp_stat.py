# -*- coding: utf-8 -*-
"""M3-4: 从 mining 推理结果统计 sft-v1 误伤(FP)样本，评估误伤修正对的原料量。"""
import json
from collections import Counter

rows = [json.loads(l) for l in open(
    "reports/artifacts/m3_mining.pred.jsonl", encoding="utf-8") if l.strip()]
print("total", len(rows))
fp = [r for r in rows if r["pred_label"] not in (None, "none") and r["gold_label"] == "none"]
fn = [r for r in rows if (r["pred_label"] is None or r["pred_label"] == "none")
      and r["gold_label"] != "none"]
print("FP (pred risk, gold none):", len(fp))
print("FN (pred none, gold risk):", len(fn))
print("FP label dist:", Counter(r["pred_label"] for r in fp))
# 保存 FP id 列表
with open("reports/m3_fp_ids.json", "w", encoding="utf-8") as f:
    json.dump([r["id"] for r in fp], f, ensure_ascii=False)
print("-> reports/m3_fp_ids.json")
