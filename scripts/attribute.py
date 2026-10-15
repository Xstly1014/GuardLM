# -*- coding: utf-8 -*-
"""M2-T4: 错误归因四分类——M3/M4 的路线图。

四分类规则（M2 手册）:
  ① 格式错误   parse_level == format_error（SFT 后应 <3%）
  ② 类别混淆   JSON 合法，pred 是风险但类别 != gold
  ③ 对抗失效   pred=none 而 gold=风险（漏放；T2 档主力错误，M4 GRPO 主战场）
  ④ 边界误判   T3 档判错 或 pred=风险而 gold=none（误伤 FP，M3 DPO 核心素材）

优先级: ① > ④ > ③ > ②（前面命中则归前面，一条样本只归一类）。
注意 ②③ 的区分: ②是"判出风险但类别错"（识别对、分类错），③是"整条漏放"。

用法:
  python scripts/attribute.py --pred reports/sft-v1.pred.jsonl \
      --eval data/eval/ -o reports/sft-v1.attribution.md
"""
import argparse
import json
import os
from collections import Counter

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RISK_LABELS = {"insult", "porn", "ads", "illegal"}
EVAL_FILES = ["t1.jsonl", "t2_variants.jsonl", "t2_sp_attack.jsonl", "t3.jsonl"]


def load_eval(eval_dir):
    gold = {}
    for fname in EVAL_FILES:
        path = os.path.join(eval_dir, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    gold[r["id"]] = r
    return gold


def attribute(pred_row, eval_row):
    """返回归因类别 + 简述。优先级: ① > ③ > ④ > ②（一条样本只归一类）。

    手册口径:
      ③ 对抗失效 = T2 档带扰动标记的样本判错（变形绕过，M4 GRPO 主战场）
      ④ 边界误判 = T3 档判错 或 误伤 FP（pred 风险而 gold none，M3 DPO 素材）
      ② 类别混淆 = 其余 label 错（T1 常规档，基础判定能力）
    """
    if pred_row["parse_level"] == "format_error" or pred_row["pred_label"] is None:
        return "1_format", "解析失败"
    pred, gold = pred_row["pred_label"], eval_row["gold"]["label"]
    tier = eval_row["tier"]
    if pred != gold:
        is_adv = tier == "T2" and eval_row.get("perturb", "")
        if is_adv:
            kind = "漏放" if pred == "none" else "变形判错"
            return "3_adv evade", f"{kind}: gold={gold} pred={pred}"
        if tier == "T3":
            return "4_boundary", f"T3 边界: gold={gold} pred={pred}"
        if pred in RISK_LABELS and gold == "none":
            return "4_boundary", f"误伤: gold=none pred={pred}"
        return "2_confusion", f"gold={gold} pred={pred}"
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--eval", default="data/eval/")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    eval_map = load_eval(os.path.join(BASE, args.eval))
    rows = []
    with open(os.path.join(BASE, args.pred), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    counter = Counter()
    examples = {}
    for p in rows:
        ev = eval_map.get(p["id"])
        if ev is None:
            continue
        cat, desc = attribute(p, ev)
        if cat:
            counter[cat] += 1
            examples.setdefault(cat, []).append({
                "id": p["id"], "tier": ev["tier"],
                "perturb": ev.get("perturb", ""), "desc": desc,
                "text": ev["input"][:50],
            })

    total = len(rows)
    n_err = sum(counter.values())
    lines = ["# 错误归因四分类", ""]
    lines.append(f"- 样本总数: {total}，错误样本: {n_err}（{n_err / max(total, 1):.1%}）")
    lines.append("")
    lines.append("| 归因类别 | 数量 | 占错误比 | 占总量比 |")
    lines.append("|---|---|---|---|")
    order = ["1_format", "2_confusion", "3_adv evade", "4_boundary"]
    names = {"1_format": "① 格式错误", "2_confusion": "② 类别混淆",
             "3_adv evade": "③ 对抗失效（漏放）", "4_boundary": "④ 边界误判（误伤/边界）"}
    for cat in order:
        n = counter.get(cat, 0)
        lines.append(f"| {names[cat]} | {n} | {n / max(n_err, 1):.1%} | {n / max(total, 1):.1%} |")
    lines.append("")

    for cat in order:
        if cat not in examples:
            continue
        lines.append(f"## {names[cat]} · 典型样本（前 3）")
        lines.append("")
        for ex in examples[cat][:3]:
            lines.append(f"- `{ex['id']}` [{ex['tier']}{('·' + ex['perturb']) if ex['perturb'] else ''}] "
                         f"{ex['desc']}  \n  {ex['text']}")
        lines.append("")

    # 一句话结论（占位，人工确认后改写进 experiments.md）
    top = counter.most_common(1)
    if top:
        lines.append(f"**主要矛盾（自动初判）**: {names[top[0][0]]}，"
                     f"占错误样本 {top[0][1] / max(n_err, 1):.1%}")
    lines.append("")

    os.makedirs(os.path.dirname(os.path.abspath(os.path.join(BASE, args.out))), exist_ok=True)
    with open(os.path.join(BASE, args.out), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"attribution -> {args.out}")
    for cat in order:
        print(f"  {cat}: {counter.get(cat, 0)}")
    print(f"  errors={n_err}/{total}")


if __name__ == "__main__":
    main()
