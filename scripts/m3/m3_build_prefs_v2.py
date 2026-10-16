# -*- coding: utf-8 -*-
"""M3-4: 偏好对方向修正 —— prefs-v2.jsonl。

背景（dpo-v1 红线诊断）:
  FPR 0.71% → 3.57% 超红线，但 KL(π‖π_ref) ≈ 0 —— 不是漂移，是方向失衡:
  判定对 767 条中 chosen=风险 742 / chosen=none 25（96.7% 单向推「判风险」）。

修正（手册任务4: KL 健康区间 → 不动 β，转查数据权重）:
  E  onpolicy_fp   mining 中的 on-policy 误伤对: chosen=canon none / rejected=模型真实误伤输出
  F  none_mirror   none 正常样本镜像对: chosen=canon none / rejected=构造误伤 JSON
                   （类别按真实 FP 分布 insult 58%/illegal 38%/porn 4% 采样）

保持 β=0.1 / lr=1e-5 不变（每次只动一个变量——本版动的变量是数据权重）。

用法:
  python scripts/m3_build_prefs_v2.py --mirror 176
"""
import argparse
import json
import os
import random
from collections import Counter

random.seed(32)
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

# 真实 FP 类别分布（m3_fp_stat: insult 14 / illegal 9 / porn 1）
FP_LABELS = ["insult"] * 14 + ["illegal"] * 9 + ["porn"] * 1


def load_jsonl(path):
    with open(os.path.join(BASE, path), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def canonical_golds(sft_rows):
    by_label = {}
    for r in sft_rows:
        try:
            o = json.loads(r["output"])
        except json.JSONDecodeError:
            continue
        by_label.setdefault(o["label"], Counter())[r["output"]] += 1
    return {lab: cnt.most_common(1)[0][0] for lab, cnt in by_label.items()}


def make_pair(instruction, text, chosen, rejected, source, err_class, pid):
    ins = instruction.rstrip()
    if not ins.endswith("/no_think"):
        ins = ins + " /no_think"
    return {"instruction": ins, "input": text, "chosen": chosen,
            "rejected": rejected, "source": source,
            "err_class": err_class, "id": pid}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mirror", type=int, default=176)
    args = ap.parse_args()

    canon = canonical_golds(load_jsonl("data/sft/train.jsonl"))
    pairs = load_jsonl("data/rl/prefs.jsonl")
    existing_ids = {p["id"] for p in pairs}
    existing_texts = {p["input"] for p in pairs if p["input"]}

    mine_rows = {r["id"]: r for r in load_jsonl("data/interim/m3_mining/t1.jsonl")}
    mine_pred = load_jsonl("reports/artifacts/m3_mining.pred.jsonl")

    added = []

    # ---- E: on-policy FP 修正对（chosen=none / rejected=模型真实误伤） ----
    n_e = 0
    for p in mine_pred:
        if p["pred_label"] in (None, "none") or p["gold_label"] != "none":
            continue
        if p["id"] in existing_ids:  # v1 已收录的 fp 对不重复
            continue
        rejected = (p["raw"] or "").strip()
        if not rejected:
            continue
        m = mine_rows[p["id"]]
        added.append(make_pair(m["instruction"], m["input"],
                               canon["none"], rejected,
                               "onpolicy_fp", "fp_fix", p["id"]))
        n_e += 1
    print(f"[E onpolicy_fp] 新增 {n_e} 对")

    # ---- F: none 镜像对（模型判对的 none 样本，教「正常文本不误伤」） ----
    tn = [p for p in mine_pred
          if p["gold_label"] == "none" and p["pred_label"] == "none"
          and p["id"] not in existing_ids]
    random.shuffle(tn)
    n_f = 0
    for p in tn[:args.mirror]:
        m = mine_rows[p["id"]]
        if m["input"] in existing_texts:
            continue
        label = random.choice(FP_LABELS)
        added.append(make_pair(m["instruction"], m["input"],
                               canon["none"], canon[label],
                               "none_mirror", "fp_guard",
                               p["id"] + ":nm"))
        n_f += 1
    print(f"[F none_mirror] 新增 {n_f} 对")

    # ---- 合并 + 卫生检查 ----
    all_pairs = pairs + added
    seen_key = set()
    deduped = []
    for p in all_pairs:
        k = p["instruction"] + "\x00" + p["input"]
        if k in seen_key:
            continue
        seen_key.add(k)
        deduped.append(p)
    n_dedup = len(all_pairs) - len(deduped)

    # 泄漏检查
    eval_inputs = set()
    for f in ["t1.jsonl", "t2_variants.jsonl", "t2_sp_attack.jsonl", "t3.jsonl"]:
        for r in load_jsonl(f"data/eval/{f}"):
            eval_inputs.add(r["input"])
    leaks = [p for p in deduped if p["source"] not in ("m2_badcase",)
             and p["input"] and p["input"] in eval_inputs]
    assert not leaks, f"泄漏 {len(leaks)} 条!"

    # 长度配平
    all_r = [len(p["chosen"]) / max(len(p["rejected"]), 1) for p in deduped]
    dec = [p for p in deduped if p["source"] != "cvalues"]
    ch_none = sum(1 for p in dec if '"none"' in p["chosen"][:30])
    print(f"[hygiene] 去重 {n_dedup} 条, 总 {len(deduped)} 对, "
          f"泄漏 0, avg_len_ratio={sum(all_r)/len(all_r):.3f}")
    print(f"[direction] 判定对 {len(dec)} 中 chosen=风险 {len(dec)-ch_none} / "
          f"chosen=none {ch_none} ({ch_none/len(dec):.1%})")
    print("[sources]", dict(Counter(p["source"] for p in deduped)))

    out = os.path.join(BASE, "data/rl/prefs-v2.jsonl")
    random.shuffle(deduped)
    with open(out, "w", encoding="utf-8") as f:
        for p in deduped:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"written -> data/rl/prefs-v2.jsonl ({len(deduped)} 对)")


if __name__ == "__main__":
    main()
