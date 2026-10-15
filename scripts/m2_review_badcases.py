# -*- coding: utf-8 -*-
"""M2 DoD f07: bad case 抽样复核——随机抽 N 条错误样本逐条核对归因合理性。"""
import argparse
import json
import random
import sys

sys.path.insert(0, "/mnt/e/workspace_work/GuardLM")
from scripts.attribute import load_eval, attribute

ap = argparse.ArgumentParser()
ap.add_argument("--pred", default="reports/sft-v1.pred.jsonl")
ap.add_argument("--eval", default="data/eval/")
ap.add_argument("-n", type=int, default=20)
ap.add_argument("--seed", type=int, default=7)
args = ap.parse_args()

ev = load_eval(args.eval)
errs = []
for line in open(args.pred, encoding="utf-8"):
    p = json.loads(line)
    e = ev.get(p["id"])
    if e and p["pred_label"] != e["gold"]["label"]:
        cat, desc = attribute(p, e)
        errs.append((cat, p["id"], e["tier"], e.get("perturb", ""),
                     e["gold"]["label"], p["pred_label"], e["input"][:38]))

random.seed(args.seed)
print(f"errors={len(errs)}, sampling {args.n}\n")
for cat, pid, tier, pert, g, pr, tx in random.sample(errs, min(args.n, len(errs))):
    print(f"{cat} | {tier}{pert} | {g}>{pr} | {tx}")
