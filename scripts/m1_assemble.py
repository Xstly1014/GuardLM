# -*- coding: utf-8 -*-
"""
M1 收尾: 最终训练集组装。

流程:
  1) SFT: train_pool 按 --risk:none 配比采样（结论来自 ratio_probe）+
     配对增强（基样本入选则其变体以 --aug-pair-rate 概率随行）
  2) DPO: cvalues.pref.jsonl 采样 --n-dpo 条
  3) 输出 data/sft/train.jsonl + data/rl/train_pref.jsonl（M2/M3 直用）

用法:
  python scripts/m1_assemble.py --risk 3000 --ratio 3 --aug-pair-rate 0.5 --n-dpo 2000
"""
import argparse
import json
import os
import random
from collections import Counter, defaultdict

random.seed(2026)
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def load_jsonl(path):
    p = os.path.join(BASE, path)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--risk", type=int, default=3000, help="风险样本条数")
    ap.add_argument("--ratio", type=float, default=3.0, help="none:risk 配比（探针结论）")
    ap.add_argument("--aug-pair-rate", type=float, default=0.5,
                    help="基样本入选时其变体随行概率")
    ap.add_argument("--n-dpo", type=int, default=2000)
    ap.add_argument("--out-sft", default="data/sft/train.jsonl")
    ap.add_argument("--out-rl", default="data/rl/train_pref.jsonl")
    args = ap.parse_args()

    pool = load_jsonl("data/interim/train_pool.jsonl")
    augs = load_jsonl("data/interim/train_aug.jsonl")
    prefs = load_jsonl("data/rl/cvalues.pref.jsonl")

    # ---- 类别配额（风险类内平衡：insult 主力，其他类保底） ----
    by_label = defaultdict(list)
    for r in pool:
        by_label[json.loads(r["output"])["label"]].append(r)
    for v in by_label.values():
        random.shuffle(v)

    quota = {"insult": 0.55, "illegal": 0.30, "porn": 0.08, "ads": 0.07}
    picked_risk, picked_none = [], []
    for lab, frac in quota.items():
        take = min(round(args.risk * frac), len(by_label.get(lab, [])))
        picked_risk += by_label[lab][:take]
    n_none = min(round(args.risk * args.ratio), len(by_label.get("none", [])))
    picked_none = by_label["none"][:n_none]

    # ---- 配对增强 ----
    base_ids = {r["id"] for r in picked_risk}
    aug_by_origin = defaultdict(list)
    for a in augs:
        if a.get("origin_id") in base_ids:
            aug_by_origin[a["origin_id"]].append(a)
    picked_aug = []
    for oid, variants in aug_by_origin.items():
        for v in variants:
            if random.random() < args.aug_pair_rate:
                picked_aug.append(v)

    sft = picked_risk + picked_none + picked_aug
    random.shuffle(sft)

    os.makedirs(os.path.join(BASE, "data/sft"), exist_ok=True)
    with open(os.path.join(BASE, args.out_sft), "w", encoding="utf-8") as f:
        for r in sft:
            f.write(json.dumps({
                "instruction": r["instruction"],
                "input": r["input"],
                "output": r["output"],
                "source": r.get("source", ""),
            }, ensure_ascii=False) + "\n")

    # ---- DPO 偏好对 ----
    random.shuffle(prefs)
    dpo = prefs[:args.n_dpo]
    with open(os.path.join(BASE, args.out_rl), "w", encoding="utf-8") as f:
        for r in dpo:
            f.write(json.dumps({
                "prompt": r["prompt"],
                "chosen": r["chosen"],
                "rejected": r["rejected"],
                "source": "cvalues",
            }, ensure_ascii=False) + "\n")

    lab_cnt = Counter(json.loads(r["output"])["label"] for r in sft)
    print(f"[sft] risk={len(picked_risk)} none={len(picked_none)} aug={len(picked_aug)} "
          f"total={len(sft)}")
    print(f"  labels: {dict(lab_cnt)}")
    print(f"[dpo] {len(dpo)} pairs")
    print(f"written -> {args.out_sft} / {args.out_rl}")


if __name__ == "__main__":
    main()
