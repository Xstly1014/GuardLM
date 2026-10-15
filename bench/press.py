# -*- coding: utf-8 -*-
"""M6-3 压测脚本：对运行中的 vLLM 服务（OpenAI 兼容）发真实评测语料，产出容量报告。

方法纪律（M6 手册三条）：
1. 控制的是 in-flight 请求数（信号量稳态），不是连接数
2. 并发梯度按 vLLM 启动日志的 KV cache 容量定，默认 1/4/16/64
3. 防"重测虚高"：服务启动时已关 prefix caching；语料固定为评测集 prompt
   （长度分布一致），每档跑 N 轮取中位数

指标：P50/P99 E2E、TTFT P50/P99、吞吐（req/s 与 output token/s）、失败率

用法:
  python bench/press.py --endpoint http://localhost:8000/v1/chat/completions \
      --pool data/eval/t1.jsonl --concurrency 1,4,16,64 \
      --num-prompts 100 --rounds 1 -o reports/bench.md
"""
import argparse
import asyncio
import json
import math
import os
import sys
import time

import aiohttp

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from harness.backend import verdict_response_format  # noqa: E402

INSTRUCTION = "你是内容安全审核员。判定以下文本的风险类别并输出 JSON。"

RESPONSE_FORMAT = verdict_response_format()


def load_pool(pool_path, limit=0):
    """评测集 prompt 池：T1 真实分布。"""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    path = pool_path if os.path.isabs(pool_path) else os.path.join(base, pool_path)
    texts = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                ins = r.get("instruction", INSTRUCTION)
                texts.append(f"{ins}\n{r['input']}")
    if limit:
        texts = texts[:limit]
    return texts


def pct(sorted_vals, p):
    if not sorted_vals:
        return float("nan")
    idx = max(0, math.ceil(p / 100.0 * len(sorted_vals)) - 1)
    return sorted_vals[min(idx, len(sorted_vals) - 1)]


async def one_request(session, sem, text, args, results):
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": text}],
        "max_tokens": args.max_tokens,
        "temperature": 0.7,
        "top_p": 0.8,
        "stream": True,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if args.structured:
        payload["response_format"] = RESPONSE_FORMAT

    async with sem:
        t0 = time.perf_counter()
        ttft = None
        out_tokens = 0
        ok = False
        try:
            timeout = aiohttp.ClientTimeout(total=args.timeout)
            async with session.post(args.endpoint, json=payload,
                                    timeout=timeout) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    results.append({"ok": False, "err": f"HTTP {resp.status}: {body[:120]}"})
                    return
                async for line in resp.content:
                    if not line.startswith(b"data: "):
                        continue
                    data = line[6:].strip()
                    if data == b"[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("usage"):
                        out_tokens = obj["usage"].get("completion_tokens", 0)
                    choices = obj.get("choices") or []
                    if choices and ttft is None:
                        delta = choices[0].get("delta", {})
                        if delta.get("content") is not None:
                            ttft = time.perf_counter() - t0
                ok = True
        except Exception as e:  # noqa: BLE001
            results.append({"ok": False, "err": f"{type(e).__name__}: {e}"[:120]})
            return
        e2e = time.perf_counter() - t0
        results.append({"ok": ok, "e2e": e2e, "ttft": ttft,
                        "tokens": out_tokens})


async def run_round(session, texts, concurrency, args):
    sem = asyncio.Semaphore(concurrency)
    results = []
    tasks = []
    for i in range(args.num_prompts):
        text = texts[i % len(texts)]
        tasks.append(asyncio.create_task(
            one_request(session, sem, text, args, results)))
    t0 = time.perf_counter()
    await asyncio.gather(*tasks)
    wall = time.perf_counter() - t0
    return results, wall


def summarize(results, wall, concurrency, round_id):
    oks = [r for r in results if r.get("ok")]
    errs = [r for r in results if not r.get("ok")]
    e2es = sorted(r["e2e"] for r in oks)
    ttfts = sorted(r["ttft"] for r in oks if r["ttft"] is not None)
    toks = sum(r["tokens"] for r in oks)
    err_types = {}
    for r in errs:
        et = r.get("err", "?").split(":")[0]
        err_types[et] = err_types.get(et, 0) + 1
    return {
        "concurrency": concurrency, "round": round_id,
        "n_ok": len(oks), "n_err": len(errs),
        "err_types": err_types,
        "fail_rate": len(errs) / max(len(results), 1),
        "e2e_p50_ms": pct(e2es, 50) * 1000,
        "e2e_p99_ms": pct(e2es, 99) * 1000,
        "ttft_p50_ms": pct(ttfts, 50) * 1000 if ttfts else float("nan"),
        "ttft_p99_ms": pct(ttfts, 99) * 1000 if ttfts else float("nan"),
        "req_per_s": len(oks) / wall,
        "tok_per_s": toks / wall,
        "wall_s": wall,
    }


async def main_async(args):
    texts = load_pool(args.pool, args.pool_limit)
    print(f"pool={len(texts)} prompts, structured={'ON' if args.structured else 'OFF'}")

    all_stats = []
    connector = aiohttp.TCPConnector(limit=256, force_close=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        for conc in args.concurrency:
            for rnd in range(args.rounds):
                print(f"--- concurrency={conc} round={rnd+1} ---", flush=True)
                results, wall = await run_round(session, texts, conc, args)
                st = summarize(results, wall, conc, rnd + 1)
                st["raw"] = [{"ok": r.get("ok", False),
                              "e2e": round(r["e2e"], 3), "ttft": r["ttft"],
                              "tokens": r.get("tokens", 0)}
                             for r in results if "e2e" in r]
                all_stats.append(st)
                print(json.dumps({k: (round(v, 2) if isinstance(v, float) else v)
                                  for k, v in st.items()
                                  if k not in ("wall_s", "raw")},
                                 ensure_ascii=False), flush=True)

    write_report(args, all_stats)
    return all_stats


def median_rows(all_stats):
    """每档并发取各轮中位数（手册：每档跑 3 轮取中位数防波动）。"""
    by_conc = {}
    for st in all_stats:
        by_conc.setdefault(st["concurrency"], []).append(st)
    rows = []
    for conc in sorted(by_conc):
        sts = by_conc[conc]
        def med(key):
            vals = sorted(s[key] for s in sts)
            return pct(vals, 50)
        rows.append({
            "concurrency": conc,
            "e2e_p50_ms": med("e2e_p50_ms"), "e2e_p99_ms": med("e2e_p99_ms"),
            "ttft_p50_ms": med("ttft_p50_ms"), "ttft_p99_ms": med("ttft_p99_ms"),
            "req_per_s": med("req_per_s"), "tok_per_s": med("tok_per_s"),
            "fail_rate": med("fail_rate"),
            "rounds": len(sts),
        })
    return rows


def write_report(args, all_stats):
    # 原始时序 sidecar：停摆归因 / 复盘用
    raw_path = os.path.splitext(args.out)[0] + "_raw.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_stats, f, ensure_ascii=False)
    print(f"raw timeline -> {raw_path}")

    rows = median_rows(all_stats)
    lines = []
    lines.append("### 压测结果\n")
    lines.append(f"- endpoint: `{args.endpoint}`")
    lines.append(f"- model: `{args.model}`")
    lines.append(f"- pool: `{args.pool}` ({len(load_pool(args.pool, args.pool_limit))} prompts)")
    lines.append(f"- 参数: max_tokens={args.max_tokens}, temp=0.7/top_p=0.8, "
                  f"structured={'ON' if args.structured else 'OFF'}, "
                  f"rounds/conc={args.rounds}, num_prompts={args.num_prompts}")
    lines.append("- 环境: 单机 4090/24G · WSL2 · 客户端与服务同机（限制已如实记录）\n")
    lines.append("| 并发 | P50 E2E | P99 E2E | TTFT P50 | TTFT P99 | 吞吐 req/s | 输出 tok/s | 失败率 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['concurrency']} | {r['e2e_p50_ms']:.0f}ms | {r['e2e_p99_ms']:.0f}ms "
            f"| {r['ttft_p50_ms']:.0f}ms | {r['ttft_p99_ms']:.0f}ms "
            f"| {r['req_per_s']:.1f} | {r['tok_per_s']:.0f} | {r['fail_rate']:.1%} |")
    lines.append("")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"report appended -> {args.out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://localhost:8000/v1/chat/completions")
    ap.add_argument("--model", default="guardlm")
    ap.add_argument("--pool", default="data/eval/t1.jsonl")
    ap.add_argument("--pool-limit", type=int, default=0)
    ap.add_argument("--concurrency", default="1,4,16,64")
    ap.add_argument("--num-prompts", type=int, default=100)
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--max-tokens", type=int, default=64)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--structured", action="store_true", help="开启约束解码 response_format")
    ap.add_argument("--out", default="reports/bench.md")
    args = ap.parse_args()
    args.concurrency = [int(c) for c in args.concurrency.split(",") if c.strip()]
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
