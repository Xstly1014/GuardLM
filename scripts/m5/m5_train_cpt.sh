#!/usr/bin/env bash
# M5-2: 启动 CPT-v1 训练
# 关键: M4 升级 transformers 到 4.56.1 后超出 llamafactory 0.9.3 的 <4.53 要求,
#       用 DISABLE_VERSION_CHECK=1 绕过范围检查(实际兼容, GRPO 已验证)
# 日志: logs/m5_cpt_v1.log
set -e
cd /mnt/e/workspace_work/GuardLM

export DISABLE_VERSION_CHECK=1
export CUDA_VISIBLE_DEVICES=0

LOG=logs/m5_cpt_v1.log
mkdir -p logs
echo "[$(date '+%F %T')] CPT-v1 start" | tee -a $LOG

/root/guardlm-venv/bin/llamafactory-cli train training/cpt/cpt-v1.yaml 2>&1 | tee -a $LOG
EXIT=$?
echo "[$(date '+%F %T')] CPT-v1 exit=$EXIT" | tee -a $LOG
exit $EXIT
