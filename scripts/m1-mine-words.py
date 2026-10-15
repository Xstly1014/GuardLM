# -*- coding: utf-8 -*-
"""M1-T2: 从数据池挖掘高频风险词候选，人工筛选后回填 risk_words.json。"""
import json
import os
from collections import Counter

import jieba

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
POOL = os.path.join(BASE, "data", "interim", "train_pool.jsonl")

# 停用/中性词粗过滤
STOP_CHARS = set("的了着呢吗啊吧呀哦嘛啦是在和跟把被这那你我他她它们个也又就都还很更不没我你")
GENERIC = {"时候", "东西", "事情", "问题", "知道", "觉得", "真的", "什么", "怎么", "这样",
           "那样", "现在", "已经", "还是", "就是", "不是", "可以", "一个", "没有", "如果",
           "因为", "所以", "但是", "然后", "或者", "大家", "自己", "别人", "感觉", "认为",
           "出来", "进去", "开始", "以后", "以前", "之前", "之后", "一下", "一直", "一定"}


def mine(label, topn=60):
    words = Counter()
    with open(POOL, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            out = json.loads(rec["output"])
            if out["label"] != label:
                continue
            for w in jieba.lcut(rec["input"]):
                w = w.strip()
                if len(w) < 2 or len(w) > 4:
                    continue
                if any(c in STOP_CHARS for c in w):
                    continue
                if w in GENERIC or w.isdigit() or w.isascii():
                    continue
                words[w] += 1
    return words.most_common(topn)


if __name__ == "__main__":
    out = []
    for label in ["insult", "illegal", "porn", "ads"]:
        c = mine(label)
        out.append(f"## {label} 候选词（频次）")
        out.append(", ".join(f"{w}({n})" for w, n in c))
        out.append("")
    p = os.path.join(BASE, "reports", "m1_mined_words.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"written -> {p}")
