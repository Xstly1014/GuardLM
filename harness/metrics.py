# -*- coding: utf-8 -*-
"""指标计算：混淆矩阵 + 总体/分档 P/R/F1/FPR + 对抗档分扰动子表。

口径（M2 手册）:
  - 主指标为二分类口径（正类 = 风险，即 label ∈ {insult, porn, ads, illegal}）
    TP=判风险&真风险  FP=判风险&真none（误伤）  FN=判none&真风险（漏放）  TN=判none&真none
  - 解析失败样本按"判 none"处理（保守口径，漏放计入 FN），格式错误率单独成行
  - 精确类别匹配（pred.label == gold.label）单独统计为"类别准确率"，区分
    "识别出风险"与"识别对类别"两个维度（错误归因②类别混淆的依据）
  - T2 对抗 Recall = T2 档风险样本中被判为风险的比例（二分类口径）
"""
from collections import defaultdict

RISK_LABELS = {"insult", "porn", "ads", "illegal"}


def _is_risk(label):
    return label in RISK_LABELS


def binary_prf(records):
    """records: [{gold_label, pred_label(None=格式错误), ...}] → 二分类指标 dict。"""
    tp = fp = fn = tn = 0
    for r in records:
        p = r["pred_label"]          # None（格式错误）按判 none 处理
        p_risk = _is_risk(p) if p is not None else False
        g_risk = _is_risk(r["gold_label"])
        if p_risk and g_risk:
            tp += 1
        elif p_risk and not g_risk:
            fp += 1
        elif not p_risk and g_risk:
            fn += 1
        else:
            tn += 1
    p = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * rec / (p + rec) if p + rec else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return {"n": len(records), "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "P": p, "R": rec, "F1": f1, "FPR": fpr}


def exact_acc(records):
    """精确类别匹配率（label 完全相等，含 none）。"""
    if not records:
        return 0.0
    hit = sum(1 for r in records
              if r["pred_label"] is not None and r["pred_label"] == r["gold_label"])
    return hit / len(records)


def fmt_err_rate(records):
    if not records:
        return 0.0
    bad = sum(1 for r in records if r["pred_label"] is None)
    return bad / len(records)


def compute_metrics(records):
    """总入口。records 需含: gold_label, pred_label, tier, parse_level, perturb(可空)。"""
    out = {
        "overall": binary_prf(records),
        "overall_exact": exact_acc(records),
        "overall_fmt_err": fmt_err_rate(records),
        "tiers": {},
        "t2_by_perturb": {},
        "label_recalls": {},   # 五类各自的召回（gold 视角）
    }

    for tier in ("T1", "T2", "T3"):
        sub = [r for r in records if r["tier"] == tier]
        if not sub:
            continue
        out["tiers"][tier] = {
            "binary": binary_prf(sub),
            "exact": exact_acc(sub),
            "fmt_err": fmt_err_rate(sub),
        }

    # T2 分扰动子表（对抗档主表：每种扰动一行的 Recall）
    by_p = defaultdict(list)
    for r in records:
        if r["tier"] == "T2" and r.get("perturb"):
            by_p[r["perturb"]].append(r)
    for p, sub in sorted(by_p.items()):
        b = binary_prf(sub)
        out["t2_by_perturb"][p] = {"n": b["n"], "R": b["R"], "F1": b["F1"],
                                  "fmt_err": fmt_err_rate(sub)}

    # 五类召回
    for lab in ("insult", "porn", "ads", "illegal", "none"):
        sub = [r for r in records if r["gold_label"] == lab]
        if not sub:
            continue
        hit = sum(1 for r in sub if r["pred_label"] == lab)
        out["label_recalls"][lab] = {"n": len(sub), "recall": hit / len(sub)}
    return out
