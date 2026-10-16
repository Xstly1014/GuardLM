#!/usr/bin/env bash
# M3-2: 启动 DPO 训练 dpo-v1（后台, 日志落盘）
cd /mnt/e/workspace_work/GuardLM
mkdir -p logs
nohup /root/guardlm-venv/bin/llamafactory-cli train \
  /mnt/e/workspace_work/GuardLM/training/dpo/dpo-v1.yaml \
  > logs/dpo-v1.log 2>&1 &
echo "dpo-v1 training started, pid=$!"
