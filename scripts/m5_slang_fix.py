# -*- coding: utf-8 -*-
"""M5-1b 补丁: 黑话造句质量修复。

问题（抽检 30 句实测）: 原始词造句自然，但 homophone 变体词按字面义造句大量语境错位
（"剑人组队打游戏"/"范罪的优惠活动"）——基座不认识变体的黑话语义。手册坑表第 1 条 fallback：
"仍差的词直接用词表条目+拼接模板，别硬造"。

修复方案（更优的拼接）: 变体句 = 含原词的自然句做同位替换——
与 M1 五件套 homophone 扰动同构，天然保证语境正确：
  "想约炮的加微信" → "想约泡的加薇心"

处理:
  ① 丢弃 cat=homophone 的直接造句（错位率高）
  ② 对含 base 词的自然句，替换出每个 variant 各 2 句
  ③ 保留全部原始词造句（自然度达标）
"""
import json
import os
import random

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "data/cpt/slang.jsonl")
WORDS = os.path.join(ROOT, "configs/risk_words.json")
rng = random.Random(42)


def main():
    rows = [json.loads(l) for l in open(SRC, encoding="utf-8") if l.strip()]
    cfg = json.load(open(WORDS, encoding="utf-8"))

    kept = [r for r in rows if r["cat"] != "homophone"]
    dropped = len(rows) - len(kept)
    print(f"[①] 保留原始词造句 {len(kept)}，丢弃变体直接造句 {dropped}")

    # ② 变体替换: base 词句 → variant 句
    by_word = {}
    for r in kept:
        by_word.setdefault(r["word"], []).append(r["text"])
    repl = []
    for base, variants in cfg.get("homophone", {}).items():
        sents = by_word.get(base, [])
        for v in variants:
            take = rng.sample(sents, min(2, len(sents))) if sents else []
            for s in take:
                if base in s:
                    repl.append({"text": s.replace(base, v), "cat": "homophone", "word": v})
    print(f"[②] 变体替换句 {len(repl)} 条（{len(cfg.get('homophone', {}))} 个 base 词）")

    out = kept + repl
    rng.shuffle(out)
    with open(SRC, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[产出] {SRC} 共 {len(out)} 条")


if __name__ == "__main__":
    main()
