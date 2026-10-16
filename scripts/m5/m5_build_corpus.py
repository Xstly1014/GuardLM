# -*- coding: utf-8 -*-
"""M5-1: CPT 语料构建（四来源 + 7:3 配比）。

来源（手册任务1）:
  ① 违规案例描述语料（主料）: interim/dedup.unified.jsonl 的 input 字段 + COLD 原始 TEXT 列全量
     ——纯文本无 QA 结构；【泄漏防线】排除 data/eval/*.jsonl 出现过的全部文本（M1 隔离纪律）
  ② 黑话/暗语造句: m5_gen_slang.py 产出 data/cpt/slang.jsonl（基座造句 + 人工抽检）
  ③ 法规与标准文本: 内置摘录（公开法规核心条款，占比控制在领域 20% 内——远低于）
  ④ 通用 replay: raw/cvalues.jsonl 正例文本（近似通用中文；理想为 CLUE 级语料，DATA_CARD 记录近似）

配比: 领域:通用 = 7:3（工程惯例起点）
产出: data/cpt/cpt_corpus.jsonl（llamafactory stage:pt 格式 {"text": ...}）+ 统计摘要

用法: python scripts/m5_build_corpus.py
"""
import argparse
import csv
import json
import os
import random
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
DEDUP = os.path.join(ROOT, "data/interim/dedup.unified.jsonl")
CVALUES = os.path.join(ROOT, "data/raw/cvalues.jsonl")
SLANG = os.path.join(ROOT, "data/cpt/slang.jsonl")
OUT = os.path.join(ROOT, "data/cpt/cpt_corpus.jsonl")

# ③ 法规与标准文本摘录（公开法规核心条款，用于审核术语正式表达语境）
REGULATION = [
    "《网络信息内容生态治理规定》鼓励制作、复制、发布含有正能量、宣传社会主义核心价值观的内容；"
    "不得制作、复制、发布含有淫秽色情、低俗庸俗、赌博暴力、凶杀恐怖等法律法规禁止的内容。"
    "网络信息内容服务平台应当建立信息发布审核制度，健全人工复核机制，对违法信息及时采取处置措施。",
    "《网络信息内容生态治理规定》要求网络信息内容服务平台在首页、热点版块等重点环节管理中，"
    "加强对算法推荐的管理，优化算法推荐机制，防范和抵制流量造假、深度伪造等行为。"
    "平台应当配备与服务规模相适应的审核人员，建立健全审核标准与培训制度。",
    "《中华人民共和国网络安全法》规定，任何个人和组织不得利用网络从事危害国家安全、荣誉和利益，"
    "煽动颠覆国家政权、推翻社会主义制度，煽动分裂国家、破坏国家统一，宣扬恐怖主义、极端主义，"
    "宣扬民族仇恨、民族歧视，传播暴力、淫秽色情信息，编造、传播虚假信息扰乱经济秩序和社会秩序等行为。",
    "内容安全审核实务中，常见违规类别包括：涉政有害、色情低俗、暴恐血腥、赌博诈骗、毒品危化、"
    "网络谣言、侮辱谩骂、垃圾营销广告、侵犯个人隐私、未成年保护违规。"
    "低俗内容指带有性暗示、软色情擦边但未达淫秽标准的边缘内容；引战内容指挑动对立、地域攻击、性别对立等煽动性言论。",
    "平台内容安全标准通常将风险等级划分为：低危（正常内容或轻微不当）、中危（违规倾向明显，"
    "建议限流或删除）、高危（明确违法违规，删除并视情况封禁账号、上报）。"
    "黑灰产常见对抗手段包括：谐音字、拼音缩写、拆字变形、同形字替换、表情符号插入、隐语暗语等变体表达。",
]

QA_MARK = re.compile(r"^(问[:：]|答[:：]|Q[:：]|A[:：]|用户[:：]|助手[:：])", re.M)


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_eval_texts():
    """泄漏防线: eval 全量文本（含 T1/T2/T3 原文与母本），CPT 语料一律排除。"""
    texts = set()
    edir = os.path.join(ROOT, "data/eval")
    for fn in os.listdir(edir):
        if fn.endswith(".jsonl"):
            for r in load_jsonl(os.path.join(edir, fn)):
                t = (r.get("input") or "").strip()
                if t:
                    texts.add(t)
    return texts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    eval_texts = load_eval_texts()
    print(f"[泄漏防线] eval 文本 {len(eval_texts)} 条，将从领域主料中排除")

    def clean(t):
        t = t.strip()
        if len(t) < 20 or len(t) > 3000:
            return None
        if QA_MARK.search(t):
            return None
        if t in eval_texts:
            return None
        return t

    # ① 领域主料 a: dedup input 纯文本
    domain_docs, seen, n_skip = [], set(), 0
    for r in load_jsonl(DEDUP):
        t = clean(r.get("input") or "")
        if not t:
            n_skip += 1
            continue
        key = t[:64]
        if key in seen:
            n_skip += 1
            continue
        seen.add(key)
        domain_docs.append(t)
    print(f"[主料a] dedup input 有效文档 {len(domain_docs)}（跳过 {n_skip} 过短/长/泄漏/QA残留）")

    # ① 领域主料 b: COLD 原始 TEXT 列全量（train+dev+test，eval 文本已排除）
    csv.field_size_limit(sys.maxsize)
    n_cold = 0
    for split in ["train", "dev", "test"]:
        p = os.path.join(ROOT, f"data/raw/cold/COLDataset/{split}.csv")
        with open(p, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                t = clean(row.get("TEXT") or "")
                if t and t[:64] not in seen:
                    seen.add(t[:64])
                    domain_docs.append(t)
                    n_cold += 1
    print(f"[主料b] COLD 原始 TEXT 新增 {n_cold} 篇（未入 dedup 池部分）")

    # ② 黑话造句（若已生成）
    slang_docs = []
    if os.path.exists(SLANG):
        for r in load_jsonl(SLANG):
            t = (r.get("text") or r.get("sentence") or "").strip()
            if len(t) >= 10:
                slang_docs.append(t)
    print(f"[黑话] 造句 {len(slang_docs)} 条")

    # ③ 法规摘录
    reg_docs = list(REGULATION)
    print(f"[法规] 摘录 {len(reg_docs)} 段")

    # ④ 通用 replay: CValues 正例文本（pos_resp）
    general_docs = []
    for r in load_jsonl(CVALUES):
        t = (r.get("pos_resp") or "").strip()
        if len(t) >= 30:
            general_docs.append(t)
    print(f"[通用] CValues 正例文本 {len(general_docs)} 条")

    # 配比: 领域 7 : 通用 3；领域全量保留（数据源全量即此，量级如实入卡）
    domain_all = domain_docs + slang_docs + reg_docs
    domain_b = sum(len(s.encode('utf-8')) for s in domain_all)
    general_budget = int(domain_b * 3 / 7)
    rng.shuffle(general_docs)
    gen_sel, acc = [], 0
    for t in general_docs:
        b = len(t.encode('utf-8'))
        if acc + b > general_budget:
            break
        gen_sel.append(t)
        acc += b

    # 汇总输出（打乱顺序，领域与通用混流）
    corpus = domain_all + gen_sel
    rng.shuffle(corpus)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for t in corpus:
            f.write(json.dumps({"text": t}, ensure_ascii=False) + "\n")

    n_char = sum(len(t) for t in corpus)
    stats = {
        "总文档": len(corpus),
        "总字符": n_char,
        "领域文档": len(domain_all),
        "领域 MB": round(domain_b / 1048576, 2),
        "  主料(违规案例)": f"{len(domain_docs)} 篇",
        "  黑话造句": f"{len(slang_docs)} 条",
        "  法规摘录": f"{len(reg_docs)} 段",
        "通用文档(replay)": len(gen_sel),
        "通用 MB": round(acc / 1048576, 2),
        "配比(领域:通用)": "7:3",
        "泄漏防线": "eval 全量文本已排除（含 T2 母本）",
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    with open(os.path.join(ROOT, "data/cpt/corpus_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"[产出] {OUT}")


if __name__ == "__main__":
    main()
