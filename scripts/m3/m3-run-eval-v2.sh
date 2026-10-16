#!/usr/bin/env bash
# M3-4: dpo-v2 三档评测（LoRA 链式加载: dpo-v2 adapter -> sft-v1-merged 基座）
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python -m harness.run \
  --model /root/saves/Qwen3-1.7B/guardlm-dpo-v2 \
  --base /root/saves/Qwen3-1.7B/guardlm-sft-v1-merged \
  --eval data/eval/ \
  --tier T1,T2,T3 --no-think \
  --out reports/dpo-v2.md \
  --tag "DPO v2 方向修正 (none_mirror+176)" \
  > logs/m3_eval_dpo_v2.log 2>&1
echo "exit=$?"
