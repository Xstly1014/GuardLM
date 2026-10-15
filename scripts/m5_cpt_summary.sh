#!/usr/bin/env bash
# M5-2: CPT-v1 训练摘要（train metrics + 产物检查）
LOG=/mnt/e/workspace_work/GuardLM/logs/m5_cpt_v1.log

echo "=== train metrics（日志尾部）==="
tr '\r' '\n' < $LOG | grep -A 20 'train metrics' | head -25

echo ""
echo "=== 产物 ==="
ls -la /root/saves/Qwen3-1.7B/guardlm-cpt-v1/ | grep -v '^total'
