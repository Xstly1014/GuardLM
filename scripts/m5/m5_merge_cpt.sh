#!/usr/bin/env bash
# M5-3: 合并 cpt-v1 LoRA → sft-v2 的起点模型
# 注意: transformers 已降级回 4.52.4（llamafactory 官方支持范围），trl 0.21 仍超范围，
#       保留 DISABLE_VERSION_CHECK=1
set -e
cd /mnt/e/workspace_work/GuardLM
export DISABLE_VERSION_CHECK=1

LOG=logs/m5_merge_cpt.log
echo "[$(date '+%F %T')] merge cpt-v1 start" | tee -a $LOG
/root/guardlm-venv/bin/llamafactory-cli export training/cpt/merge-cpt-v1.yaml 2>&1 | tee -a $LOG
echo "[$(date '+%F %T')] merge done" | tee -a $LOG
ls -la /root/saves/Qwen3-1.7B/guardlm-cpt-v1-merged/ | grep -E 'safetensors|config'
