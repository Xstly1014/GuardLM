# -*- coding: utf-8 -*-
"""M4-2: GRPO 训练 grpo-v1（TRL 0.21 GRPOTrainer + QLoRA）。

手册任务2 超参（MI300 实测表）:
  G=8（组内统计稳定）/ beta=0.04（KL 平衡点）/ lr=5e-6 / completion≤80
  起点模型: dpo-v2-merged（KL 锚 = 起点本身, peft 模式 disable_adapter 免第二份模型）

生成 batch 结构:
  per_device_train_batch_size=8 × grad_accum=8 = 64 completions = 8 prompts × G8
  2400 prompts → 300 optimizer steps / 1 epoch

五指标监控（任务3）: reward / entropy / kl / completion_len 由 TRL log;
  reward_std（组内奖励离散度 → 零优势组预警）同 log。

用法:
  python training/grpo/train_grpo.py                # 全量 1 epoch
  python training/grpo/train_grpo.py --dry-run      # 3 步链路验证
"""
import argparse
import json
import os
import sys

import torch

GRPO_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(GRPO_DIR, "..", "..")
sys.path.insert(0, GRPO_DIR)
sys.path.insert(0, ROOT)

import rewards  # noqa: E402  training/grpo/rewards.py

MODEL_PATH = "/root/saves/Qwen3-1.7B/guardlm-dpo-v2-merged"
POOL = os.path.join(ROOT, "data/rl/grpo_prompts.jsonl")
OUT = "/root/saves/Qwen3-1.7B/guardlm-grpo-v1"


def build_dataset(tokenizer):
    rows = [json.loads(l) for l in open(POOL, encoding="utf-8") if l.strip()]
    data = []
    for r in rows:
        msgs = [{"role": "user", "content": r["instruction"] + "\n" + r["input"]}]
        prompt = tokenizer.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        data.append({"prompt": prompt, "answer": json.dumps(r["answer"]),
                     "aug": r["aug"], "pool_id": r["id"]})
    from datasets import Dataset
    return Dataset.from_list(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    from datasets import Dataset
    from peft import LoraConfig
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              BitsAndBytesConfig)
    from trl import GRPOConfig, GRPOTrainer

    tok = AutoTokenizer.from_pretrained(MODEL_PATH)
    rewards.set_tokenizer(tok)  # 长度惩罚精确按 token 计

    print(f"[1/4] loading QLoRA base: {MODEL_PATH}")
    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, quantization_config=bnb, device_map={"": 0},
        attn_implementation="eager")

    # 修复 TRL 0.21 + peft 已知问题: unwrap_model_for_generation 的
    # gradient_checkpointing_disable 对 PeftModel 不生效 → 生成走 no-cache
    # checkpointing 前向 → logits nan（诊断: m4_diag_grpo_gen.sh）。
    # 方案: patch generate 全权接管——生成期间切 eval+cache+禁 ckpt，结束恢复训练态。
    from transformers import LogitsProcessorList

    class _NanSanitize:
        def __call__(self, input_ids, scores):
            return torch.nan_to_num(scores, nan=-1e9, posinf=-1e9, neginf=-1e9)

    GC_KWARGS = {"use_reentrant": False}
    _orig_generate = model.generate

    def _safe_generate(*args, **kwargs):
        gc_active = bool(getattr(model, "is_gradient_checkpointing", False))
        if gc_active:
            model.gradient_checkpointing_disable()
        old_cache = model.config.use_cache
        model.config.use_cache = True
        was_training = model.training
        model.eval()
        lp = LogitsProcessorList([_NanSanitize()] +
                                 list(kwargs.pop("logits_processor", [])))
        try:
            return _orig_generate(*args, logits_processor=lp, **kwargs)
        finally:
            model.config.use_cache = old_cache
            if gc_active:
                model.gradient_checkpointing_enable(gradient_checkpointing_kwargs=GC_KWARGS)
            if was_training:
                model.train()

    model.generate = _safe_generate

    print("[2/4] building dataset ...")
    dataset = build_dataset(tok)
    print(f"      {len(dataset)} prompts")

    # LoRA: 对齐 DPO 阶段配置（r32 α4, 从上一步最佳状态一致出发）
    peft_cfg = LoraConfig(
        r=32, lora_alpha=4, lora_dropout=0.05,
        target_modules="all-linear", task_type="CAUSAL_LM")

    print("[3/4] configuring GRPOTrainer ...")
    cfg = GRPOConfig(
        output_dir=args.out,
        per_device_train_batch_size=8,      # 8 completions / 微步
        gradient_accumulation_steps=8,     # 64 completions = 8 prompts × G8
        num_generations=8,
        max_prompt_length=512,
        max_completion_length=80,          # 手册硬上限: 防膨胀+省显存
        beta=0.04,                          # KL 平衡点（MI300 实测表）
        learning_rate=5e-6,
        num_train_epochs=1.0,
        lr_scheduler_type="constant_with_warmup",
        warmup_steps=10,
        temperature=1.5,                   # 温度探针(EXP-004): 1.0仅33%组有梯度, 1.5达50%且fmt无损
        scale_rewards=True,                # 组内 std 归一化（Dr.GRPO 坑已知，不改）
        bf16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=1,                    # GRPO 每步都要看——一步就能变脸
        save_strategy="steps",
        save_steps=50,                      # 熵坍缩回退点
        save_total_limit=3,
        report_to="tensorboard",
        seed=42,
    )
    if args.dry_run:
        cfg.max_steps = 3
        cfg.save_strategy = "no"
        args.out += "-dryrun"

    print("[4/4] training ...")
    trainer = GRPOTrainer(
        model=model,
        reward_funcs=rewards.REWARD_FUNCS,
        args=cfg,
        train_dataset=dataset,
        peft_config=peft_cfg,
    )
    trainer.train()
    if not args.dry_run:
        trainer.save_model(args.out)
        tok.save_pretrained(args.out)
    print(f"done -> {args.out}")


if __name__ == "__main__":
    main()
