#!/usr/bin/env bash
# M3-1a: sft-v1 on-policy 错误挖掘（3000 条未见样本）
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python -m harness.run \
  --model /root/saves/Qwen3-1.7B/guardlm-sft-v1 \
  --eval data/interim/m3_mining/ \
  --tier T1 --no-think \
  --out reports/m3_mining.md \
  --tag "on-policy mining (sft-v1)" \
  > logs/m3_mining.log 2>&1
echo "exit=$?"
