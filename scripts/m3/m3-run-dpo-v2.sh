#!/usr/bin/env bash
# M3-4: 启动 dpo-v2 训练（后台, 日志落盘）
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python scripts/m3/m3_register_dpo_v2.py || exit 1
mkdir -p logs
nohup /root/guardlm-venv/bin/llamafactory-cli train \
  /mnt/e/workspace_work/GuardLM/training/dpo/dpo-v2.yaml \
  > logs/m3_dpo_v2.log 2>&1 &
echo "dpo-v2 started, pid=$!"
