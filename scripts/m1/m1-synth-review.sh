#!/bin/bash
cd /mnt/e/workspace_work/GuardLM
source /root/guardlm-venv/bin/activate

# 生成合成样本人审表：495 条抽 50 条
python scripts/common/sample_review.py data/interim/synth.raw.jsonl -n 50 \
  -o review/m1_synth_review.md --kind synth
