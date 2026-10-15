# -*- coding: utf-8 -*-
"""
M1-T4b: 配比探针实验——用未微调基座模型测"判定倾向"。

设计（M1 手册任务4）:
  3 组小样本，各 200 条候选（风险:none = 1:1 / 1:3 / 1:5），
  从各组抽 50 条混合文本让基座模型批量判定，观察输出分布:
    - 若模型"全判 none" -> none 过多强化保守倾向 -> 下调
    - 若模型"全判风险" -> 风险样本主导 -> 上调 none
  记录"倾向 -> 配比"因果观察（M2 训练后回看）。

实现: transformers 直接加载 Qwen3-1.7B（WSL GPU），chat template + generate。
输出 reports/m1_probe.md。

用法:
  python scripts/ratio_probe.py --model /root/models/Qwen3-1.7B \
    --pool data/interim/train_pool.jsonl -o reports/m1_probe.md
"""
import argparse
import json
import os
import random
import re
from collections import Counter

random.seed(42)
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

INSTRUCTION = "你是内容安全审核员。判定以下文本的风险类别并输出 JSON。"
LABEL_RE = re.compile(r'"label"\s*:\s*"(\w+)"')


def build_probe_set(pool, ratio, n_probe=50):
    """按 风险:none=ratio 组装探针混合文本"""
    risks = [r for r in pool if json.loads(r["output"])["label"] != "none"]
    nones = [r for r in pool if json.loads(r["output"])["label"] == "none"]
    random.shuffle(risks)
    random.shuffle(nones)
    n_risk = round(n_probe * ratio / (1 + ratio))
    n_none = n_probe - n_risk
    picked = risks[:n_risk] + nones[:n_none]
    random.shuffle(picked)
    return picked


SAFE_HINTS = ("无风险", "安全", "正常", "none")


def parse_label(gen_text):
    """两级解析: 先试 GuardLM schema(label)，再试基座自由 schema(risk_category/risk_level)。
    目的是统计判定倾向（风险 vs none），非 schema 遵循度（后者是 SFT 后指标）。"""
    m = LABEL_RE.search(gen_text)
    if m:
        return m.group(1)
    # 基座自由 schema: risk_category / risk_level
    cat = re.search(r'"risk_category"\s*:\s*"([^"]*)"', gen_text)
    lvl = re.search(r'"risk_level"\s*:\s*"([^"]*)"', gen_text)
    if cat:
        c = cat.group(1)
        if any(h in c for h in SAFE_HINTS) or c == "无":
            return "none"
        return "risk:" + c[:12]
    if lvl:
        l = lvl.group(1)
        if l in ("无", "低", "无风险", "安全"):
            return "none"
        return "risk:lvl=" + l
    # 宽松兜底
    for lab in ["insult", "porn", "ads", "illegal", "none"]:
        if lab in gen_text:
            return lab
    return "unparsable"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="/root/models/Qwen3-1.7B")
    ap.add_argument("--pool", default="data/interim/train_pool.jsonl")
    ap.add_argument("--n-probe", type=int, default=50)
    ap.add_argument("-o", "--out", default="reports/m1_probe.md")
    args = ap.parse_args()

    pool = []
    with open(os.path.join(BASE, args.pool), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                pool.append(json.loads(line))
    print(f"pool={len(pool)}")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map="cuda")

    groups = {"A:1:1": 1.0, "B:1:3": 3.0, "C:1:5": 5.0}
    results = {}
    for gname, ratio in groups.items():
        probes = build_probe_set(pool, ratio, args.n_probe)
        dist = Counter()
        n_ok = 0
        for r in probes:
            msgs = [{"role": "user", "content": f"{INSTRUCTION}\n文本：{r['input']}"}]
            text = tok.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=True,
                enable_thinking=False)
            ids = tok(text, return_tensors="pt").to("cuda")
            with torch.no_grad():
                out = model.generate(
                    **ids, max_new_tokens=64, do_sample=False,
                    pad_token_id=tok.eos_token_id)
            gen = tok.decode(out[0][ids["input_ids"].shape[1]:],
                             skip_special_tokens=True)
            lab = parse_label(gen)
            dist[lab] += 1
            if lab != "unparsable":
                n_ok += 1
        results[gname] = {
            "dist": dict(dist),
            "n_probe": len(probes),
            "n_risk": sum(c for l, c in dist.items() if l not in ("none", "unparsable")),
            "n_none": dist.get("none", 0),
            "unparsable": dist.get("unparsable", 0),
        }
        print(f"[{gname}] {dict(dist)}")

    # ---- 报告 ----
    rep = ["# M1 配比探针实验报告", "",
           f"- 基座模型: 未微调 {os.path.basename(args.model)}",
           f"- 每组探针: {args.n_probe} 条混合文本（比例组合见下）",
           f"- 目的: 观察基座判定倾向，为 M2 训练配比提供因果证据",
           "",
           "| 组 | 风险:none | 风险判定数 | none 判定数 | 无法解析 | 判定分布 |",
           "|---|---|---|---|---|---|"]
    for g, r in results.items():
        rep.append(f"| {g} | {g.split(':')[1]} | {r['n_risk']} | {r['n_none']} | "
                   f"{r['unparsable']} | {r['dist']} |")
    rep += ["", "## 结论", "",
            "<!-- 手写结论：例如 '组C 出现判定塌缩为 none 的倾向，故 M2 拟用组B 的 1:3 配比' -->"]

    rp = os.path.join(BASE, args.out)
    os.makedirs(os.path.dirname(rp), exist_ok=True)
    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(rep) + "\n")
    print(f"report -> {rp}")


if __name__ == "__main__":
    main()
