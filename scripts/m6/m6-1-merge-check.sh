#!/bin/bash
# M6-1: merge_check —— adapter 推理 vs 合并权重推理，50 条 T1 greedy 对比
set -e
/root/guardlm-venv/bin/python /mnt/e/workspace_work/GuardLM/scripts/m6/m6_merge_check.py 2>&1 | tee /mnt/e/workspace_work/GuardLM/logs/m6-merge-check.log
