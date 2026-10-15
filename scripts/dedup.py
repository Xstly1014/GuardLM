# -*- coding: utf-8 -*-
"""
M1-T4: MinHash 模糊去重。

设计（与 M1 手册一致）:
  - 训练集内部去重用高阈值（默认 0.9）: 只去"真重复"
  - 增强变体不参与本步（增强在去重+切分之后才做，且变体刻意保留）
  - 精确去重先行（整行 hash），再跑 MinHash 层——两级漏斗省时间
  - num_perm=64（10 万级数据精度足够，速度比 128 快一倍）

用法:
  python scripts/dedup.py --in data/interim/all.unified.jsonl \
    --out data/interim/dedup.unified.jsonl --jaccard 0.9 --report reports/m1_dedup.md
"""
import argparse
import hashlib
import json
import os
from collections import Counter

from datasketch import MinHash, MinHashLSH

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# 保留优先级：原始公开数据 > 合成数据（重复对里优先留原始源）
SRC_PRIORITY = {"cold": 0, "safety_prompts": 0, "cvalues": 0, "synth": 1, "aug": 2}


def shingles(text, n=3):
    return {text[i:i + n] for i in range(max(len(text) - n + 1, 1))}


def minhash_sig(text, num_perm=64):
    m = MinHash(num_perm=num_perm)
    for s in shingles(text):
        m.update(s.encode("utf-8"))
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--jaccard", type=float, default=0.9)
    ap.add_argument("--num-perm", type=int, default=64)
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    in_path = os.path.join(BASE, args.inp)
    out_path = os.path.join(BASE, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    records = []
    with open(in_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    # ---- 第 1 级: 精确去重（hash 整行文本） ----
    seen_exact = set()
    exact_dedup = []
    exact_dup_cnt = 0
    for r in records:
        h = hashlib.md5(r["input"].encode("utf-8")).hexdigest()
        if h in seen_exact:
            exact_dup_cnt += 1
            continue
        seen_exact.add(h)
        exact_dedup.append(r)

    # ---- 第 2 级: MinHashLSH 模糊去重 ----
    lsh = MinHashLSH(threshold=args.jaccard, num_perm=args.num_perm)
    sigs = {}
    kept = []
    dup_pairs = []  # (kept_id, dropped_id, dropped_source)
    dropped_by_src = Counter()

    for i, r in enumerate(exact_dedup):
        sig = minhash_sig(r["input"], args.num_perm)
        key = f"r{i}"
        # 查询已入库的相似者
        hits = lsh.query(sig)
        if hits:
            # 有相似者：按优先级决定是否替换（原始源优先保留）
            keep_idx = int(hits[0][1:])  # key 格式 "r{i}" -> i
            if SRC_PRIORITY.get(r["source"], 9) < SRC_PRIORITY.get(exact_dedup[keep_idx]["source"], 9):
                # 新记录来源更"原始"：踢掉旧的留新的
                lsh.remove(hits[0])
                kept = [x for x in kept if x[0] != keep_idx]
                dup_pairs.append((r["id"], exact_dedup[keep_idx]["id"], exact_dedup[keep_idx]["source"]))
                dropped_by_src[exact_dedup[keep_idx]["source"]] += 1
                lsh.insert(key, sig)
                sigs[key] = sig
                kept.append((i, r))
            else:
                dup_pairs.append((exact_dedup[keep_idx]["id"], r["id"], r["source"]))
                dropped_by_src[r["source"]] += 1
        else:
            lsh.insert(key, sig)
            sigs[key] = sig
            kept.append((i, r))

    final = [r for _, r in kept]

    with open(out_path, "w", encoding="utf-8") as f:
        for r in final:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---- 报告 ----
    rep = ["# M1 去重报告", "",
           f"- 输入: {len(records)} 条",
           f"- 第 1 级精确去重: 移除 {exact_dup_cnt} 条（整行 md5 相同）",
           f"- 第 2 级 MinHash（num_perm={args.num_perm}, Jaccard≥{args.jaccard}）: 移除 {len(exact_dedup) - len(final)} 条",
           f"- 输出: {len(final)} 条",
           "",
           "## 重复来源归因（被移除侧）",
           "",
           "| source | 移除条数 |",
           "|---|---|"]
    for s, c in dropped_by_src.most_common():
        rep.append(f"| {s} | {c} |")
    rep += ["", f"## 相似对样例（前 20 对，人工复核用）", ""]
    for a, b, s in dup_pairs[:20]:
        rep.append(f"- 保留 `{a}` ← 移除 `{b}` (source={s})")

    if args.report:
        rp = os.path.join(BASE, args.report)
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        with open(rp, "w", encoding="utf-8") as f:
            f.write("\n".join(rep) + "\n")
        print(f"report -> {rp}")
    print(f"[dedup] {len(records)} -> exact-removed {exact_dup_cnt} -> fuzzy-removed "
          f"{len(exact_dedup) - len(final)} -> final {len(final)}")


if __name__ == "__main__":
    main()
