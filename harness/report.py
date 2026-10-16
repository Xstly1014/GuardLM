# -*- coding: utf-8 -*-
"""Markdown 报告渲染（五节骨架，base-v0 / sft-v1 及后续所有版本复用）。"""
import os
import time


def _pct(x):
    return f"{100 * x:.1f}%"


def _f(x):
    return f"{x:.4f}"


def render_report(meta, metrics, badcases):
    """meta: {model, eval_dir, n, gen_params, extra}; metrics: compute_metrics 输出;
    badcases: 前 20 条错误样本 [{id, tier, gold, pred, level, text}]。"""
    ov = metrics["overall"]
    tiers = metrics["tiers"]
    t1 = tiers.get("T1", {})
    t2 = tiers.get("T2", {})
    t3 = tiers.get("T3", {})

    lines = []
    lines.append(f"# {meta['title']}")
    lines.append("")
    lines.append("> 生成时间: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("")

    # ① 版本信息
    lines.append("## 1. 版本信息")
    lines.append("")
    lines.append(f"- 模型: `{meta['model']}`")
    lines.append(f"- 评测集: `{meta['eval_dir']}`（{meta['n']} 条，{meta['tier_desc']}）")
    lines.append(f"- 生成参数: {meta['gen_params']}")
    if meta.get("extra"):
        lines.append(f"- 备注: {meta['extra']}")
    lines.append("")

    # ② 总体指标
    lines.append("## 2. 总体指标（T1+T2+T3 合并，二分类口径：正类=风险）")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| Precision | {_f(ov['P'])} |")
    lines.append(f"| Recall | {_f(ov['R'])} |")
    lines.append(f"| F1 | {_f(ov['F1'])} |")
    lines.append(f"| FPR（误伤率） | {_f(ov['FPR'])} |")
    lines.append(f"| 格式错误率 | {_pct(metrics['overall_fmt_err'])} |")
    lines.append(f"| 精确类别匹配率 | {_pct(metrics['overall_exact'])} |")
    lines.append(f"| 混淆矩阵 | TP={ov['TP']} FP={ov['FP']} FN={ov['FN']} TN={ov['TN']} |")
    lines.append("")

    # 分类别召回
    if metrics["label_recalls"]:
        lines.append("五类召回（gold 视角）:")
        lines.append("")
        lines.append("| 类别 | n | recall |")
        lines.append("|---|---|---|")
        for lab, d in metrics["label_recalls"].items():
            lines.append(f"| {lab} | {d['n']} | {_pct(d['recall'])} |")
        lines.append("")

    # ③ 分档指标
    lines.append("## 3. 分档指标")
    lines.append("")
    lines.append("| 档 | n | F1 | Recall | FPR | 格式错误率 | 类别匹配 |")
    lines.append("|---|---|---|---|---|---|---|")
    for tname, d in (("T1 常规", t1), ("T2 对抗", t2), ("T3 边界", t3)):
        if not d:
            continue
        b = d["binary"]
        lines.append(
            f"| {tname} | {b['n']} | {_f(b['F1'])} | {_f(b['R'])} | "
            f"{_f(b['FPR'])} | {_pct(d['fmt_err'])} | {_pct(d['exact'])} |")
    lines.append("")

    if metrics["t2_by_perturb"]:
        lines.append("T2 按扰动类型子表（对抗 Recall = 该扰动下风险样本被判风险的比例）:")
        lines.append("")
        lines.append("| 扰动 | n | 对抗 Recall | F1 | 格式错误率 |")
        lines.append("|---|---|---|---|---|")
        for p, d in metrics["t2_by_perturb"].items():
            lines.append(
                f"| {p} | {d['n']} | {_pct(d['R'])} | {_f(d['F1'])} | {_pct(d['fmt_err'])} |")
        lines.append("")

    # ④ bad case
    lines.append("## 4. Bad Case（前 20 条）")
    lines.append("")
    if badcases:
        lines.append("| # | id | 档 | gold | pred | 解析 | 文本（截断） |")
        lines.append("|---|---|---|---|---|---|---|")
        for i, bc in enumerate(badcases[:20], 1):
            text = bc["text"][:40].replace("|", " ").replace("\n", " ")
            pred = bc["pred_label"] if bc["pred_label"] is not None else "格式错误"
            lines.append(f"| {i} | {bc['id']} | {bc['tier']} | {bc['gold_label']} "
                         f"| {pred} | {bc['parse_level']} | {text} |")
    else:
        lines.append("（无错误样本）")
    lines.append("")

    # ⑤ 结论占位（人工填写/后续自动生成）
    lines.append("## 5. 结论与下一步")
    lines.append("")
    lines.append("- （待训练侧/归因侧填写）")
    lines.append("")
    return "\n".join(lines)


def write_report(path, content):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
