# -*- coding: utf-8 -*-
"""M3-1b: 组装 DPO 偏好对 data/rl/prefs.jsonl。

来源设计（M3 手册任务1 决策一 + Spec t31）:
  B  m2_badcase   M2 归因表 134 条错误的复活:
                   chosen=标准 gold JSON / rejected=sft-v1 真实误判输出（on-policy）
  C  onpolicy_mine sft-v1 在 3000 条「训练未见+评测未见」样本上新挖的错误（on-policy）
  D  aug_mirror   风险变体镜像对: chosen=变体正确判定 / rejected=典型漏放判定
  A  cvalues      CValues 安全/不安全回答（NL 偏好，easy 主力 ~50%）

铁律:
  - 同链路: 分类对 instruction 与 SFT/Harness 完全一致（尾部 " /no_think"）
  - 长度配平: 同对内 chosen/rejected 长度差尽量 <30%，聚合均值比 0.8–1.2
  - 相似度过滤: CValues 剔除 pos/neg 语义几乎相同的对
  - 泄漏检查: 任何 input 不得命中评测集文本

用法:
  python scripts/m3_build_prefs.py --total 2000 --mirror 150
"""
import argparse
import difflib
import json
import os
import random
from collections import Counter

random.seed(31)
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
EVAL_FILES = ["t1.jsonl", "t2_variants.jsonl", "t2_sp_attack.jsonl", "t3.jsonl"]

# 2026-10-15 方向性人审: 剔除 3 条源数据 gold 噪声对（用户确认）
REVIEW_EXCLUDE = {
    "aug:sp:Crimes_And_Illegal_Activities:04825",  # 受害者咨询被 gold 判 illegal
    "sp:Inquiry_With_Unsafe_Opinion:03946",        # 防骗求助被 gold 判 illegal
    "aug:cold:train:010091",                        # 共情发言（含扰动词）被 gold 判 insult
}


def load_jsonl(path):
    with open(os.path.join(BASE, path), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def attribute_err(pred, gold, tier, perturb):
    """复用 attribute.py 四分类规则（返回 err_class）。"""
    if pred is None:
        return "format"
    if pred == gold:
        return None
    is_adv = perturb != ""
    if is_adv:
        return "adversarial"
    if pred == "none":
        return "miss"
    if gold == "none":
        return "fp"
    return "confusion"


def canonical_golds(sft_rows):
    """每个 label 的标准判定 JSON（SFT 数据中的多数派输出）。"""
    by_label = {}
    for r in sft_rows:
        try:
            o = json.loads(r["output"])
        except json.JSONDecodeError:
            continue
        by_label.setdefault(o["label"], Counter())[r["output"]] += 1
    canon = {}
    for lab, cnt in by_label.items():
        canon[lab] = cnt.most_common(1)[0][0]
    return canon


def make_pair(instruction, text, chosen, rejected, source, err_class, pid):
    ins = instruction.rstrip()
    if not ins.endswith("/no_think"):
        ins = ins + " /no_think"
    return {
        "instruction": ins, "input": text,
        "chosen": chosen, "rejected": rejected,
        "source": source, "err_class": err_class, "id": pid,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--total", type=int, default=2000)
    ap.add_argument("--mirror", type=int, default=150)
    args = ap.parse_args()

    # ---- 输入 ----
    sft_rows = load_jsonl("data/sft/train.jsonl")
    canon = canonical_golds(sft_rows)
    print("[canonical gold JSON]")
    for lab in sorted(canon):
        print(f"  {lab}: {canon[lab]}")

    eval_rows = {}
    for fname in EVAL_FILES:
        for r in load_jsonl(f"data/eval/{fname}"):
            eval_rows[r["id"]] = r
    eval_inputs = {r["input"] for r in eval_rows.values()}

    mine_rows = {r["id"]: r for r in load_jsonl("data/interim/m3_mining/t1.jsonl")}
    mine_pred = load_jsonl("reports/m3_mining.pred.jsonl")

    pairs = []

    # ---- B: M2 bad case 复活（含 ①②③④ 四类） ----
    sft_pred = load_jsonl("reports/sft-v1.pred.jsonl")
    n_skip = 0
    for p in sft_pred:
        ev = eval_rows.get(p["id"])
        if ev is None or p["pred_label"] == p["gold_label"]:
            continue
        rejected = (p["raw"] or "").strip()
        if not rejected:  # 输出为空无法成对
            n_skip += 1
            continue
        ec = attribute_err(p["pred_label"], p["gold_label"],
                            ev["tier"], ev.get("perturb", ""))
        # ②类别混淆在 T1 / ④边界误判在 T1/T3 —— 沿用 attribute.py 口径
        if ec is None:
            ec = "confusion"
        if p["parse_level"] == "format_error" or p["pred_label"] is None:
            ec = "format"
        elif ev["tier"] == "T3":
            ec = "boundary"
        if p["id"] in REVIEW_EXCLUDE:
            continue
        pairs.append(make_pair(ev["instruction"], ev["input"],
                               canon[ev["gold"]["label"]], rejected,
                               "m2_badcase", ec, p["id"]))
    print(f"[B m2_badcase] {sum(1 for p in pairs if p['source'] == 'm2_badcase')} 对 (跳过空输出 {n_skip})")

    # ---- C: on-policy 挖掘 ----
    n_c = 0
    for p in mine_pred:
        m = mine_rows.get(p["id"])
        if m is None or p["pred_label"] == p["gold_label"]:
            continue
        rejected = (p["raw"] or "").strip()
        if not rejected:
            continue
        ec = attribute_err(p["pred_label"], p["gold_label"],
                            "T1", p.get("perturb", ""))
        if ec is None or p["id"] in REVIEW_EXCLUDE:
            continue
        pairs.append(make_pair(m["instruction"], m["input"],
                               canon[m["gold"]["label"]], rejected,
                               "onpolicy_mine", ec, p["id"]))
        n_c += 1
    print(f"[C onpolicy_mine] {n_c} 对")
    ec_dist = Counter(p["err_class"] for p in pairs if p["source"] == "onpolicy_mine")
    print(f"  err_class: {dict(ec_dist)}")

    # ---- D: 对抗变体镜像对（模型判对的风险变体，巩固不变性） ----
    err_ids = {p["id"] for p in pairs}
    mirror_cands = [m for m in mine_rows.values()
                    if m["source"] == "mine_risky_aug" and m["id"] not in err_ids
                    and m["input"] not in eval_inputs]
    random.shuffle(mirror_cands)
    for m in mirror_cands[:args.mirror]:
        gold_out = m["gold"]  # prepare 阶段已解析为 dict
        chosen = json.dumps(gold_out, ensure_ascii=False)
        pairs.append(make_pair(m["instruction"], m["input"],
                               chosen, canon["none"],
                               "aug_mirror", "adversarial", m["id"]))
    print(f"[D aug_mirror] {sum(1 for p in pairs if p['source'] == 'aug_mirror')} 对")

    # ---- A: CValues 填充 ----
    quota_a = args.total - len(pairs)
    cv_cands = []
    seen_prompt = set()
    cv_rows = load_jsonl("data/rl/cvalues.pref.jsonl")
    random.shuffle(cv_rows)
    for ci, r in enumerate(cv_rows):
        if ci % 4000 == 0:
            print(f"  [cv scan] {ci}/{len(cv_rows)}", flush=True)
        prompt = (r["prompt"] or "").strip()
        ch, rj = (r["chosen"] or "").strip(), (r["rejected"] or "").strip()
        if not prompt or not ch or not rj:
            continue
        if prompt in seen_prompt or prompt in eval_inputs:
            continue
        # 相似度过滤: pos/neg 语义几乎相同 -> 剔除
        sm = difflib.SequenceMatcher(None, ch, rj)
        if sm.quick_ratio() > 0.95 or sm.ratio() > 0.85:
            continue
        # 长度过滤: 同对内长度比 [0.5, 2.0]，总长 <= 600 字符
        lr = len(ch) / max(len(rj), 1)
        if not (0.5 <= lr <= 2.0):
            continue
        if len(prompt) + max(len(ch), len(rj)) > 600:
            continue
        seen_prompt.add(prompt)
        cv_cands.append((r, lr))
    print(f"[A cvalues] 过滤后候选 {len(cv_cands)} (原始 {len(cv_rows)})")

    # 长度配平: 优先取对内均衡的（|log ratio| 升序），带内不足再放宽
    def ratio_band(cands, lo, hi):
        return [c for c in cands if lo <= c[1] <= hi]

    in_band = ratio_band(cv_cands, 0.7, 1.43)
    if len(in_band) >= quota_a:
        sel, rest = in_band, []
    else:
        sel = in_band
        rest = ratio_band(cv_cands, 0.5, 2.0)
        rest = [c for c in rest if c not in sel]
    sel.sort(key=lambda x: abs(__import__("math").log(x[1])))
    picked_rows = [r for r, _ in sel[:quota_a]]
    # 带内不足 -> 放宽带两指针补齐
    if len(picked_rows) < quota_a and rest:
        rest.sort(key=lambda x: x[1])
        lo, hi = 0, len(rest) - 1
        while lo <= hi and len(picked_rows) < quota_a:
            c = rest[lo] if len(picked_rows) % 2 == 0 else rest[hi]
            if len(picked_rows) % 2 == 0:
                lo += 1
            else:
                hi -= 1
            picked_rows.append(c[0])
    picked = []
    for r in picked_rows:
        pairs.append({
            "instruction": r["prompt"].rstrip() + " /no_think",
            "input": "",
            "chosen": r["chosen"], "rejected": r["rejected"],
            "source": "cvalues", "err_class": "", "id": r.get("id", ""),
        })
        picked.append(len(r["chosen"]) / max(len(r["rejected"]), 1))
    print(f"[A cvalues] 采纳 {len(picked)} 对 (配额 {quota_a}), "
          f"均比={sum(picked) / max(len(picked), 1):.3f}, "
          f"带内候选 {len(in_band)}")

    # ---- 全局卫生检查 ----
    # 去重
    seen_key = set()
    deduped = []
    for p in pairs:
        k = p["instruction"] + "\x00" + p["input"]
        if k in seen_key:
            continue
        seen_key.add(k)
        deduped.append(p)
    pairs = deduped
    # 泄漏检查（m2_badcase 按设计复用评测集错误文本, 属 Spec t31 认可的闭环, 不算泄漏）
    leaks = [p for p in pairs
             if p["source"] != "m2_badcase" and p["input"] and p["input"] in eval_inputs]
    assert not leaks, f"泄漏 {len(leaks)} 条!"
    # JSON 合法性: 判定对来源（cvalues 是自然语言回答，不适用；①格式对的 rejected 是碎 JSON，属设计）
    n_bad = 0
    for p in pairs:
        if p["source"] == "cvalues":
            continue
        try:
            json.loads(p["chosen"])
            if p["err_class"] != "format":
                json.loads(p["rejected"])
        except json.JSONDecodeError:
            n_bad += 1
    print(f"[hygiene] 去重后 {len(pairs)} 对, 判定对 JSON 非法 {n_bad} 对（应为 0）")

    # ---- 统计 ----
    random.shuffle(pairs)
    src_cnt = Counter(p["source"] for p in pairs)
    print("[sources]", dict(src_cnt))
    for src in src_cnt:
        sub = [p for p in pairs if p["source"] == src]
        ratios = [len(p["chosen"]) / max(len(p["rejected"]), 1) for p in sub]
        print(f"  {src}: n={len(sub)}, avg_len_ratio="
              f"{sum(ratios) / max(len(ratios), 1):.3f}, "
              f"pair<30%diff={sum(1 for r in ratios if 0.7 <= r <= 1.43) / len(sub):.1%}")
    all_r = [len(p["chosen"]) / max(len(p["rejected"]), 1) for p in pairs]
    print(f"[overall] avg_len_ratio={sum(all_r) / len(all_r):.3f} (DoD 要求 0.8-1.2)")

    out = os.path.join(BASE, "data/rl/prefs.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"written -> data/rl/prefs.jsonl ({len(pairs)} 对)")

    # ---- 20 条人审样本（按 source 分层） ----
    review = []
    for src in ["m2_badcase", "onpolicy_mine", "aug_mirror", "cvalues"]:
        sub = [p for p in pairs if p["source"] == src]
        review += random.sample(sub, min(5, len(sub)))
    random.shuffle(review)
    lines = ["# M3 偏好对方向性人审（20 条）", "",
             "- 审查标准: chosen 是否是正确/更优的回答; rejected 是否确实是错判或劣判",
             "- 任意一条方向反了即为不通过", ""]
    for i, p in enumerate(review, 1):
        lines.append(f"## {i}. [{p['source']}/{p['err_class'] or '-'}] `{p['id']}`")
        lines.append(f"- **input**: {p['input'][:120] if p['input'] else '(指令即问题)'}")
        lines.append(f"- **instruction**: {p['instruction'][:80]}...")
        lines.append(f"- **chosen**: {p['chosen'][:150]}")
        lines.append(f"- **rejected**: {p['rejected'][:150]}")
        lines.append("")
    rev_path = os.path.join(BASE, "reports/m3_prefs_review.md")
    with open(rev_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"review -> reports/m3_prefs_review.md ({len(review)} 条)")


if __name__ == "__main__":
    main()
