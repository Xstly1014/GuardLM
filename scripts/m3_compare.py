# -*- coding: utf-8 -*-
"""M3-3: dpo-v1 vs sft-v1 对比报告（含长度偏差检查）。

输入:
  reports/sft-v1.pred.jsonl  (M2 产物)
  reports/dpo-v1.pred.jsonl (M3-3 评测产物)

产出:
  reports/m3_compare.md

内容:
  ① 总体/分档指标对比（口径与 harness.metrics 完全一致）
  ② 五类召回 + T2 分扰动对比（DPO 主战场是 T3 边界与误伤，T2 留给 M4）
  ③ 长度偏差检查（DPO 已知副作用：输出变长/变短漂移）
  ④ 翻转分析（sft错→dpo修好了多少 / sft对→dpo弄坏了多少）

用法:
  python scripts/m3_compare.py
"""
import json
import os
import sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, BASE)

from harness.metrics import compute_metrics  # noqa: E402

RISK_LABELS = {"insult", "porn", "ads", "illegal"}


def load_pred(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def avg_len(rows):
    if not rows:
        return 0.0
    return sum(len(r["raw"]) for r in rows) / len(rows)


def fmt_row(name, a, b, better="up"):
    """a=sft b=dpo，输出对比行。better: 'up'=升好 'down'=降好"""
    if better == "up":
        delta = (b - a)
        arrow = "+" if delta >= 0 else ""
    else:
        delta = (a - b)
        arrow = "+" if delta >= 0 else ""
    flag = ""
    if abs(delta) > 1e-9:
        good = delta > 0
        flag = " △" if good else " ▽"
    return f"| {name} | {a:.4f} | {b:.4f} | {arrow}{delta:.4f}{flag} |"


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-pred", default="reports/sft-v1.pred.jsonl")
    ap.add_argument("--new-pred", default="reports/dpo-v1.pred.jsonl")
    ap.add_argument("--out", default="reports/m3_compare.md")
    ap.add_argument("--names", default="sft-v1,dpo-v1")
    ap.add_argument("--desc", default="sft-v1: QLoRA SFT (M2) | dpo: β=0.1, lr=1e-5, 1ep")
    args = ap.parse_args()
    name_a, name_b = args.names.split(",")

    sft = load_pred(os.path.join(BASE, args.base_pred))
    dpo = load_pred(os.path.join(BASE, args.new_pred))
    assert len(sft) == len(dpo), f"样本数不一致: {len(name_a)}={len(sft)} {len(name_b)}={len(dpo)}"

    ms, md = compute_metrics(sft), compute_metrics(dpo)
    L = [f"# M3 对比报告: {name_a} → {name_b}", ""]
    L.append(f"- 样本: {len(sft)} 条（T1/T2/T3 全量）")
    L.append(f"- {args.desc}")
    L.append("- 口径: 解析失败按判 none 计（FN），格式错误率单列")
    L.append("")

    # ① 总体
    L.append("## 1. 总体指标")
    L.append("")
    L.append(f"| 指标 | {name_a} | {name_b} | Δ |")
    L.append("|---|---|---|---|")
    L.append(fmt_row("F1", ms["overall"]["F1"], md["overall"]["F1"]))
    L.append(fmt_row("Recall", ms["overall"]["R"], md["overall"]["R"]))
    L.append(fmt_row("Precision", ms["overall"]["P"], md["overall"]["P"]))
    L.append(fmt_row("FPR(误伤)", ms["overall"]["FPR"], md["overall"]["FPR"], "down"))
    L.append(fmt_row("类别准确率", ms["overall_exact"], md["overall_exact"]))
    L.append(fmt_row("格式错误率", ms["overall_fmt_err"], md["overall_fmt_err"], "down"))
    L.append("")

    # ② 分档
    L.append("## 2. 分档指标")
    L.append("")
    for tier in ("T1", "T2", "T3"):
        a, b = ms["tiers"].get(tier), md["tiers"].get(tier)
        if not a or not b:
            continue
        L.append(f"### {tier}（n={a['binary']['n']}）")
        L.append("")
        L.append(f"| 指标 | {name_a} | {name_b} | Δ |")
        L.append("|---|---|---|---|")
        L.append(fmt_row("F1", a["binary"]["F1"], b["binary"]["F1"]))
        L.append(fmt_row("Recall", a["binary"]["R"], b["binary"]["R"]))
        L.append(fmt_row("FPR", a["binary"]["FPR"], b["binary"]["FPR"], "down"))
        L.append(fmt_row("类别准确率", a["exact"], b["exact"]))
        L.append(fmt_row("格式错误率", a["fmt_err"], b["fmt_err"], "down"))
        L.append("")

    # 五类召回
    L.append("### 五类召回（gold 视角）")
    L.append("")
    L.append("| 类别 | n | sft R | dpo R | Δ |")
    L.append("|---|---|---|---|---|")
    for lab in ("insult", "porn", "ads", "illegal", "none"):
        a = ms["label_recalls"].get(lab)
        b = md["label_recalls"].get(lab)
        if not a or not b:
            continue
        ra, rb = a["recall"], b["recall"]
        delta = rb - ra
        arrow = "+" if delta >= 0 else ""
        L.append(f"| {lab} | {a['n']} | {ra:.1%} | {rb:.1%} | {arrow}{delta:.1%} |")
    L.append("")

    # T2 分扰动
    if ms["t2_by_perturb"] or md["t2_by_perturb"]:
        L.append("### T2 分扰动 Recall（M4 GRPO 主战场，本阶段只看不动）")
        L.append("")
        L.append("| 扰动 | n | sft R | dpo R | Δ |")
        L.append("|---|---|---|---|---|")
        keys = sorted(set(ms["t2_by_perturb"]) | set(md["t2_by_perturb"]))
        for k in keys:
            a = ms["t2_by_perturb"].get(k, {})
            b = md["t2_by_perturb"].get(k, {})
            ra = a.get("R", 0.0)
            rb = b.get("R", 0.0)
            delta = rb - ra
            arrow = "+" if delta >= 0 else ""
            L.append(f"| {k} | {a.get('n', 0)} | {ra:.1%} | {rb:.1%} | {arrow}{delta:.1%} |")
        L.append("")

    # ③ 长度偏差检查
    L.append("## 3. 长度偏差检查（DPO 已知副作用）")
    L.append("")
    la_all, lb_all = avg_len(sft), avg_len(dpo)
    drift = (lb_all - la_all) / la_all if la_all else 0
    verdict = "PASS（±10% 内）" if abs(drift) <= 0.10 else "WARN：明显漂移，检查偏好对长度配平"
    L.append(f"| 口径 | {name_a} | {name_b} | 漂移 |")
    L.append("|---|---|---|---|")
    L.append(f"| 全量平均输出长度(字符) | {la_all:.1f} | {lb_all:.1f} | {drift:+.1%} |")
    for tier in ("T1", "T2", "T3"):
        sa = [r for r in sft if r["tier"] == tier]
        sb = [r for r in dpo if r["tier"] == tier]
        if not sa or not sb:
            continue
        va, vb = avg_len(sa), avg_len(sb)
        d = (vb - va) / va if va else 0
        L.append(f"| {tier} 平均长度 | {va:.1f} | {vb:.1f} | {d:+.1%} |")
    L.append("")
    L.append(f"**结论: {verdict}**")
    L.append("")

    # ④ 翻转分析
    L.append("## 4. 翻转分析")
    L.append("")
    sft_map = {r["id"]: r for r in sft}
    dpo_map = {r["id"]: r for r in dpo}
    fixed, broken, both_wrong, both_right = [], [], 0, 0
    for rid, dr in dpo_map.items():
        sr = sft_map[rid]
        s_ok = sr["pred_label"] == sr["gold_label"]
        d_ok = dr["pred_label"] == dr["gold_label"]
        if s_ok and not d_ok:
            broken.append((sr, dr))
        elif not s_ok and d_ok:
            fixed.append((sr, dr))
        elif not s_ok and not d_ok:
            both_wrong += 1
        else:
            both_right += 1
    L.append(f"- sft 错 → dpo 对（修复）: **{len(fixed)}** 条")
    L.append(f"- sft 对 → dpo 错（回退）: **{len(broken)}** 条")
    L.append(f"- 两版都对: {both_right} 条 | 两版都错: {both_wrong} 条")
    net = len(fixed) - len(broken)
    L.append(f"- 净收益: **{net:+d}** 条")
    L.append("")

    # 修复样本按 tier 分布
    from collections import Counter
    fix_tier = Counter(r["tier"] for _, r in fixed)
    brk_tier = Counter(r["tier"] for _, r in broken)
    L.append("| 档 | 修复 | 回退 |")
    L.append("|---|---|---|")
    for t in ("T1", "T2", "T3"):
        L.append(f"| {t} | {fix_tier.get(t, 0)} | {brk_tier.get(t, 0)} |")
    L.append("")

    # 典型样本
    def sample_lines(pairs, title, limit=8):
        out = [f"### {title}", ""]
        for sr, dr in pairs[:limit]:
            gold = sr["gold_label"]
            out.append(f"- `[{sr['tier']}]` {sr['id']} gold={gold} "
                       f"sft={sr['pred_label']} → dpo={dr['pred_label']}")
        out.append("")
        return out

    if fixed:
        L.extend(sample_lines(fixed, "典型修复样本（前 8）"))
    if broken:
        L.extend(sample_lines(broken, "典型回退样本（前 8）"))

    out_path = os.path.join(BASE, args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"-> {out_path}")

    # 控制台摘要
    print(f"[overall] sft F1={ms['overall']['F1']:.4f} -> dpo F1={md['overall']['F1']:.4f}")
    print(f"[overall] sft FPR={ms['overall']['FPR']:.4f} -> dpo FPR={md['overall']['FPR']:.4f}")
    print(f"[len drift] {drift:+.1%} ({verdict})")
    print(f"[flip] fixed={len(fixed)} broken={len(broken)} net={net:+d}")


if __name__ == "__main__":
    main()
