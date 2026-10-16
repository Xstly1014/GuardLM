# -*- coding: utf-8 -*-
"""
M1-T2: 对抗增强五件套——拼音/谐音/emoji符号/拆字/繁体。

设计原则（与 M1 手册一致）:
  1) 只对风险样本（label != none）做变形; none 样本按 --none-ratio 概率加"无害扰动"
     （插入空格/标点），打破"变形=危险"的伪规律，防止 FPR 虚高
  2) 每条样本随机选 1-2 种扰动，不做全叠加（对抗强度控制）
  3) 扰动只作用于风险词表命中的片段（拼音/谐音/emoji/拆字），繁体除外（全文转换语义无损）
  4) 增强样本继承原标签，source=aug，origin_id 指回母本（任务5隔离校验靠它）

用法:
  python scripts/common/augment.py \
    --in  data/interim/cold.unified.jsonl \
    --out data/interim/cold.aug.jsonl \
    --modes pinyin,homophone,emoji,split,fan \
    --ratio 0.5 --none-ratio 0.07
"""
import argparse
import json
import os
import random
import re

from pypinyin import lazy_pinyin, Style
from opencc import OpenCC

random.seed(42)
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

with open(os.path.join(BASE, "configs", "risk_words.json"), encoding="utf-8") as f:
    VOCAB = json.load(f)

RISK_WORDS = sorted({w for words in VOCAB["risk_words"].values() for w in words},
                    key=len, reverse=True)  # 长词优先命中
HOMOPHONE = VOCAB["homophone"]
SPLIT_MAP = {k: v for k, v in VOCAB["split"].items() if k != v}
SYMBOLS = VOCAB["symbols"]
CC = OpenCC("s2t")


def find_risk_spans(text):
    """返回文本中命中的风险词 span 列表 [(start, end, word)]"""
    spans = []
    for w in RISK_WORDS:
        start = 0
        while True:
            i = text.find(w, start)
            if i < 0:
                break
            spans.append((i, i + len(w), w))
            start = i + len(w)
    # 去重叠 span（保留长的）
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    chosen, last_end = [], -1
    for s in spans:
        if s[0] >= last_end:
            chosen.append(s)
            last_end = s[1]
    return chosen


def perturb_pinyin(text, spans):
    """命中词 -> 全拼或首字母（随机）。"""
    out, prev = [], 0
    for s, e, w in spans:
        out.append(text[prev:s])
        py = lazy_pinyin(w)
        if random.random() < 0.5:
            out.append("".join(py))          # 全拼: 微信 -> weixin
        else:
            out.append("".join(p[0] for p in py))  # 首字母: 微信 -> wx
        prev = e
    out.append(text[prev:])
    return "".join(out)


def perturb_homophone(text, spans):
    """命中词表登记词 -> 随机谐音变体；未登记词尝试单字谐音。"""
    out, prev, hit = [], 0, False
    for s, e, w in spans:
        out.append(text[prev:s])
        rep = None
        if w in HOMOPHONE:
            rep = random.choice(HOMOPHONE[w])
        else:
            for i, ch in enumerate(w):
                if ch in HOMOPHONE:
                    rep = w[:i] + random.choice(HOMOPHONE[ch]) + w[i + 1:]
                    break
        if rep is None:
            rep = w
        else:
            hit = True
        out.append(rep)
        prev = e
    out.append(text[prev:])
    return "".join(out) if hit else None


def perturb_emoji(text, spans):
    """命中词内部随机插入符号。"""
    out, prev = [], 0
    for s, e, w in spans:
        out.append(text[prev:s])
        parts = list(w)
        k = random.randint(1, max(len(parts) - 1, 1))
        idxs = sorted(random.sample(range(1, len(parts)), min(k, max(len(parts) - 1, 0)))) if len(parts) > 1 else []
        buf = [parts[0]]
        for i in range(1, len(parts)):
            if i in idxs:
                buf.append(random.choice(SYMBOLS))
            buf.append(parts[i])
        out.append("".join(buf))
        prev = e
    out.append(text[prev:])
    return "".join(out)


def perturb_split(text, spans):
    """命中词中的可拆字 -> 部件。"""
    out, prev, hit = [], 0, False
    for s, e, w in spans:
        out.append(text[prev:s])
        rep = "".join(SPLIT_MAP.get(ch, ch) for ch in w)
        if rep != w:
            hit = True
        out.append(rep)
        prev = e
    out.append(text[prev:])
    return "".join(out) if hit else None


def perturb_fan(text, spans):
    """繁体：全文 s2t（语义无损，不限于风险词）。"""
    return CC.convert(text)


PERTURBERS = {
    "pinyin": perturb_pinyin,
    "homophone": perturb_homophone,
    "emoji": perturb_emoji,
    "split": perturb_split,
    "fan": perturb_fan,
}


def harmless_perturb(text):
    """none 样本的无害扰动：随机位置插入空格/标点。"""
    if len(text) < 8:
        return text
    out = list(text)
    n = random.randint(1, 2)
    for _ in range(n):
        i = random.randint(2, len(out) - 2)
        out.insert(i, random.choice([" ", "，", "。"]))
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--modes", default="pinyin,homophone,emoji,split,fan")
    ap.add_argument("--ratio", type=float, default=0.5,
                    help="每条风险样本生成变体的概率")
    ap.add_argument("--none-ratio", type=float, default=0.07,
                    help="none 样本加无害扰动的比例（5-10%）")
    ap.add_argument("--max-modes-per-sample", type=int, default=1,
                    help="每条样本叠加的扰动种数（1-2，防过度变形）")
    args = ap.parse_args()

    modes = [m.strip() for m in args.modes.split(",") if m.strip() in PERTURBERS]

    in_path = os.path.join(BASE, args.inp)
    out_path = os.path.join(BASE, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    stats = {"risk_in": 0, "none_in": 0, "risk_aug": 0, "none_aug": 0,
             "by_mode": {}, "by_label": {}}
    n_out = 0
    with open(in_path, encoding="utf-8") as fin, \
         open(out_path, "w", encoding="utf-8") as fout:
        for line in fin:
            rec = json.loads(line)
            label = json.loads(rec["output"])["label"]
            text = rec["input"]

            if label == "none":
                stats["none_in"] += 1
                if random.random() >= args.none_ratio:
                    continue
                new_text = harmless_perturb(text)
                if new_text == text:
                    continue
                mode = "harmless"
                stats["none_aug"] += 1
            else:
                stats["risk_in"] += 1
                if random.random() >= args.ratio:
                    continue
                spans = find_risk_spans(text)
                k = min(args.max_modes_per_sample, len(modes))
                chosen = random.sample(modes, k)
                new_text = text
                mode = "+".join(chosen)
                for m in chosen:
                    fn = PERTURBERS[m]
                    if m == "fan":
                        new_text = fn(new_text, None)
                    else:
                        if not spans:
                            new_text = None
                            break
                        new_text = fn(new_text, spans)
                    if not new_text or new_text == text:
                        new_text = None
                        break
                if not new_text or new_text == text:
                    continue
                stats["risk_aug"] += 1
                stats["by_label"][label] = stats["by_label"].get(label, 0) + 1

            stats["by_mode"][mode] = stats["by_mode"].get(mode, 0) + 1
            aug = {
                "id": f"aug:{rec['id']}",
                "instruction": rec["instruction"],
                "input": new_text,
                "output": rec["output"],  # 继承母本标签与风险分
                "source": "aug",
                "origin_id": rec["id"],
                "origin_label": rec.get("origin_label", ""),
                "aug_mode": mode,
            }
            fout.write(json.dumps(aug, ensure_ascii=False) + "\n")
            n_out += 1

    print(f"[augment] risk_in={stats['risk_in']} -> risk_aug={stats['risk_aug']}, "
          f"none_in={stats['none_in']} -> none_aug={stats['none_aug']}, total_out={n_out}")
    print("by_mode:", json.dumps(stats["by_mode"], ensure_ascii=False))
    print("by_label:", json.dumps(stats["by_label"], ensure_ascii=False))
    print(f"written -> {out_path}")


if __name__ == "__main__":
    main()
