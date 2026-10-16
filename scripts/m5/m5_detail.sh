#!/usr/bin/env bash
# M5-4: 误伤明细 + P5 黑话探针对比明细
cd /mnt/e/workspace_work/GuardLM
PY=/root/guardlm-venv/bin/python

$PY - <<'EOF'
import json

print("=" * 70)
print("A. sft-v2 T1 误伤明细（none 被判风险）")
print("=" * 70)
fps = []
with open("reports/artifacts/sft-v2.pred.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r["gold_label"] == "none" and r["pred_label"] and r["pred_label"] != "none":
            fps.append(r)
print(f"共 {len(fps)} 条误伤\n")
eval_texts = {}
with open("data/eval/t1.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        eval_texts[r["id"]] = r["input"]

for r in fps:
    try:
        obj = json.loads(r["raw"])
        risk, reason = obj.get("risk"), obj.get("reason", "")
    except Exception:
        risk, reason = "?", r["raw"][:60]
    print(f"[{r['id']}] pred={r['pred_label']}(risk={risk})")
    print(f"  text: {eval_texts.get(r['id'], '?')[:80]}")
    print(f"  reason: {reason[:80]}")
    print()

print("=" * 70)
print("B. P5 黑话探针逐条对比（sft-v1 vs sft-v2）")
print("=" * 70)
def load_pred(p):
    d = {}
    with open(p, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            d[r["id"]] = r
    return d

p1 = load_pred("reports/artifacts/sft-v1.p5.pred.jsonl")
p2 = load_pred("reports/artifacts/sft-v2.p5.pred.jsonl")
gold = {}
with open("data/eval/probe_slang.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        gold[r["id"]] = r

n_flip = 0
for rid in sorted(p2.keys()):
    g = gold[rid]["gold"]["label"]
    a, b = p1[rid]["pred_label"], p2[rid]["pred_label"]
    mark_a = "OK " if a == g else "MISS"
    mark_b = "OK " if b == g else "MISS"
    if (a == g) != (b == g):
        n_flip += 1
        flip = " <== CPT 改变"
    else:
        flip = ""
    print(f"[{rid}] gold={g:8s} sft-v1={str(a):8s}({mark_a}) sft-v2={str(b):8s}({mark_b}){flip}")
    print(f"  text: {gold[rid]['input'][:70]}")
print(f"\nCPT 改变判定方向的条数: {n_flip}/20")
EOF
