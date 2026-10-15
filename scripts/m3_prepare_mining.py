# -*- coding: utf-8 -*-
"""M3-1a: on-policy 错误挖掘——准备挖掘采样集。

M3 手册原则「on-policy 优先」: rejected 用策略模型(sft-v1)自己的真实输出，
比人工编的假想错误更贴近模型当前错误分布。M2 评测只覆盖 650 条评测集，
错误仅 134 条；本脚本从「SFT 训练未见 + 评测集未见」的池子里采样，
交给 harness 跑 sft-v1 推理挖出新的真实错误，扩充 hard negative。

组成（约 3000 条）:
  - 风险增强变体（五件套）  1400  对抗失效主力
  - 风险原文（train_pool）    700  常规漏放
  - none 原文（train_pool）   500  误伤 FP 探测
  - harmless 变体（none 增强） 400  变体上的误伤探测

排除: SFT train.jsonl 已见文本（输入串匹配）+ 评测集全部文本（防泄漏）。

输出: data/interim/m3_mining/t1.jsonl（harness 评测格式，--tier T1 直跑）
"""
import json
import os
import random

random.seed(31)
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def load_jsonl(path):
    with open(os.path.join(BASE, path), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    pool = load_jsonl("data/interim/train_pool.jsonl")
    aug = load_jsonl("data/interim/train_aug.jsonl")
    sft = load_jsonl("data/sft/train.jsonl")

    # 排除集: SFT 已见 + 评测集
    seen = {r["input"] for r in sft}
    for fname in ["t1.jsonl", "t2_variants.jsonl", "t2_sp_attack.jsonl", "t3.jsonl"]:
        for r in load_jsonl(f"data/eval/{fname}"):
            seen.add(r["input"])

    def gold_label(row):
        return json.loads(row["output"])["label"]

    # ---- 1) 风险增强变体（非 harmless 模式）----
    risky_aug = [a for a in aug
                 if a["aug_mode"] != "harmless" and a["input"] not in seen]
    harmless_aug = [a for a in aug
                    if a["aug_mode"] == "harmless" and a["input"] not in seen]
    random.shuffle(risky_aug)
    random.shuffle(harmless_aug)

    # ---- 2) 池子原文 ----
    pool_risk = [p for p in pool if gold_label(p) != "none" and p["input"] not in seen]
    pool_none = [p for p in pool if gold_label(p) == "none" and p["input"] not in seen]
    random.shuffle(pool_risk)
    random.shuffle(pool_none)

    take = {
        "risky_aug": (risky_aug, 1400),
        "pool_risk": (pool_risk, 700),
        "pool_none": (pool_none, 500),
        "harmless_aug": (harmless_aug, 400),
    }

    rows, used_inputs = [], set()
    for part, (cands, n) in take.items():
        got = 0
        for r in cands:
            if got >= n or r["input"] in used_inputs:
                continue
            used_inputs.add(r["input"])
            rows.append({
                "id": r["id"],
                "instruction": r["instruction"],
                "input": r["input"],
                "gold": json.loads(r["output"]),
                "tier": "T1",
                "perturb": r.get("aug_mode", "") if part.endswith("aug") else "",
                "source": f"mine_{part}",
            })
            got += 1
        print(f"[{part}] {got}/{n} (候选 {len(cands)})")

    random.shuffle(rows)
    out_dir = os.path.join(BASE, "data/interim/m3_mining")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "t1.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    from collections import Counter
    print(f"[mining set] total={len(rows)}")
    print("  by part:", Counter(r["source"] for r in rows))
    print("  by gold:", Counter(r["gold"]["label"] for r in rows))
    print(f"written -> data/interim/m3_mining/t1.jsonl")


if __name__ == "__main__":
    main()
