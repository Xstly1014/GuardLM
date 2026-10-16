#!/usr/bin/env bash
# M5-3: sft-v2 训练（cpt-v1 起点，超参与 sft-v1 严格一致）
set -e
cd /mnt/e/workspace_work/GuardLM
export DISABLE_VERSION_CHECK=1
export CUDA_VISIBLE_DEVICES=0

LOG=logs/m5_sft_v2.log
mkdir -p logs
echo "[$(date '+%F %T')] sft-v2 (cpt 起点) start" | tee -a $LOG
/root/guardlm-venv/bin/llamafactory-cli train training/cpt/sft-v2.yaml 2>&1 | tee -a $LOG
EXIT=$?
echo "[$(date '+%F %T')] sft-v2 exit=$EXIT" | tee -a $LOG
exit $EXIT
