# -*- coding: utf-8 -*-
"""M1-T1: 探查原始数据源结构（类型分布/条数/字段），输出到 UTF-8 文件供 review。"""
import json
import io
import os

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
OUT = []

def w(s=""):
    OUT.append(str(s))

def inspect_safety_prompts():
    sp_dir = os.path.join(RAW, "safety-prompts")
    if not os.path.isdir(sp_dir):
        w("[skip] safety-prompts not found")
        return
    for fname in ["typical_safety_scenarios.json", "instruction_attack_scenarios.json"]:
        path = os.path.join(sp_dir, fname)
        if not os.path.exists(path):
            w(f"[skip] {fname} missing")
            continue
        w(f"\n===== {fname} =====")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        w(f"top-level keys ({len(data)}): {list(data.keys())}")
        for k, items in data.items():
            n = len(items)
            # 统计字段与样例
            keys0 = list(items[0].keys()) if items else []
            lens = [len(it.get("prompt", "")) for it in items]
            w(f"  {k}: {n} items, fields={keys0}, prompt len min/avg/max = "
              f"{min(lens)}/{sum(lens)//max(n,1)}/{max(lens)}")
        # 每个大类抽 2 条样例
        w("  --- samples ---")
        for k, items in list(data.items())[:30]:
            for it in items[:2]:
                p = it.get("prompt", "").replace("\n", " ")[:60]
                w(f"  [{k}] prompt: {p}")

def inspect_cold():
    cold_dir = os.path.join(RAW, "cold")
    if not os.path.isdir(cold_dir):
        w("\n[skip] cold not found")
        return
    w("\n===== COLD =====")
    for root, dirs, files in os.walk(cold_dir):
        for f in files:
            w(f"  file: {os.path.join(root, f).replace(RAW, '')} ({os.path.getsize(os.path.join(root, f))} bytes)")
    # 尝试读 csv
    import csv as _csv
    for split in ["train", "dev", "test"]:
        p = os.path.join(cold_dir, "dataset", f"{split}.csv")
        if not os.path.exists(p):
            continue
        cnt, pos, neg = 0, 0, 0
        sample = []
        with open(p, encoding="utf-8") as f:
            reader = _csv.reader(f, delimiter="\t")
            for row in reader:
                if not row:
                    continue
                cnt += 1
                if len(sample) < 3:
                    sample.append(row)
                # 最后一列是 label
                try:
                    if int(float(row[-1])) == 1:
                        pos += 1
                    else:
                        neg += 1
                except Exception:
                    pass
        w(f"  {split}.csv: {cnt} rows, label=1(offensive): {pos}, label=0: {neg}")
        for s in sample:
            w(f"    row({len(s)} cols): {[c[:40] for c in s]}")

def inspect_cvalues():
    p = os.path.join(RAW, "cvalues.jsonl")
    if not os.path.exists(p):
        w("\n[skip] cvalues.jsonl not found yet")
        return
    w("\n===== CValues =====")
    cnt = 0
    first = None
    with open(p, encoding="utf-8") as f:
        for line in f:
            if first is None:
                first = json.loads(line)
            cnt += 1
    w(f"  total {cnt} rows")
    w(f"  fields: {list(first.keys())}")
    for k, v in first.items():
        w(f"  {k}: {str(v)[:80]}")

if __name__ == "__main__":
    inspect_safety_prompts()
    inspect_cold()
    inspect_cvalues()
    out_path = os.path.join(RAW, "_inspect.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(OUT))
    print(f"written {out_path}")
