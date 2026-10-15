#!/bin/bash
# M1-T3 全量合成：按矩阵 target 执行，约 495 条
cd /mnt/e/workspace_work/GuardLM
source /root/guardlm-venv/bin/activate
source configs/synth.env  # API key 在 gitignored env 文件中

python scripts/synthesize.py \
  --matrix configs/synth_matrix.yaml \
  --base-url "$SYNTH_BASE_URL" \
  --model "$SYNTH_MODEL" \
  --batch 10 \
  --out data/interim/synth.raw.jsonl \
  --log data/interim/synth.api_log.jsonl
