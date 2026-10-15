# -*- coding: utf-8 -*-
"""
M1-T1: 数据分布统计。对 data/interim/ 下所有 *.unified.jsonl 输出:
  1) 各源条数表
  2) 5 类分布表（none 占比一目了然）
  3) 长度分布（分位数）
  4) origin_label 明细（SP 细分判例的分布）
输出 markdown 到 reports/，可直接贴 experiments.md。

用法:
  python scripts/stats.py data/interim/ -o reports/m1_stats.md
"""
import argparse
import glob
import json
import os
from collections import Counter

import numpy as np

LABELS = ["insult", "porn", "ads", "illegal", "none"]


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="目录或 jsonl 文件列表")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    paths = []
    for inp in args.inputs:
        if os.path.isdir(inp):
            paths += sorted(glob.glob(os.path.join(inp, "*.unified.jsonl")))
        else:
            paths.append(inp)

    lines = ["# M1 数据分布统计", ""]
    total_by_src = Counter()
    label_by_src = {}
    origin_by_src = {}
    lens_by_label = {}
    all_cnt = 0

    for p in paths:
        src = os.path.basename(p).split(".")[0]
        labels, origins, lens = Counter(), Counter(), []
        n = 0
        for rec in load_jsonl(p):
            n += 1
            out = json.loads(rec["output"])
            lab = out.get("label", "?")
            labels[lab] += 1
            origins[rec.get("origin_label", "?")] += 1
            lens.append(len(rec.get("input", "")))
        total_by_src[src] = n
        label_by_src[src] = labels
        origin_by_src[src] = origins
        lens_by_label[src] = lens
        all_cnt += n

        lines.append(f"## {src}（{n} 条）")
        lines.append("")
        lines.append("| label | n | pct |")
        lines.append("|---|---|---|")
        for lab in LABELS + ["?"]:
            c = labels.get(lab, 0)
            if c:
                lines.append(f"| {lab} | {c} | {c / max(n, 1) * 100:.1f}% |")
        if lens:
            arr = np.array(lens)
            lines.append("")
            lines.append(f"- 长度: min={arr.min()} p25={int(np.percentile(arr, 25))} "
                         f"median={int(np.percentile(arr, 50))} p95={int(np.percentile(arr, 95))} max={arr.max()}")
        lines.append("- origin_label 明细: " + ", ".join(f"{k}={v}" for k, v in origins.most_common(20)))
        lines.append("")

    # 汇总表
    lines.insert(2, "| source | total | " + " | ".join(LABELS) + " |")
    lines.insert(3, "|---|---|" + "---|" * len(LABELS))
    row = 4
    for src, n in total_by_src.items():
        lb = label_by_src[src]
        lines.insert(row, f"| {src} | {n} | " + " | ".join(str(lb.get(l, 0)) for l in LABELS) + " |")
        row += 1
    none_total = sum(lb.get("none", 0) for lb in label_by_src.values())
    lines.insert(row, f"| **合计** | {all_cnt} | none 占比 {none_total / max(all_cnt, 1) * 100:.1f}% |")
    lines.insert(row + 1, "")

    text = "\n".join(lines)
    if args.out:
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", args.out)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"written -> {out_path}")
    else:
        print(text)


if __name__ == "__main__":
    main()
