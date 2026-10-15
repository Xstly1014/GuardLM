# -*- coding: utf-8 -*-
"""Harness CLI 入口。

用法:
  python -m harness.run --model /root/models/Qwen3-1.7B \
      --eval data/eval/ --tier T1,T2,T3 --no-think --out reports/base-v0.md

产出:
  ① Markdown 报告（--out）
  ② 逐条预测 .pred.jsonl（同名 .pred.jsonl，归因脚本 attribute.py 的输入）
"""
import argparse
import json
import os
import time

from .backend import TransformersBackend, VLLMBackend
from .parse import parse_pred
from .metrics import compute_metrics
from .report import render_report, write_report

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
EVAL_FILES = {
    "T1": "t1.jsonl",
    "T2": ["t2_variants.jsonl", "t2_sp_attack.jsonl"],
    "T3": "t3.jsonl",
    "P5": "probe_slang.jsonl",  # M5 黑话探针集（CPT 消融专用，20 条留出词）
}


def load_eval(eval_dir, tiers):
    rows = []
    for tier in tiers:
        spec = EVAL_FILES[tier]
        files = spec if isinstance(spec, list) else [spec]
        for fname in files:
            path = os.path.join(eval_dir, fname)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--base", default=None, help="LoRA 基座路径（默认读 adapter_config）")
    ap.add_argument("--backend", default="transformers",
                    choices=["transformers", "vllm"],
                    help="transformers=本地 GPU 加载; vllm=OpenAI 兼容服务")
    ap.add_argument("--endpoint", default="http://localhost:8000/v1",
                    help="vLLM 服务地址（--backend vllm 时生效）")
    ap.add_argument("--structured", action="store_true",
                    help="vllm 后端开启约束解码 response_format")
    ap.add_argument("--eval", default="data/eval/")
    ap.add_argument("--tier", default="T1,T2,T3")
    ap.add_argument("--no-think", action="store_true", help="instruction 尾部追加 /no_think")
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--max-new-tokens", type=int, default=64)
    ap.add_argument("--limit", type=int, default=0, help="调试用：只跑前 N 条")
    ap.add_argument("--tag", default="", help="报告标题后缀")
    args = ap.parse_args()

    tiers = [t.strip().upper() for t in args.tier.split(",") if t.strip()]
    eval_dir = os.path.join(BASE, args.eval)
    data = load_eval(eval_dir, tiers)
    if args.limit:
        data = data[:args.limit]
    print(f"eval={len(data)} tiers={tiers} model={args.model}")

    # /no_think 与训练侧 to_sft.py 完全一致：instruction 尾部追加
    if args.no_think:
        for r in data:
            if not r["instruction"].endswith("/no_think"):
                r["instruction"] = r["instruction"] + " /no_think"

    if args.backend == "vllm":
        backend = VLLMBackend(model=args.model, endpoint=args.endpoint,
                              structured=args.structured)
    else:
        backend = TransformersBackend(args.model, base_path=args.base)
    prompts = [(r["instruction"], r["input"]) for r in data]

    t0 = time.time()
    raws = backend.infer(prompts, max_new_tokens=args.max_new_tokens,
                         batch_size=args.batch_size)
    t_infer = time.time() - t0
    print(f"infer done in {t_infer:.1f}s ({len(raws) / max(t_infer, 1e-9):.1f} samples/s)")

    # 解析 + 组装 records
    records = []
    for r, raw in zip(data, raws):
        obj, level = parse_pred(raw)
        records.append({
            "id": r["id"],
            "gold_label": r["gold"]["label"],
            "pred_label": obj["label"] if obj else None,
            "pred_risk": obj["risk"] if obj else None,
            "tier": r["tier"],
            "perturb": r.get("perturb", ""),
            "parse_level": level,
            "raw": raw,
            "text": r["input"],
        })

    # 落盘 pred.jsonl（归因脚本输入）
    pred_path = os.path.splitext(args.out)[0] + ".pred.jsonl"
    os.makedirs(os.path.dirname(os.path.abspath(pred_path)), exist_ok=True)
    with open(pred_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps({
                "id": rec["id"], "gold_label": rec["gold_label"],
                "pred_label": rec["pred_label"], "parse_level": rec["parse_level"],
                "tier": rec["tier"], "perturb": rec["perturb"],
                "raw": rec["raw"][:300],
            }, ensure_ascii=False) + "\n")

    metrics = compute_metrics(records)
    badcases = [r for r in records
                if r["pred_label"] is None or r["pred_label"] != r["gold_label"]]
    badcases.sort(key=lambda r: (r["parse_level"] == "format_error",))  # 格式错误优先展示

    tier_desc = " / ".join(f"{t}:{sum(1 for r in records if r['tier'] == t)}"
                           for t in tiers)
    title = f"GuardLM 评测报告 · {os.path.splitext(os.path.basename(args.out))[0]}"
    if args.tag:
        title += f" · {args.tag}"
    meta = {
        "title": title,
        "model": args.model,
        "eval_dir": args.eval,
        "n": len(records),
        "tier_desc": tier_desc,
        "gen_params": (f"max_new_tokens={args.max_new_tokens}, temperature=0.7, "
                       f"top_p=0.8, top_k=20, batch={args.batch_size}, "
                       f"no_think={'on' if args.no_think else 'off'}, "
                       f"backend={args.backend}"
                       + (", structured=on" if args.structured else "")
                       + f", infer={t_infer:.0f}s"),
        "extra": "口径: 解析失败按判 none 计（FN），格式错误率单列",
    }
    report = render_report(meta, metrics, badcases)
    write_report(args.out, report)
    print(f"report -> {args.out}\npred -> {pred_path}")

    # 控制台摘要
    ov = metrics["overall"]
    print(f"[overall] F1={ov['F1']:.4f} FPR={ov['FPR']:.4f} "
          f"fmt_err={metrics['overall_fmt_err']:.1%} exact={metrics['overall_exact']:.1%}")
    for tname, d in metrics["tiers"].items():
        b = d["binary"]
        print(f"[{tname}] F1={b['F1']:.4f} R={b['R']:.4f} "
              f"FPR={b['FPR']:.4f} fmt_err={d['fmt_err']:.1%}")


if __name__ == "__main__":
    main()
