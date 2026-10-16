#!/usr/bin/env bash
# M4-3: grpo-v1 训练监控（五指标抽取）
LOG=/root/logs/grpo-v1-train.log
echo "== progress =="
tail -c 200 "$LOG"
echo ""
echo "== last-5 entropy =="
grep -o "'entropy': [0-9.]*" "$LOG" | tail -5
echo "== last-5 reward =="
grep -o "'reward': [0-9.]*" "$LOG" | tail -5
echo "== last-5 frac_zero_std =="
grep -o "'frac_reward_zero_std': [0-9.]*" "$LOG" | tail -5
echo "== last-5 kl =="
grep -o "'kl': [0-9.e-]*" "$LOG" | tail -5
echo "== last-5 completion_len =="
grep -o "'completions/mean_length': [0-9.]*" "$LOG" | tail -5
echo "== reward trend (every 30 steps) =="
grep -o "'reward': [0-9.]*" "$LOG" | awk 'NR % 30 == 1 {print NR": "$0}'
