# -*- coding: utf-8 -*-
"""M3-4: KL(π_dpo ‖ π_ref) 估计——β/lr 迭代的诊断依据（手册任务4 流程）。

方法（forward KL 的蒙特卡洛估计）:
  KL(π‖π_ref) = E_{y~π(·|x)}[ log π(y|x) − log π_ref(y|x) ]
  从偏好对 prompt 采样 y（on-policy），分别计算两模型下 y 的 token 平均 logprob 差，
  换算 bits/token（1 nat = 1/ln2 bits ≈ 1.4427 bits）。

手册判读:
  KL > 10 bits/token → 漂太远 → β 降档(0.1→0.05) 或 lr 降档
  KL < 1 bit/token  → 学了个寂寞 → β 升档(0.1→0.2) 或 lr 升档
  2–8 bits/token    → 健康，不动 β 转查数据权重

用法:
  python scripts/m3_kl_estimate.py --adapter /root/saves/Qwen3-1.7B/guardlm-dpo-v1a \
      --ref /root/saves/Qwen3-1.7B/guardlm-sft-v1-merged -n 64
"""
import argparse
import json
import os

import torch

NAT2BIT = 1.4427  # 1 nat = 1/ln2 bits


def load_model(path, base_path=None, dtype=torch.bfloat16):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(path)
    tok.padding_side = "left"
    adapter_cfg = os.path.join(path, "adapter_config.json")
    if os.path.exists(adapter_cfg):
        from peft import PeftModel
        base = AutoModelForCausalLM.from_pretrained(
            base_path, torch_dtype=dtype, device_map="cuda",
            attn_implementation="eager")
        model = PeftModel.from_pretrained(base, path)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            path, torch_dtype=dtype, device_map="cuda",
            attn_implementation="eager")
    model.eval()
    return model, tok


@torch.no_grad()
def gen_samples(model, tok, prompts, max_new_tokens=64, batch_size=8,
                temperature=0.7, top_p=0.8, top_k=20):
    outs = []
    for i in range(0, len(prompts), batch_size):
        chunk = prompts[i:i + batch_size]
        texts = [tok.apply_chat_template(
            [{"role": "user", "content": p}],
            tokenize=False, add_generation_prompt=True,
            enable_thinking=False) for p in chunk]
        enc = tok(texts, return_tensors="pt", padding=True,
                  truncation=True, max_length=512).to("cuda")
        gen = model.generate(
            **enc, max_new_tokens=max_new_tokens, do_sample=True,
            temperature=temperature, top_p=top_p, top_k=top_k,
            pad_token_id=tok.pad_token_id or tok.eos_token_id)
        for j in range(len(chunk)):
            new_ids = gen[j][enc["input_ids"].shape[1]:]
            outs.append(tok.decode(new_ids, skip_special_tokens=True))
    return outs


@torch.no_grad()
def avg_logprob(model, tok, prompt, completion):
    """completion 的 token 平均 logprob（nat/token），跳过 prompt 部分。

    边界近似: prefix 以 assistant 换行结尾，与 completion 首 token 融合概率低。
    """
    prefix = tok.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=False, add_generation_prompt=True, enable_thinking=False)
    n_prefix = len(tok(prefix)["input_ids"])
    full = prefix + completion + "<|im_end|>"
    ids = tok(full, return_tensors="pt", truncation=True,
              max_length=768).to("cuda")
    input_ids = ids["input_ids"][0]
    if input_ids.shape[0] <= n_prefix + 1:
        return 0.0, 0
    logits = model(input_ids.unsqueeze(0)).logits[0]  # [T, V]
    logprobs = torch.log_softmax(logits[:-1].float(), dim=-1)  # [T-1, V]
    tgt = input_ids[1:]
    start = n_prefix - 1  # logits[start] 预测 input_ids[start+1]（completion 首个）
    idx = torch.arange(start, len(tgt))
    lp = logprobs[idx, tgt[start:]]
    return lp.mean().item(), len(idx)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--prefs", default="data/rl/prefs.jsonl")
    ap.add_argument("-n", type=int, default=64)
    args = ap.parse_args()

    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    rows = []
    with open(os.path.join(base, args.prefs), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    rows = rows[:args.n]

    print("loading policy (dpo) + ref (sft-merged), 显存两份 bf16 1.7B ≈ 7G ...")
    pi, tok = load_model(args.adapter, base_path=args.ref)
    ref, _ = load_model(args.ref)

    prompts = [(r["instruction"] + "\n" + r.get("input", "")).strip()
               for r in rows]
    print(f"generating {len(prompts)} on-policy samples from π ...")
    ys = gen_samples(pi, tok, prompts)

    diffs, ntoks = [], []
    for i, (p, y) in enumerate(zip(prompts, ys)):
        if not y.strip():
            continue
        lp_pi, n1 = avg_logprob(pi, tok, p, y)
        lp_ref, n2 = avg_logprob(ref, tok, p, y)
        if n1 and n2:
            diffs.append(lp_pi - lp_ref)  # nat/token
            ntoks.append(n1)
        if (i + 1) % 16 == 0:
            print(f"  {i + 1}/{len(prompts)} done")

    mean_diff = sum(diffs) / max(len(diffs), 1)
    kl_bits = mean_diff * NAT2BIT
    print(f"\nsamples={len(diffs)}  mean_new_tokens={sum(ntoks)/max(len(ntoks),1):.0f}")
    print(f"KL(pi_dpo || pi_ref) ≈ {mean_diff:+.4f} nat/token = {kl_bits:+.3f} bits/token")
    if kl_bits > 10:
        print("判读: KL > 10 —— 漂太远 → β 降档 0.1→0.05 或 lr 降档")
    elif kl_bits < 1:
        print("判读: KL < 1 —— 学了个寂寞 → β 升档 0.1→0.2 或 lr 升档")
    else:
        print("判读: KL ∈ (1,10) —— 接近健康区间，结合红线判断是否查数据权重")

    out = {"kl_nat_per_token": mean_diff, "kl_bits_per_token": kl_bits,
           "n_samples": len(diffs)}
    out_path = os.path.join(base, "reports/m3_kl_estimate.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
