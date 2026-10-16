#!/bin/bash
# M6-1: 合并 grpo-v1 -> guardlm-final（全链路终点权重）
# 用法: wsl bash /mnt/e/workspace_work/GuardLM/scripts/m6/m6-1-merge-final.sh
set -e
export LOG=/mnt/e/workspace_work/GuardLM/logs/m6-merge.log
mkdir -p "$(dirname "$LOG")"

echo "=== 磁盘 ===" | tee -a "$LOG"
df -h /root | tail -1 | tee -a "$LOG"

echo "=== 合并 grpo-v1 (base=dpo-v2-merged) -> /root/models/guardlm-final ===" | tee -a "$LOG"
# trl 0.21(M4 GRPO 所需) 与 lf 0.9.3 版本检查冲突；export 不依赖 trl 训练器，跳过检查
DISABLE_VERSION_CHECK=1 /root/guardlm-venv/bin/llamafactory-cli export \
  /mnt/e/workspace_work/GuardLM/training/deploy/merge-grpo-final.yaml 2>&1 | tail -6 | tee -a "$LOG"

echo "=== 产物 ===" | tee -a "$LOG"
ls -la /root/models/guardlm-final/ | tee -a "$LOG"
