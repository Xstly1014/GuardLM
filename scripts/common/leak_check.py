# -*- coding: utf-8 -*-
"""
M1-T5b: 训练-评测隔离校验（Leakage Check）。

双重校验:
  1) MinHash 相似度 >= 0.6 的 train-eval 对 -> 逐条列出，人工裁决后移除训练侧
  2) origin_id 关联校验: 评测样本的母本/变体是否出现在训练集

通过线: 0.6 相似对 = 0 条（一条都不能有，宁严勿松）

用法:
  python scripts/common/leak_check.py --train data/sft/train.jsonl data/rl/train_pref.jsonl \
    --eval data/eval/ --jaccard 0.6 --report reports/m1_leak.md
"""
import argparse
import glob
import json
import os
from collections import defaultdict

from datasketch import MinHash, MinHashLSH

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")


def shingles(text, n=3):
    return {text[i:i + n] for i in range(max(len(text) - n + 1, 1))}


def minhash_sig(text, num_perm=64):
    m = MinHash(num_perm=num_perm)
    for s in shingles(text):
        m.update(s.encode("utf-8"))
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", nargs="+", required=True)
    ap.add_argument("--eval", dest="eval_dirs", nargs="+", required=True)
    ap.add_argument("--jaccard", type=float, default=0.6)
    ap.add_argument("--num-perm", type=int, default=64)
    ap.add_argument("--report", default="reports/m1_leak.md")
    args = ap.parse_args()

    def read_jsonl(p):
        with open(p, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]

    # ---- 读训练侧（SFT: input 字段; DPO: prompt 字段）----
    train_texts = []  # (src_file, idx, text)
    for p in args.train:
        path = os.path.join(BASE, p)
        if not os.path.exists(path):
            print(f"[warn] train file missing: {p}")
            continue
        for i, r in enumerate(read_jsonl(path)):
            t = r.get("input") or r.get("prompt") or ""
            if t:
                train_texts.append((p, i, t, r))

    # ---- 读评测侧 ----
    eval_texts = []  # (file, idx, text, rec)
    for d in args.eval_dirs:
        dp = os.path.join(BASE, d)
        files = sorted(glob.glob(os.path.join(dp, "*.jsonl"))) if os.path.isdir(dp) else [dp]
        for p in files:
            for i, r in enumerate(read_jsonl(p)):
                t = r.get("input") or ""
                if t:
                    eval_texts.append((p, i, t, r))

    print(f"train={len(train_texts)} eval={len(eval_texts)}")

    # ---- 1) MinHash 相似对 ----
    lsh = MinHashLSH(threshold=args.jaccard, num_perm=args.num_perm)
    sigs = []
    for i, (_, _, t, _) in enumerate(train_texts):
        sig = minhash_sig(t, args.num_perm)
        lsh.insert(f"tr{i}", sig)
        sigs.append(sig)

    similar_pairs = []
    for j, (fp, _, t, _) in enumerate(eval_texts):
        sig = minhash_sig(t, args.num_perm)
        for hit in lsh.query(sig):
            i = int(hit[2:])
            sim = sigs[i].jaccard(sig)
            if sim >= args.jaccard:
                similar_pairs.append((sim, train_texts[i][0], train_texts[i][2], fp, t))

    # ---- 2) origin_id 关联校验 ----
    train_ids = set()
    train_origin_ids = set()
    for _, _, _, r in train_texts:
        if "id" in r:
            train_ids.add(r["id"])
        if "origin_id" in r:
            train_origin_ids.add(r["origin_id"])
    origin_leaks = []
    for fp, _, _, r in eval_texts:
        rid = r.get("id", "")
        oid = r.get("origin_id", "")
        # 评测样本 id 出现在训练 origin_id（评测母本的变体进了训练）
        if rid and rid in train_origin_ids:
            origin_leaks.append((fp, rid, "eval-id appears as train origin_id"))
        # 训练样本 id 出现在评测 origin_id（训练母本的变体进了评测）
        if oid and oid in train_ids:
            origin_leaks.append((fp, rid, f"train sample {oid} is origin of eval record"))

    # ---- 报告 ----
    n_sim = len(similar_pairs)
    n_org = len(origin_leaks)
    status = "PASS" if (n_sim == 0 and n_org == 0) else "FAIL"
    rep = [f"# M1 训练-评测隔离校验报告", "",
           f"- 结论: **{status}**",
           f"- MinHash(Jaccard>={args.jaccard}) 相似对: {n_sim} 条（通过线 = 0）",
           f"- origin_id 关联泄漏: {n_org} 条（通过线 = 0）",
           f"- 训练侧文本: {len(train_texts)}; 评测侧文本: {len(eval_texts)}",
           ""]
    if similar_pairs:
        rep += ["## 相似对明细（需人工裁决，移除训练侧）", "",
                "| sim | train 文本 | eval 文本 |", "|---|---|---|"]
        for sim, tf, tt, ef, et in sorted(similar_pairs, reverse=True)[:50]:
            rep.append(f"| {sim:.2f} | {tt[:40]}... ({tf}) | {et[:40]}... |")
    if origin_leaks:
        rep += ["## origin 关联泄漏明细", ""]
        for fp, rid, why in origin_leaks[:50]:
            rep.append(f"- `{rid}` @ {fp}: {why}")

    rp = os.path.join(BASE, args.report)
    os.makedirs(os.path.dirname(rp), exist_ok=True)
    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(rep) + "\n")
    print(f"[leak_check] {status}: similar={n_sim}, origin_leak={n_org}")
    print(f"report -> {rp}")


if __name__ == "__main__":
    main()
