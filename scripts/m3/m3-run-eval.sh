#!/usr/bin/env bash
# M3-3: dpo-v1 三档评测（LoRA 链式加载: dpo adapter -> sft-v1-merged 基座）
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python -m harness.run \
  --model /root/saves/Qwen3-1.7B/guardlm-dpo-v1a \
  --base /root/saves/Qwen3-1.7B/guardlm-sft-v1-merged \
  --eval data/eval/ \
  --tier T1,T2,T3 --no-think \
  --out reports/dpo-v1.md \
  --tag "DPO beta=0.1 lr=1e-5 1ep" \
  > logs/m3_eval_dpo.log 2>&1
echo "exit=$?"
