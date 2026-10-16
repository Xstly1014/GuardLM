# -*- coding: utf-8 -*-
"""
M1-T5a: 三档评测集切分（必须在增强之前执行！顺序铁律见 M1 手册任务5）。

切分逻辑:
  T1 常规 (~250): 统一池按 5 类分层随机抽样
  T2 对抗:
    - SP 指令攻击风险样本 (~120): source=safety_prompts & split=attack & label!=none
    - 风险母本 (~130): 从剩余风险样本抽样；母本不进训练，
      由 augment.py 生成"评测专属变体"（训练集从未见过该母本的任何形态）
  T3 边界 (~150): 合成边界池（人审通过者）

输出:
  data/eval/t1.jsonl / t2_sp_attack.jsonl / t2_mothers.jsonl / t3.jsonl（答案键格式）
  data/interim/train_pool.jsonl（剩余训练池）

答案键格式: {id, instruction, input, gold:{label,risk,reason}, source, tier, origin_label}
"""
import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from augment import find_risk_spans  # noqa: E402

random.seed(2026)  # 切分可复现

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
LABELS = ["insult", "porn", "ads", "illegal", "none"]


def to_answer(rec, tier, extra=None):
    out = json.loads(rec["output"])
    ans = {
        "id": rec["id"],
        "instruction": rec["instruction"],
        "input": rec["input"],
        "gold": out,
        "source": rec["source"],
        "tier": tier,
        "origin_label": rec.get("origin_label", ""),
    }
    if extra:
        ans.update(extra)
    return ans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="data/interim/dedup.unified.jsonl",
                    help="去重后的统一池（含 cold + sp + synth）")
    ap.add_argument("--t1", type=int, default=250)
    ap.add_argument("--t2-sp", type=int, default=120)
    ap.add_argument("--t2-moms", type=int, default=130)
    ap.add_argument("--t3", type=int, default=150)
    ap.add_argument("--out-dir", default="data/eval")
    ap.add_argument("--train-out", default="data/interim/train_pool.jsonl")
    args = ap.parse_args()

    pool = []
    with open(os.path.join(BASE, args.pool), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                pool.append(json.loads(line))

    # 池按 label / 用途分组
    by_label = defaultdict(list)
    sp_attack_risk = []   # SP 指令攻击风险样本（T2 备选）
    synth_boundary = []   # 合成边界样本（T3 备选）
    for r in pool:
        lab = json.loads(r["output"])["label"]
        if r.get("source") == "safety_prompts" and r.get("split") == "attack" and lab != "none":
            sp_attack_risk.append(r)
        elif r.get("source") == "synth":
            synth_boundary.append(r)
        else:
            by_label[lab].append(r)

    random.shuffle(sp_attack_risk)
    random.shuffle(synth_boundary)
    for lab in LABELS:
        random.shuffle(by_label[lab])

    used_ids = set()

    # ---- T1: 分层抽样 ----
    t1 = []
    train_side = [r for lab in LABELS for r in by_label[lab]]  # 可参与 T1 抽样的全体
    # 分层配额（按池内分布）
    dist = Counter(json.loads(r["output"])["label"] for r in train_side)
    total_n = len(train_side)
    quota = {lab: round(args.t1 * dist.get(lab, 0) / total_n) for lab in LABELS}
    # 修正 rounding
    diff = args.t1 - sum(quota.values())
    for lab in sorted(LABELS, key=lambda l: -dist.get(l, 0)):
        if diff == 0:
            break
        quota[lab] += 1 if diff > 0 else -1
        diff += -1 if diff > 0 else 1
    for lab in LABELS:
        take = quota[lab]
        cnt = 0
        for r in by_label[lab]:
            if cnt >= take or r["id"] in used_ids:
                continue
            t1.append(to_answer(r, "T1"))
            used_ids.add(r["id"])
            cnt += 1

    # ---- T2: SP attack + 风险母本 ----
    t2_attack = []
    for r in sp_attack_risk[:args.t2_sp]:
        if r["id"] not in used_ids:
            t2_attack.append(to_answer(r, "T2", {"perturb": "sp_attack"}))
            used_ids.add(r["id"])

    # 母本选取：优先"含词表命中"的风险样本（它们能产生有效变形），
    # 未命中词表的风险样本兜底——T2 变体分扰动子表靠母本可变形性保证
    mom_hit, mom_rest = [], []
    for lab in ["insult", "illegal", "porn", "ads"]:
        for r in by_label[lab]:
            if r["id"] in used_ids:
                continue
            (mom_hit if find_risk_spans(r["input"]) else mom_rest).append(r)
    random.shuffle(mom_hit)
    random.shuffle(mom_rest)
    mom_pool = mom_hit + mom_rest

    t2_mothers = []
    for r in mom_pool:
        if len(t2_mothers) >= args.t2_moms:
            break
        t2_mothers.append(to_answer(r, "T2", {"perturb": "mother"}))
        used_ids.add(r["id"])

    # ---- T3: 合成边界 ----
    t3 = []
    for r in synth_boundary[:args.t3]:
        if r["id"] not in used_ids:
            t3.append(to_answer(r, "T3", {"boundary_type": r.get("type", r.get("origin_label", ""))}))
            used_ids.add(r["id"])

    # ---- 剩余训练池 ----
    train_pool = [r for r in pool if r["id"] not in used_ids]

    # ---- 落盘 ----
    out_dir = os.path.join(BASE, args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    def dump(path, records):
        with open(os.path.join(BASE, path), "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    dump(f"{args.out_dir}/t1.jsonl", t1)
    dump(f"{args.out_dir}/t2_sp_attack.jsonl", t2_attack)
    dump(f"{args.out_dir}/t2_mothers.jsonl", t2_mothers)
    dump(f"{args.out_dir}/t3.jsonl", t3)
    dump(args.train_out, train_pool)

    print(f"[split] pool={len(pool)}")
    print(f"  T1={len(t1)} ({Counter(a['gold']['label'] for a in t1)})")
    print(f"  T2 attack={len(t2_attack)} + mothers={len(t2_mothers)}")
    print(f"  T3={len(t3)} ({Counter(a['gold']['label'] for a in t3)})")
    print(f"  train_pool={len(train_pool)} "
          f"({Counter(json.loads(r['output'])['label'] for r in train_pool)})")


if __name__ == "__main__":
    main()
