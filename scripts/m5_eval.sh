#!/usr/bin/env bash
# M5-4: 评测三件套
#   ① sft-v2 全档（T1/T2/T3 650 条，与 sft-v1 同口径）
#   ② sft-v2 P5 黑话探针（20 条留出词）
#   ③ sft-v1 P5 黑话探针（对比基线——CPT 前的起点）
set -e
cd /mnt/e/workspace_work/GuardLM
PY=/root/guardlm-venv/bin/python

echo "=== [1/3] sft-v2 全档评测 ==="
$PY -m harness.run \
  --model /root/saves/Qwen3-1.7B/guardlm-sft-v2 \
  --eval data/eval/ --tier T1,T2,T3 --no-think \
  --out reports/sft-v2.md --tag "sft-v2 (CPT起点)"

echo ""
echo "=== [2/3] sft-v2 P5 黑话探针 ==="
$PY -m harness.run \
  --model /root/saves/Qwen3-1.7B/guardlm-sft-v2 \
  --eval data/eval/ --tier P5 --no-think \
  --out reports/sft-v2.p5.md --tag "sft-v2 黑话探针"

echo ""
echo "=== [3/3] sft-v1 P5 黑话探针（基线）==="
$PY -m harness.run \
  --model /root/saves/Qwen3-1.7B/guardlm-sft-v1 \
  --eval data/eval/ --tier P5 --no-think \
  --out reports/sft-v1.p5.md --tag "sft-v1 黑话探针"

echo ""
echo "=== ALL DONE ==="
