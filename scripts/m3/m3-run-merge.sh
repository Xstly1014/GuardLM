#!/usr/bin/env bash
# M3-2: 合并 sft-v1 -> 注册数据集（合并完成后启动 DPO 训练）
set -e
cd /mnt/e/workspace_work/GuardLM
df -h /root | tail -1
python3 scripts/m3/m3_register_dpo.py
/root/guardlm-venv/bin/llamafactory-cli export /mnt/e/workspace_work/GuardLM/training/sft/merge-sft-v1.yaml 2>&1 | tail -6
ls /root/saves/Qwen3-1.7B/guardlm-sft-v1-merged/ | head
