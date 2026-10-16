#!/usr/bin/env bash
# M5-2: CPT 训练健康检查（loss / grad_norm / GPU）
LOG=/mnt/e/workspace_work/GuardLM/logs/m5_cpt_v1.log

echo "=== loss 抽样（每5条取1）==="
grep -o "'loss': [0-9.]*" $LOG | awk 'NR%5==1' | tail -12

echo "=== 最近 grad_norm ==="
grep -o "'grad_norm': [0-9.]*" $LOG | tail -3

echo "=== eval loss（如有）==="
grep -o "'eval_loss': [0-9.]*" $LOG | tail -5

echo "=== GPU ==="
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader

echo "=== 进度 ==="
tail -1 $LOG | tr '\r' '\n' | tail -1
