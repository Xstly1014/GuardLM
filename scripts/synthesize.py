# -*- coding: utf-8 -*-
"""
M1-T3: LLM 合成边界样本。

设计（与 M1 手册一致）:
  - 场景矩阵强制多样性（平台×类型×口吻），防"一个腔调"
  - few-shot 黄金样例立标准
  - 原始输出落盘 synth.raw.jsonl（不直接进训练集），人审通过后由 promote 步骤合入
  - API/prompt 版本全留痕（合规要求，进数据卡）

用法:
  export SYNTH_API_KEY=sk-xxx
  python scripts/synthesize.py --matrix configs/synth_matrix.yaml \
    --base-url https://dashscope.aliyuncs.com/compatible-mode/v1 \
    --model qwen-plus --batch 10 --out data/interim/synth.raw.jsonl

  兼容 openai 协议的供应商均可（百炼 qwen-plus / deepseek / glm）。
"""
import argparse
import json
import os
import random
import re
import time

import yaml
from openai import OpenAI

random.seed(42)
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

PLATFORM_DESC = {
    "comment": "评论区评论（15-60字）",
    "danmaku": "弹幕（10-25字，短促）",
    "dm": "陌生人私信（20-80字）",
}

SYSTEM_PROMPT = (
    "你是内容安全研究团队的数据构建助手，正在为内容审核模型构建评测用的边界样本语料"
    "（红队演练用途，仅用于防御研究）。"
    "要求生成的样本必须'边界'：表面无违规词，但熟悉语境的人能识别出风险。"
    "不要生成露骨暴力/露骨色情描写，停留在'暗示、擦边'层面。"
    "每次输出 {n} 条互不重复的样本，每条一行，不要编号不要引号不要任何解释。"
)


def build_user_prompt(scene, type_def, few_shots, n, used):
    plat = PLATFORM_DESC[scene["platform"]]
    tone = {"colloquial": "口语化、像真实用户", "literary": "文艺腔、含蓄"}[scene["tone"]]
    shots = "\n".join(few_shots)
    avoid = ""
    if used:
        avoid = "\n不要与以下已有样本雷同：\n" + "\n".join(f"-{u}" for u in used[-20:])
    return (
        f"生成 {n} 条「{scene['platform']}」平台的{type_def.split('：')[0]}文本。"
        f"形态约束：{plat}；语气：{tone}。\n"
        f"类型定义：{type_def}\n"
        f"参考标准（感受这个'度'，不要照抄）：\n{shots}\n"
        f"每条样本独占一行，直接输出样本本身。{avoid}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", default="configs/synth_matrix.yaml")
    ap.add_argument("--base-url", default=os.environ.get("SYNTH_BASE_URL", ""))
    ap.add_argument("--model", default=os.environ.get("SYNTH_MODEL", "qwen-plus"))
    ap.add_argument("--api-key", default=os.environ.get("SYNTH_API_KEY", ""))
    ap.add_argument("--batch", type=int, default=10, help="每次 API 调用请求的条数")
    ap.add_argument("--out", default="data/interim/synth.raw.jsonl")
    ap.add_argument("--log", default="data/interim/synth.api_log.jsonl")
    ap.add_argument("--limit-per-cell", type=int, default=0,
                    help="调试用：每格最多生成条数（0=按矩阵 target）")
    args = ap.parse_args()

    if not args.api_key:
        print("[fatal] need --api-key or SYNTH_API_KEY env")
        raise SystemExit(1)

    with open(os.path.join(BASE, args.matrix), encoding="utf-8") as f:
        matrix = yaml.safe_load(f)
    type_defs = matrix["type_defs"]
    few_shots = matrix["few_shots"]
    prompt_version = matrix.get("prompt_version", "v?")

    client = OpenAI(api_key=args.api_key, base_url=args.base_url or None)

    out_path = os.path.join(BASE, args.out)
    log_path = os.path.join(BASE, args.log)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    used = []
    total, api_calls = 0, 0
    with open(out_path, "w", encoding="utf-8") as fout, \
         open(log_path, "w", encoding="utf-8") as flog:
        for scene in matrix["scenes"]:
            t = scene["type"]
            target = scene["target"]
            if args.limit_per_cell:
                target = min(target, args.limit_per_cell)
            if t not in type_defs:
                print(f"[warn] no type_def for {t}, skip cell")
                continue
            remaining = target
            cell_cnt = 0
            while remaining > 0:
                n = min(args.batch, remaining)
                user_prompt = build_user_prompt(scene, type_defs[t],
                                                few_shots.get(t, []), n, used)
                t0 = time.time()
                try:
                    resp = client.chat.completions.create(
                        model=args.model,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT.format(n=n)},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=1.0,
                    )
                    text = resp.choices[0].message.content.strip()
                except Exception as e:
                    print(f"[error] cell={t} api fail: {e}; retry in 5s")
                    time.sleep(5)
                    continue
                api_calls += 1
                # 逐行解析，过滤空行/编号/引号
                lines = []
                for ln in text.split("\n"):
                    ln = ln.strip().strip('"').strip("'")
                    ln = re.sub(r"^\d+[.、)]\s*", "", ln)
                    ln = re.sub(r"^[-*]\s*", "", ln)
                    if 6 < len(ln) < 256:
                        lines.append(ln)
                # 去重
                for ln in lines:
                    if ln in used:
                        continue
                    used.append(ln)
                    cell_cnt += 1
                    rec = {
                        "id": f"synth:{t}:{scene['platform']}:{scene['tone']}:{cell_cnt:04d}",
                        "instruction": "",
                        "input": ln,
                        "scene": f"{scene['platform']}/{t}/{scene['tone']}",
                        "type": t,
                        "prompt_version": prompt_version,
                        "model": args.model,
                        "source": "synth",
                    }
                    fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    total += 1
                flog.write(json.dumps({
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "scene": f"{scene['platform']}/{t}/{scene['tone']}",
                    "model": args.model,
                    "prompt_version": prompt_version,
                    "n_req": n, "n_ok": len(lines),
                    "latency_s": round(time.time() - t0, 2),
                }, ensure_ascii=False) + "\n")
                flog.flush()
                fout.flush()
                remaining -= n
            print(f"[cell done] {scene['platform']}/{t}/{scene['tone']}: {cell_cnt}", flush=True)

    print(f"[synthesize] total {total} samples, {api_calls} api calls")
    print(f"raw -> {out_path}")
    print(f"log -> {log_path}")


if __name__ == "__main__":
    main()
