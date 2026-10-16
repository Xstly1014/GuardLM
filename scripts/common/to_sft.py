# -*- coding: utf-8 -*-
"""
M2-T2: SFT 训练数据最终转换——给 instruction 尾部追加 " /no_think"。

设计（M2 手册决策三，方案 A）:
  Qwen3 思考模式默认开启，SFT 目标是稳定吐 JSON 而非推理链。
  训练样本 instruction 尾部追加 "空格+/no_think"，Harness 推理侧同样追加，
  两侧一致才能保证"训练时怎么学、推理时怎么用"。

  M1 的 assemble 产物已含最终配比（风险:none=1:3、增强变体、分层抽样），
  此脚本只做格式微调，不重组数据。

幂等: 已带后缀的行跳过，可重复执行。

用法:
  python scripts/common/to_sft.py --in data/sft/train.jsonl
"""
import argparse
import json
import os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SUFFIX = " /no_think"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default="data/sft/train.jsonl")
    args = ap.parse_args()

    path = os.path.join(BASE, args.infile)
    rows, n_added, n_skip = [], 0, 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r["instruction"].endswith(SUFFIX):
                n_skip += 1
            else:
                r["instruction"] = r["instruction"] + SUFFIX
                n_added += 1
            rows.append(r)

    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"total={len(rows)} added_suffix={n_added} already_ok={n_skip}")
    print(f"sample instruction: {rows[0]['instruction']!r}")


if __name__ == "__main__":
    main()
