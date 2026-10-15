# -*- coding: utf-8 -*-
"""M5-1b: 黑话/暗语造句（手册来源②，本地基座批量生成）。

- 词表: configs/risk_words.json（risk_words 四类 + homophone 变体）
- 每词造 N 句（few-shot 提高自然度，temp=1.0 保证多样性）
- 【防泄漏】PROBE_WORDS 为任务3 黑话探针集专用词，不参与造句（手册任务3 坑表）
- 产出: data/cpt/slang.jsonl（{"text": ...}）→ 并入 m5_build_corpus.py 重跑

用法: python scripts/m5_gen_slang.py [--n 10]
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
WORDS = os.path.join(ROOT, "configs/risk_words.json")
OUT = os.path.join(ROOT, "data/cpt/slang.jsonl")

# 探针集专用词（每类 5 个，不参与造句——任务3 黑话探针集从这里出）
PROBE_WORDS = {
    "insult": ["废物", "智障", "畜生", "人渣", "疯狗"],
    "porn": ["援交", "裸聊", "打炮", "出台", "外围"],
    "ads": ["刷单", "囤货", "爆粉", "收徒", "清仓"],
    "illegal": ["冰毒", "下注", "传销", "迷药", "高利贷"],
}

FEWSHOT = """请围绕给定的关键词，写 5 句不同场景下的自然中文短句（口语化，像社交媒体评论或聊天），每句 15-40 字，必须自然包含该关键词。不要解释，直接输出 5 句话，每行一句。

关键词：加微信
加个微信聊聊呗，我这有靠谱货源。
想要优惠券的加微信xxx，免费领取限量红包。
亲，拍下后加微信发你操作视频。
兼职日结，加微信详聊，学生宝妈都可。
扫码加微信进群，每日分享内部折扣。

关键词：{word}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12, help="每词造句数（取 5 的倍数）")
    ap.add_argument("--model", default="/root/models/Qwen3-1.7B")
    args = ap.parse_args()

    sys.path.insert(0, ROOT)
    from harness.backend import TransformersBackend

    cfg = json.load(open(WORDS, encoding="utf-8"))
    words = []
    for cat, ws in cfg["risk_words"].items():
        probe = set(PROBE_WORDS.get(cat, []))
        for w in ws:
            if w not in probe and len(w) >= 2:
                words.append((cat, w))
    # homophone 变体词（更稀缺的分布，重点补）
    for base, variants in cfg.get("homophone", {}).items():
        for w in variants:
            if len(w) >= 2:
                words.append(("homophone", w))
    print(f"[词表] 造句词 {len(words)} 个（探针专用 {sum(len(v) for v in PROBE_WORDS.values())} 个已留出）")

    be = TransformersBackend(model_path=args.model)
    outs = []
    n_rounds = (args.n + 4) // 5  # 每次生成 5 句
    for i, (cat, w) in enumerate(words):
        for r in range(n_rounds):
            gens = be.infer([(FEWSHOT.format(word=w), "")], max_new_tokens=120,
                            temperature=1.0 if r else 0.8, top_p=0.9, batch_size=1)
            lines = [l.strip().lstrip("0123456789.、) ") for l in gens[0].split("\n")]
            lines = [l for l in lines if 12 <= len(l) <= 60 and w in l]
            for l in lines[:5]:
                outs.append({"text": l, "cat": cat, "word": w})
        if (i + 1) % 40 == 0:
            print(f"  进度 {i+1}/{len(words)}，累计 {len(outs)} 句")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for o in outs:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print(f"[产出] {OUT} 共 {len(outs)} 句")


if __name__ == "__main__":
    main()
