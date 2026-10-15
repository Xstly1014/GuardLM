# -*- coding: utf-8 -*-
"""
M1-T2/T3: 人审工作表生成器。

对增强/合成产物抽样，生成 markdown 工作表:
  | # | 原文 | 变形后 | 扰动 | 标签 | 语义保持 | 可读 | 仍具风险 | 备注 |

人审勾选规则: 逐行三列判定（Y/N），不合格样本备注原因（拼音断词错/拆字撞词/符号过度/腔调重复…）。
审核完成后把结论写回 review 记录，供 promote/归因使用。

用法:
  python scripts/sample_review.py data/interim/cold.aug.jsonl -n 50 -o review/m1_aug_review.md
  python scripts/sample_review.py data/interim/synth.raw.jsonl -n 10 -o review/m1_synth_batch1.md --kind synth
"""
import argparse
import json
import os
import random

random.seed(42)
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def esc(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")[:120]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("-n", type=int, default=50)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--kind", default="aug", choices=["aug", "synth", "raw"],
                    help="aug=增强工作表; synth=合成人审表; raw=unified 抽检表")
    args = ap.parse_args()

    path = os.path.join(BASE, args.inp)
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    n = min(args.n, len(records))
    samples = random.sample(records, n)

    # 母本对照（aug 需要回查原文）
    origin_map = {}
    if args.kind == "aug":
        origin_ids = {r.get("origin_id") for r in samples if r.get("origin_id")}
        for p in [os.path.join(BASE, "data/interim/cold.unified.jsonl"),
                  os.path.join(BASE, "data/interim/sp.unified.jsonl")]:
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            r = json.loads(line)
                            if r.get("id") in origin_ids:
                                origin_map[r["id"]] = r["input"]

    lines = [f"# 人审工作表 · {os.path.basename(args.inp)}",
             "",
             f"- 抽样: {n} / {len(records)} 条",
             "- 判定口径: 语义保持（变形后意思没跑）/ 可读（人类能看懂）/ 仍具风险（变形后仍是风险文本）",
             "- 结论列填 Y/N；不合格的按扰动类型归因写备注",
             ""]

    if args.kind == "synth":
        lines += ["| # | 样本文本 | 类型 | 真边界? | 腔调重复? | 应打标签 | 备注 |",
                  "|---|---|---|---|---|---|---|"]
        for i, r in enumerate(samples, 1):
            lines.append(f"| {i} | {esc(r.get('input'))} | {r.get('type') or r.get('origin_label','')} |  |  |  |  |")
    elif args.kind == "raw":
        lines += ["| # | 样本文本 | 映射标签 | 原始标签 | 标签正确? | 备注 |",
                  "|---|---|---|---|---|---|"]
        for i, r in enumerate(samples, 1):
            lab = json.loads(r["output"])["label"] if "output" in r else "?"
            lines.append(f"| {i} | {esc(r.get('input'))} | {lab} | {r.get('origin_label','')} |  |  |")
    else:
        lines += ["| # | 原文 | 变形后 | 扰动 | 继承标签 | 语义保持 | 可读 | 仍具风险 | 备注 |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(samples, 1):
            origin = origin_map.get(r.get("origin_id"), "(母本未在池)")
            lab = json.loads(r["output"])["label"] if "output" in r else "?"
            lines.append(f"| {i} | {esc(origin)} | {esc(r.get('input'))} | {r.get('aug_mode','')} | {lab} |  |  |  |  |")

    out_path = os.path.join(BASE, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"written -> {out_path} ({n} samples)")


if __name__ == "__main__":
    main()
