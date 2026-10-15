# -*- coding: utf-8 -*-
"""M3-4: 红线触发的统计显著性检验——判断差异是真实退化还是评测噪声。

检验:
  ① FPR: sft 1/140 vs dpo-v2 5/140 → Fisher 精确检验（双侧）
  ② T1 F1: sft-v1 vs dpo-v2 在 T1 档 250 条上的逐样本配对 → McNemar 检验
  ③ overall F1: 650 条配对 → McNemar 检验

判读:
  p > 0.05 → 差异不显著，红线触发在噪声范围内（样本量不足）
  p <= 0.05 → 真实退化，需要继续迭代
"""
import json
from math import comb

BASE = "."


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def fisher_exact_2x2(a, b, c, d):
    """Fisher 精确检验（双侧, 2x2）: [[a,b],[c,d]]。"""
    def p_hyper(x):
        return comb(a + b, x) * comb(c + d, a + c - x) / comb(a + b + c + d, a + c)
    lo = max(0, a - d)
    hi = min(a, c)
    p_obs = p_hyper(a)
    p_val = sum(p_hyper(x) for x in range(lo, hi + 1) if p_hyper(x) <= p_obs + 1e-12)
    return min(p_val, 1.0)


def mcnemar(b, c):
    """McNemar 精确检验（二项分布）: b=sft错dpo对, c=sft对dpo错。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k + 1)) * (0.5 ** n) * 2
    return min(p, 1.0)


def main():
    sft = load("reports/sft-v1.pred.jsonl")
    dpo = load("reports/dpo-v2.pred.jsonl")

    # ① FPR: none 样本上误伤数
    none_s = [r for r in sft if r["gold_label"] == "none"]
    none_d = {r["id"]: r for r in dpo if r["gold_label"] == "none"}
    fp_s = sum(1 for r in none_s if r["pred_label"] not in (None, "none"))
    fp_d = sum(1 for r in none_d.values() if r["pred_label"] not in (None, "none"))
    tn_s = len(none_s) - fp_s
    tn_d = len(none_d) - fp_d
    p_fpr = fisher_exact_2x2(fp_d, fp_s, tn_d, tn_s)  # 列=模型 行=误伤与否
    print(f"[FPR] sft {fp_s}/{len(none_s)} vs dpo-v2 {fp_d}/{len(none_d)} "
          f"-> Fisher p={p_fpr:.4f}")

    # ②③ McNemar: T1 档 + overall
    for scope, rows in [("T1", [r for r in sft if r["tier"] == "T1"]),
                        ("overall", sft)]:
        dmap = {r["id"]: r for r in dpo}
        b = c = 0  # b: sft错dpo对  c: sft对dpo错
        for r in rows:
            d = dmap[r["id"]]
            s_ok = r["pred_label"] == r["gold_label"]
            d_ok = d["pred_label"] == d["gold_label"]
            if not s_ok and d_ok:
                b += 1
            elif s_ok and not d_ok:
                c += 1
        p = mcnemar(b, c)
        print(f"[{scope}] fixed={b} broken={c} -> McNemar p={p:.4f}")

    print()
    if p_fpr > 0.05:
        print("结论: FPR 差异不显著（p>0.05）——红线触发在评测噪声范围内")
    else:
        print("结论: FPR 差异显著——需要继续迭代")


if __name__ == "__main__":
    main()
