# -*- coding: utf-8 -*-
"""
M1-T3: 合成样本晋升——人审通过后从 raw 池合入统一池。

流程: synthesize.py 产 raw -> 人审(sample_review.py --kind synth) -> 淘汰清单
      -> promote.py 打 GuardLM 标签 + 统一 schema -> synth.unified.jsonl
      -> m1-merge-pool.py + dedup.py + split_eval.py 全链路重跑

标签映射（边界类型 -> GuardLM 类）:
  sarcasm/insinuation -> insult; signal/softad -> ads;
  softporn/porn_direct -> porn; ads_direct -> ads
"""
import argparse
import json
import os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

INSTRUCTION = "你是内容安全审核员。判定以下文本的风险类别并输出 JSON。"

REASON_TPL = {
    "insult": "阴阳怪气/影射类侮辱内容",
    "porn": "软色情擦边内容",
    "ads": "暗号导流/软广内容",
    "illegal": "违法违规内容",
    "none": "未发现明显风险",
}
RISK_SCORE = {"none": 0.1, "insult": 0.75, "porn": 0.8, "ads": 0.75, "illegal": 0.9}

TYPE_MAP = {
    "sarcasm": "insult",
    "insinuation": "insult",
    "signal": "ads",
    "softad": "ads",
    "softporn": "porn",
    "porn_direct": "porn",
    "ads_direct": "ads",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="data/interim/synth.raw.jsonl")
    ap.add_argument("--exclude-file", default=None,
                    help="人审淘汰 id 清单（一行一个 id）")
    ap.add_argument("--out", default="data/interim/synth.unified.jsonl")
    args = ap.parse_args()

    exclude = set()
    if args.exclude_file:
        with open(os.path.join(BASE, args.exclude_file), encoding="utf-8") as f:
            exclude = {l.strip() for l in f if l.strip()}

    n_in, n_out = 0, 0
    from collections import Counter
    by_type = Counter()
    out_path = os.path.join(BASE, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(os.path.join(BASE, args.inp), encoding="utf-8") as fin, \
         open(out_path, "w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            r = json.loads(line)
            n_in += 1
            if r["id"] in exclude:
                continue
            t = r.get("type", "")
            lab = TYPE_MAP.get(t)
            if not lab:
                continue
            rec = {
                "id": r["id"],
                "instruction": INSTRUCTION,
                "input": r["input"],
                "output": json.dumps(
                    {"label": lab, "risk": RISK_SCORE[lab], "reason": REASON_TPL[lab]},
                    ensure_ascii=False),
                "source": "synth",
                "origin_label": f"synth/{t}",
                "prompt_version": r.get("prompt_version", ""),
            }
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_out += 1
            by_type[t] += 1

    print(f"[promote] {n_in} raw -> {n_out} promoted (excluded {len(exclude)})")
    print("by_type:", dict(by_type))
    print(f"written -> {out_path}")


if __name__ == "__main__":
    main()
