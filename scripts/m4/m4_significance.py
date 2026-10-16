# -*- coding: utf-8 -*-
"""M4-4: grpo-v1 vs dpo-v2 统计显著性检验（McNemar/Fisher，M3 方法论沿用）。

检验项:
  ① overall / T1 / T2 / T3: 逐样本配对 McNemar（修复 vs 回退是否对称）
  ② FPR: none 样本误伤 Fisher 精确检验
  ③ T3 回退检查（-0.92pt）: 是否在噪声范围内

判读: p > 0.05 → 差异不显著（噪声）; p <= 0.05 → 真实信号。
"""
import json
from math import comb


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def fisher_exact_2x2(a, b, c, d):
    def p_hyper(x):
        return comb(a + b, x) * comb(c + d, a + c - x) / comb(a + b + c + d, a + c)
    lo = max(0, a - d)
    hi = min(a, c)
    p_obs = p_hyper(a)
    p_val = sum(p_hyper(x) for x in range(lo, hi + 1) if p_hyper(x) <= p_obs + 1e-12)
    return min(p_val, 1.0)


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k + 1)) * (0.5 ** n) * 2
    return min(p, 1.0)


def main():
    dpo = load("reports/artifacts/dpo-v2.pred.jsonl")
    grpo = load("reports/artifacts/grpo-v1.pred.jsonl")
    gmap = {r["id"]: r for r in grpo}

    # ① McNemar 各档
    for scope, rows in [("overall", dpo), ("T1", [r for r in dpo if r["tier"] == "T1"]),
                        ("T2", [r for r in dpo if r["tier"] == "T2"]),
                        ("T3", [r for r in dpo if r["tier"] == "T3"])]:
        b = c = 0  # b: dpo错grpo对  c: dpo对grpo错
        for r in rows:
            g = gmap[r["id"]]
            d_ok = r["pred_label"] == r["gold_label"]
            g_ok = g["pred_label"] == g["gold_label"]
            if not d_ok and g_ok:
                b += 1
            elif d_ok and not g_ok:
                c += 1
        p = mcnemar(b, c)
        print(f"[{scope:>7}] fixed={b} broken={c} net={b-c:+d} -> McNemar p={p:.4f}")

    # ② FPR Fisher
    none_d = [r for r in dpo if r["gold_label"] == "none"]
    fp_d = sum(1 for r in none_d if r["pred_label"] not in (None, "none"))
    fp_g = sum(1 for r in none_d
               if gmap[r["id"]]["pred_label"] not in (None, "none"))
    tn_d, tn_g = len(none_d) - fp_d, len(none_d) - fp_g
    p_fpr = fisher_exact_2x2(fp_g, fp_d, tn_g, tn_d)
    print(f"[    FPR] dpo {fp_d}/{len(none_d)} vs grpo {fp_g}/{len(none_d)} "
          f"-> Fisher p={p_fpr:.4f}")


if __name__ == "__main__":
    main()
