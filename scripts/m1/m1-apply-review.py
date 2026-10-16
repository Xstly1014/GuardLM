# -*- coding: utf-8 -*-
"""M1-T3b: 应用人审结论——#24 淘汰（语义歧义）、#45 改标（ads_direct→porn_direct）。

人审记录（review/m1_synth_review.md，50 条抽样，2026-10-15）:
  - #24 "这教程真适合新手，看完才知道第一步是先成为高手" — sarcasm/ads 歧义 → 淘汰
  - #43 "台词背得再熟也没用..." — 保留 insinuation
  - #45 "夜里想看点新鲜的，去主页找暗号" — 标签改判 ads_direct → porn_direct
  - 其余 47 条通过（不合格率 1/50 = 2%）
"""
import json
import os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
RAW = os.path.join(BASE, "data/interim/synth.raw.jsonl")
EXCLUDE = os.path.join(BASE, "review/m1_synth_exclude.txt")

# 人审淘汰文本（子串匹配定位 id）
EXCLUDE_TEXTS = [
    "这教程真适合新手，看完才知道第一步是先成为高手",
]
# 人审改标文本 -> 新 type
RELABEL = {
    "夜里想看点新鲜的，去主页找暗号": "porn_direct",
}

records = []
with open(RAW, encoding="utf-8") as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

excluded_ids = []
relabeled = 0
for r in records:
    txt = r.get("input", "")
    for et in EXCLUDE_TEXTS:
        if et in txt:
            excluded_ids.append(r["id"])
            r["_exclude"] = True
    for old, new_type in RELABEL.items():
        if old in txt and r.get("type") != new_type:
            old_type = r.get("type")
            r["type"] = new_type
            r["relabel"] = f"{old_type}->{new_type}(human)"
            relabeled += 1

# 排除清单写盘（promote.py --exclude-file 消费）
os.makedirs(os.path.dirname(EXCLUDE), exist_ok=True)
with open(EXCLUDE, "w", encoding="utf-8") as f:
    for eid in excluded_ids:
        f.write(eid + "\n")

# 改标写回 raw（原地更新）
with open(RAW, "w", encoding="utf-8") as f:
    for r in records:
        r.pop("_exclude", None)
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"[apply-review] excluded {len(excluded_ids)} -> {EXCLUDE}")
print(f"[apply-review] relabeled {relabeled} records")
for eid in excluded_ids:
    print(f"  exclude: {eid}")
