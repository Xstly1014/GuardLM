# -*- coding: utf-8 -*-
"""M4-2a: GRPO prompt 池构建（data/rl/grpo_prompts.jsonl）。

设计（M4 手册任务2）:
  规模 2400 条，对抗:常规 = 1:2（对抗 800 + 常规 1600）
  对抗料: ① sft-v1 mining 真实错误中的变体样本（错误密度最高=组内差异=梯度）
          ② train_aug 剩余变体随机补齐
  常规料: train_pool 按 risk:none=1:3 抽样（防分布漂移，护住常规能力）
  每条带 answer 答案键 {label, risk} + aug 标记（透传给奖励函数）
  泄漏检查: 与评测集 input 严格隔离

用法:
  python scripts/m4_build_pool.py --adv 800 --reg 1600
"""
import argparse
import json
import os
import random
from collections import Counter

random.seed(44)
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
INSTR = "你是内容安全审核员。判定以下文本的风险类别并输出 JSON。 /no_think"


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def label_of(output):
    try:
        return json.loads(output)["label"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def risk_of(output):
    try:
        return float(json.loads(output)["risk"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return 0.9


def make_row(r, aug, src):
    gold = r.get("gold")
    if isinstance(gold, dict):  # mining 集 gold 为 {label, risk}
        label, risk = gold.get("label"), gold.get("risk", 0.9)
    elif isinstance(gold, str):
        label, risk = gold, (0.1 if gold == "none" else 0.9)
    else:
        label, risk = label_of(r["output"]), risk_of(r["output"])
    return {"instruction": INSTR, "input": r["input"],
            "answer": {"label": label, "risk": risk},
            "aug": aug, "source": src, "id": r["id"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adv", type=int, default=800)
    ap.add_argument("--reg", type=int, default=1600)
    ap.add_argument("--out", default="data/rl/grpo_prompts.jsonl")
    args = ap.parse_args()

    # ---- ① 对抗料: mining 错误中的变体 + aug 池补齐 ----
    mine = {r["id"]: r for r in load_jsonl("data/interim/m3_mining/t1.jsonl")}
    mine_pred = load_jsonl("reports/m3_mining.pred.jsonl")
    err_adv = []
    seen_ids = set()
    for p in mine_pred:
        wrong = p["pred_label"] != p["gold_label"]
        is_adv = bool(p.get("perturb")) or "aug" in (p.get("source") or "")
        if wrong and is_adv and p["id"] not in seen_ids:
            r = mine[p["id"]]
            # gold 在 mining 集是 gold 字段; risk 近似 0.9（风险类）/0.1（none）
            r = dict(r)
            r.setdefault("output", json.dumps(
                {"label": p["gold_label"], "risk": 0.1 if p["gold_label"] == "none" else 0.9}))
            err_adv.append(make_row(r, True, "mine_err_adv"))
            seen_ids.add(p["id"])
    print(f"[对抗料-真实错误] {len(err_adv)} 条")

    aug_pool = [r for r in load_jsonl("data/interim/train_aug.jsonl")
                if r["id"] not in seen_ids]
    # 稀缺类别（ads/porn 源数据极少）定向优先，其余随机补齐
    scarce = [r for r in aug_pool if label_of(r["output"]) in ("ads", "porn")]
    rest = [r for r in aug_pool if label_of(r["output"]) not in ("ads", "porn")]
    random.shuffle(rest)
    for r in scarce + rest:
        if len(err_adv) >= args.adv:
            break
        err_adv.append(make_row(r, True, "aug_pool"))
        seen_ids.add(r["id"])
    print(f"[对抗料-合计] {len(err_adv)} 条（真实错误 {min(318, len(err_adv))} + aug 池补齐，"
          f"含 ads/porn 稀缺变体 {sum(1 for r in err_adv if r['answer']['label'] in ('ads', 'porn'))} 条）")

    # ---- ② 常规料: train_pool 按 1:3 抽样 ----
    pool = load_jsonl("data/interim/train_pool.jsonl")
    for r in pool:
        r["_lab"] = label_of(r["output"])
    risk = [r for r in pool if r["_lab"] in ("insult", "porn", "ads", "illegal")]
    none = [r for r in pool if r["_lab"] == "none"]
    random.shuffle(risk)
    random.shuffle(none)
    n_risk = args.reg // 4          # 1:3 → 400 risk
    n_none = args.reg - n_risk      # 1200 none
    reg = [make_row(r, False, "pool_risk") for r in risk[:n_risk]] + \
          [make_row(r, False, "pool_none") for r in none[:n_none]]
    random.shuffle(reg)
    print(f"[常规料] risk {n_risk} + none {n_none} = {len(reg)}")

    # ---- 合并 + 泄漏检查 ----
    all_rows = err_adv + reg
    eval_inputs = set()
    for f in ["t1.jsonl", "t2_variants.jsonl", "t2_sp_attack.jsonl", "t3.jsonl"]:
        for r in load_jsonl(f"data/eval/{f}"):
            eval_inputs.add(r["input"])
    leaks = [r for r in all_rows if r["input"] in eval_inputs]
    assert not leaks, f"泄漏 {len(leaks)} 条!"

    # 答案键完整性
    bad = [r for r in all_rows if not r["answer"]["label"]]
    assert not bad, f"缺答案键 {len(bad)} 条"

    random.shuffle(all_rows)
    out = os.path.join(BASE, args.out)
    with open(out, "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps({k: v for k, v in r.items() if not k.startswith("_")},
                               ensure_ascii=False) + "\n")
    print(f"[out] {out} 共 {len(all_rows)} 条")
    print(f"[配比] 对抗 {len(err_adv)} : 常规 {len(reg)} = "
          f"1:{len(reg)/max(len(err_adv),1):.1f}")
    labs = Counter(r["answer"]["label"] for r in all_rows)
    print("[label dist]", dict(labs))


if __name__ == "__main__":
    main()
