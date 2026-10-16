#!/usr/bin/env bash
# M4-4: grpo-v1 三档评测（LoRA 链式加载: grpo-v1 adapter -> dpo-v2-merged 基座）
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python -m harness.run \
  --model /root/saves/Qwen3-1.7B/guardlm-grpo-v1 \
  --base /root/saves/Qwen3-1.7B/guardlm-dpo-v2-merged \
  --eval data/eval/ \
  --tier T1,T2,T3 --no-think \
  --out reports/grpo-v1.md \
  --tag "GRPO v1 (temp1.5 G8 beta0.04, 2400池)" \
  > logs/m4_eval_grpo_v1.log 2>&1
echo "exit=$?"
