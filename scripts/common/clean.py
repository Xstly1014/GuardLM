# -*- coding: utf-8 -*-
"""
M1-T1: 三源数据清洗与统一 schema。

用法:
  python scripts/common/clean.py --src cold --out data/interim/cold.unified.jsonl
  python scripts/common/clean.py --src sp   --out data/interim/sp.unified.jsonl
  python scripts/common/clean.py --src cv   --mode dpo --out data/rl/cvalues.pref.jsonl

统一 schema (alpaca 单轮):
  {
    "id":            "sp:Crimes_And_Illegal_Activities:00012",  # 全局唯一，增强溯源靠它
    "instruction":   固定审核员指令（与评测 Harness 完全一致）,
    "input":         待审文本,
    "output":        '{"label": "...", "risk": 0.9, "reason": "..."}',
    "source":        "cold" | "safety_prompts" | "cvalues",
    "origin_label": 原始标签（回查用）,
    "split":        原始 split（cold 的 train/dev/test）
  }

标签映射判例（记入 DATA_CARD）:
  - COLD: label=1 -> insult; label=0 -> none
  - SP Insult / Unfairness_And_Discrimination -> insult
  - SP Crimes_And_Illegal_Activities / Unsafe_Instruction_Topic / Inquiry_With_Unsafe_Opinion
    / Goal_Hijacking -> illegal
  - SP 混合类（Mental_Health / Physical_Harm / Privacy_And_Property）:
      关键词规则细分——命中风险意图词表 -> 对应风险类，否则 -> none
      （SP 的类型是"安全议题域"不是"违规判定"，混合类不能整类映射）
  - SP Reverse_Exposure / Prompt_Leaking: 表面无害求助/探测 -> none
    （它们攻击的是模型不是审核场景，作为待审文本本身合规）
  - SP Role_Play_Instruction: 涉色情角色 -> porn; 涉暴力极端/违法 -> illegal; 其余 -> none
  - CValues: 不进 SFT（prompt 是诱导性问题而非待审文本），
      pos_resp/neg_resp 直接构成 DPO 偏好对出口

清洗四规则: 6 < len(text) < 256; 去空/纯符号/纯 emoji; 标签缺失丢弃; 同源精确去重。
"""
import argparse
import csv
import json
import os
import random
import re
import sys
import unicodedata

random.seed(42)

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

INSTRUCTION = "你是内容安全审核员。判定以下文本的风险类别并输出 JSON。"

REASON_TPL = {
    "insult": "侮辱攻击性内容",
    "porn": "色情低俗内容",
    "ads": "广告导流内容",
    "illegal": "违法违规内容",
    "none": "未发现明显风险",
}

RISK_SCORE = {"none": 0.1, "insult": 0.9, "porn": 0.9, "ads": 0.85, "illegal": 0.95}

# ---------------- SP 混合类细分规则（判例见文件头注释） ----------------

# 自伤/自杀意图（Mental_Health 类内细分）
SELF_HARM_RE = re.compile(r"自杀|轻生|自残|割腕|安眠药.{0,6}(吃|吞|多少)|想死|去死|结束(自己|生命)|了结")

# 暴力伤害教唆（Physical_Harm 类内细分）
VIOLENCE_RE = re.compile(r"杀人|打人|揍|殴打|伤害(他|她|别)|报复|斗殴|下毒|纵火|爆炸|袭击|虐待|体罚")

# 窥探他人隐私/财产（Privacy_And_Property 类内细分）
PRIVACY_RE = re.compile(r"(他|她|别人|某人|某某|老公|老婆|对象|男友|女友|同事|老板)[^。？?]{0,20}"
                         r"(银行|账户|余额|密码|住址|身份|行踪|定位|聊天记录|通话|开房|开盒|人肉)"
                         r"|(查|查询|查到|获取|跟踪|监视)[^。？?]{0,15}(他|她|别人|某人|位置|行踪|隐私|账户)")

# Role_Play 细分
PORN_RE = re.compile(r"情妇|小三|做爱|性爱|色情|成人|撩|调情|诱惑|床|一夜情|援交|包养")
EXTREME_RE = re.compile(r"恐怖袭击|极端主义|炸弹|枪支|毒品|贩毒|邪教|颠覆")

# 纯符号/纯 emoji 判定
def is_noise(text: str) -> bool:
    t = unicodedata.normalize("NFKC", text)
    t = re.sub(r"[\s\W_]+", "", t, flags=re.UNICODE)
    # 剔除常见 emoji 区块后再看是否还有"实义字符"
    t2 = "".join(ch for ch in t if not (0x1F300 <= ord(ch) <= 0x1FAFF)
                 and not (0x2600 <= ord(ch) <= 0x27BF)
                 and not (0xFE00 <= ord(ch) <= 0xFE0F)
                 and not (0x2B00 <= ord(ch) <= 0x2BFF)
                 and not (0x1F000 <= ord(ch) <= 0x1F02F))
    return len(t2) == 0


def make_record(rec_id, text, label, source, origin_label, split=""):
    return {
        "id": rec_id,
        "instruction": INSTRUCTION,
        "input": text.strip(),
        "output": json.dumps(
            {"label": label, "risk": RISK_SCORE.get(label, 0.5), "reason": REASON_TPL.get(label, "")},
            ensure_ascii=False,
        ),
        "source": source,
        "origin_label": origin_label,
        "split": split,
    }


def sp_refine_label(sp_type: str, text: str):
    """SP 混合类/攻击类细分。返回 (guardlm_label, origin_label_detail)"""
    if sp_type == "Mental_Health":
        if SELF_HARM_RE.search(text):
            return "illegal", "Mental_Health/self_harm"
        return "none", "Mental_Health/safe_help"
    if sp_type == "Physical_Harm":
        if VIOLENCE_RE.search(text):
            return "illegal", "Physical_Harm/violence"
        return "none", "Physical_Harm/safe_tip"
    if sp_type == "Privacy_And_Property":
        if PRIVACY_RE.search(text):
            return "illegal", "Privacy_And_Property/snoop"
        return "none", "Privacy_And_Property/safe_help"
    if sp_type == "Role_Play_Instruction":
        if PORN_RE.search(text):
            return "porn", "Role_Play/adult"
        if EXTREME_RE.search(text):
            return "illegal", "Role_Play/extreme"
        return "none", "Role_Play/benign"
    return None, None


SP_TYPE_MAP = {
    # ---- typical_safety_scenarios ----
    "Insult": "insult",
    "Unfairness_And_Discrimination": "insult",
    "Crimes_And_Illegal_Activities": "illegal",
    "Mental_Health": "MIXED",
    "Physical_Harm": "MIXED",
    "Privacy_And_Property": "MIXED",
    "Ethics_And_Morality": "MIXED",
    # ---- instruction_attack_scenarios ----
    "Reverse_Exposure": "none",
    "Prompt_Leaking": "none",
    "Goal_Hijacking": "illegal",
    "Unsafe_Instruction_Topic": "illegal",
    "Inquiry_With_Unsafe_Opinion": "illegal",
    "Role_Play_Instruction": "MIXED",
}


# ---------------- 各源 parse ----------------

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_sp(args):
    """Safety-Prompts: 两个 json -> unified 记录流"""
    sp_dir = os.path.join(BASE, "data", "raw", "safety-prompts")
    for fname, split in [("typical_safety_scenarios.json", "typical"),
                         ("instruction_attack_scenarios.json", "attack")]:
        path = os.path.join(sp_dir, fname)
        if not os.path.exists(path):
            print(f"[warn] missing {path}, skip")
            continue
        data = load_json(path)
        for sp_type, items in data.items():
            base_label = SP_TYPE_MAP.get(sp_type)
            if base_label is None:
                print(f"[warn] unknown SP type: {sp_type}, skip")
                continue
            for i, it in enumerate(items):
                text = (it.get("prompt") or "").strip()
                if base_label == "MIXED":
                    label, detail = sp_refine_label(sp_type, text)
                    if label is None:
                        continue
                    origin = detail
                else:
                    label, origin = base_label, sp_type
                yield make_record(f"sp:{sp_type}:{i:05d}", text, label, "safety_prompts", origin, split)


def parse_cold(args):
    """COLD: COLDataset/{train,dev,test}.csv
    实际格式: 逗号分隔 5 列带表头 — index,split,topic,label,TEXT（CRLF 换行）
    topic ∈ {race, region, gender, qiangzhi, others}; label 0/1
    """
    cold_dir = os.path.join(BASE, "data", "raw", "cold")
    dset_dir = os.path.join(cold_dir, "COLDataset")
    if not os.path.isdir(dset_dir):
        dset_dir = cold_dir  # 兼容数据直接放仓库根
    for split in ["train", "dev", "test"]:
        path = os.path.join(dset_dir, f"{split}.csv")
        if not os.path.exists(path):
            print(f"[warn] missing {path}, skip")
            continue
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if not row or len(row) < 5:
                    continue
                if i == 0 and row[1] == "split":  # 表头
                    continue
                # 列: index, split, topic, label, TEXT
                text = row[4].strip().strip('"')
                try:
                    off = int(float(row[3]))
                except ValueError:
                    continue
                label = "insult" if off == 1 else "none"
                topic = row[2] if row[2] else "na"
                yield make_record(f"cold:{split}:{i:06d}", text, label, "cold",
                                  f"off={off};topic={topic}", split)


def parse_cv(args):
    """CValues-Comparison -> DPO 偏好对出口（不是 SFT 分类！）
    每行: {prompt, pos_resp, neg_resp, pos_type, neg_type}
    出口 schema: {prompt, chosen, rejected, chosen_type, rejected_type, source}
    """
    path = os.path.join(BASE, "data", "raw", "cvalues.jsonl")
    if not os.path.exists(path):
        print(f"[fatal] {path} not found")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            prompt = (r.get("prompt") or "").strip()
            chosen = (r.get("pos_resp") or "").strip()
            rejected = (r.get("neg_resp") or "").strip()
            if not (prompt and chosen and rejected):
                continue
            yield {
                "prompt": prompt,
                "chosen": chosen,
                "rejected": rejected,
                "chosen_type": r.get("pos_type", ""),
                "rejected_type": r.get("neg_type", ""),
                "source": "cvalues",
                "id": f"cv:{i:06d}",
            }


# ---------------- 统一清洗 ----------------

def clean_stream(stream, max_per_class):
    """清洗四规则 + 同源精确去重 + 每类限量"""
    seen = set()
    kept = []
    label_cnt = {}
    for rec in stream:
        text = rec.get("input") or rec.get("prompt", "")
        # 规则1: 长度 6 < len < 256
        if not (6 < len(text) < 256):
            continue
        # 规则2: 空/纯符号/纯 emoji
        if is_noise(text):
            continue
        # 规则3: 标签/内容缺失已在 parse 处理
        # 规则4: 同源精确去重
        key = text
        if key in seen:
            continue
        seen.add(key)
        # 规模控制
        if max_per_class:
            lab = json.loads(rec["output"])["label"] if "output" in rec else None
            if lab is not None and label_cnt.get(lab, 0) >= max_per_class:
                continue
            if lab is not None:
                label_cnt[lab] = label_cnt.get(lab, 0) + 1
        kept.append(rec)
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, choices=["cold", "sp", "cv"])
    ap.add_argument("--mode", default="sft", choices=["sft", "dpo"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-per-class", type=int, default=0,
                    help="每类最多保留条数，0=不限")
    args = ap.parse_args()

    if args.src == "cv":
        stream = parse_cv(args)
        kept = [r for r in stream if r["prompt"] and r["chosen"] and r["rejected"]]
        # DPO 出口同样做长度过滤与精确去重
        seen, dedup = set(), []
        for r in kept:
            if 6 < len(r["prompt"]) < 256 and r["prompt"] not in seen:
                seen.add(r["prompt"])
                dedup.append(r)
        kept = dedup
    else:
        stream = parse_sp(args) if args.src == "sp" else parse_cold(args)
        kept = clean_stream(stream, args.max_per_class)

    out_path = os.path.join(BASE, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for rec in kept:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 统计摘要（stdout，ASCII 兼容）
    from collections import Counter
    if args.src == "cv":
        types = Counter(r["chosen_type"] or "?" for r in kept)
        print(f"[cv-dpo] kept {len(kept)} preference pairs")
        for t, c in types.most_common(10):
            print(f"  chosen_type={t}: {c}")
    else:
        labels = Counter(json.loads(r["output"])["label"] for r in kept)
        print(f"[{args.src}] kept {len(kept)} records")
        for t, c in labels.most_common():
            print(f"  {t}: {c}")
    print(f"written -> {out_path}")


if __name__ == "__main__":
    main()
