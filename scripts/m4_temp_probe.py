# -*- coding: utf-8 -*-
"""M4-2b 温度探针: dry-run 暴露零优势组 0.75-1.0 + entropy 0.006（DPO 后分布过尖）。

问题: 组内 8 采样高度雷同 → 奖励全同 → 无梯度。手册处置: 升温增探索。
本脚本模拟 GRPO 真实组结构（每 prompt 采样 G=8），扫描温度，输出:
  - distinct 比: 组内不同 label 判断数 / 8（多样性）
  - 非零优势组占比: 奖励 std > 0 的组（能产生梯度的组）
  - corr 分歧组占比: 组内 label 判断不全同（有对错拉锯的组）
  - fmt/corr 均值: 高温是否把格式/正确性烧坏

选温标准: 非零优势组最大化 & 格式奖励不明显退化（<0.9 报警）。

用法:
  python scripts/m4_temp_probe.py [--n 24] [--temps 1.0 1.2 1.5]
"""
import argparse
import json
import os
import random
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "training", "grpo"))

MODEL = "/root/saves/Qwen3-1.7B/guardlm-dpo-v2-merged"
POOL = os.path.join(ROOT, "data/rl/grpo_prompts.jsonl")
G = 8  # 与 GRPOConfig.num_generations 一致


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=24, help="抽 prompt 数（对抗:常规=1:2）")
    ap.add_argument("--temps", type=float, nargs="+", default=[1.0, 1.2, 1.5])
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    import rewards
    from harness.backend import TransformersBackend

    rows = [json.loads(l) for l in open(POOL, encoding="utf-8") if l.strip()]
    rng = random.Random(args.seed)
    aug = [r for r in rows if r["aug"]]
    nor = [r for r in rows if not r["aug"]]
    n_aug = max(args.n // 3, 1)
    sample = rng.sample(aug, min(n_aug, len(aug))) + rng.sample(nor, args.n - n_aug)
    print(f"[probe] pool={len(rows)} sample={len(sample)} "
          f"(aug={sum(1 for r in sample if r['aug'])}) G={G}")

    be = TransformersBackend(model_path=MODEL)
    rewards.set_tokenizer(be.tokenizer)

    print(f"\n{'temp':>5} {'distinct':>9} {'非零std组':>9} {'corr分歧组':>9} "
          f"{'fmt均值':>8}")
    results = {}
    for t in args.temps:
        groups = []  # 每组: (rewards, labels, fmts)
        for r in sample:
            outs = be.infer([(r["instruction"], r["input"])] * G,
                            max_new_tokens=80, temperature=t,
                            top_p=1.0, top_k=0)  # 对齐 TRL GRPO 默认
            rw = rewards.total_reward(outs, [r["answer"]] * G, [r["aug"]] * G)
            fmts = rewards.format_reward(None, outs)
            labels = [rewards._parse_json(o)[0].get("label")
                      if rewards._parse_json(o)[0] else None for o in outs]
            groups.append((rw, labels, fmts))
        n = len(groups)
        distinct = sum(len(set(g[1])) for g in groups) / (n * G)
        nz_std = sum(1 for g in groups if max(g[0]) - min(g[0]) > 1e-9) / n
        corr_div = sum(1 for g in groups if len(set(g[1])) > 1) / n
        fmt_mean = sum(sum(g[2]) for g in groups) / (n * G)
        results[t] = (distinct, nz_std, corr_div, fmt_mean)
        print(f"{t:>5} {distinct:>9.2f} {nz_std:>9.0%} {corr_div:>9.0%} "
              f"{fmt_mean:>8.3f}")

    print("\n[判读] 非零std组 = 能产生梯度的组（dry-run @1.0 仅 ~25%，红线 50%）")
    cands = [t for t in args.temps if results[t][3] >= 0.9]
    best = max(cands or args.temps, key=lambda t: results[t][1])
    print(f"[结论] 建议温度: {best} "
          f"(非零std组 {results[best][1]:.0%}, fmt {results[best][3]:.3f})")


if __name__ == "__main__":
    main()
