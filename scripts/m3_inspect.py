# -*- coding: utf-8 -*-
"""M3-1 前置检查: CValues 原始 schema / pred.jsonl / aug 可用字段"""
import json
import os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def load(path, n=None):
    rows = []
    with open(os.path.join(BASE, path), encoding="utf-8") as f:
        for i, l in enumerate(f):
            if n and i >= n:
                break
            if l.strip():
                rows.append(json.loads(l))
    return rows


def main():
    cv = load("data/raw/cvalues.jsonl", 2000)
    keys = {}
    for r in cv:
        for k in r:
            keys[k] = keys.get(k, 0) + 1
    print("[cvalues raw] keys:", keys)

    pref = load("data/rl/cvalues.pref.jsonl", 500)
    pk = {}
    for r in pref:
        for k in r:
            pk[k] = pk.get(k, 0) + 1
    print("[cvalues.pref] keys:", pk)

    pred = load("reports/sft-v1.pred.jsonl")
    print("[pred] n=%d keys=%s" % (len(pred), list(pred[0].keys())))
    # 错误样本里 raw 字段是否有值（on-policy rejected 的来源）
    errs = [r for r in pred if r["pred_label"] != r["gold_label"]]
    no_raw = [r for r in errs if not r.get("raw")]
    fmt_err = [r for r in pred if r.get("parse_level") == "format_error"]
    print("[pred] errors=%d, errors_without_raw=%d, format_error=%d"
          % (len(errs), len(no_raw), len(fmt_err)))
    # 错误按档/扰动分布
    from collections import Counter
    print("[pred] err by tier:", Counter(r["tier"] for r in errs))
    print("[pred] err by perturb:", Counter(r.get("perturb", "") for r in errs))
    # gold=porn/ads 的错误（判例对素材）
    for r in errs[:3]:
        print("  e.g.", r["id"], r["gold_label"], "->", r["pred_label"], "|", r["raw"][:80])

    aug = load("data/interim/train_aug.jsonl", 3000)
    print("[aug] keys:", list(aug[0].keys()))
    from collections import Counter as C2
    print("[aug] modes:", C2(a.get("aug_mode") for a in aug))


if __name__ == "__main__":
    main()
