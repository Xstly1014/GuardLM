#!/bin/bash
# M1-T3 试生成：每格 3 条，验证质量后再跑全量
cd /mnt/e/workspace_work/GuardLM
source /root/guardlm-venv/bin/activate
source configs/synth.env  # API key 在 gitignored env 文件中

python scripts/synthesize.py \
  --matrix configs/synth_matrix.yaml \
  --base-url "$SYNTH_BASE_URL" \
  --model "$SYNTH_MODEL" \
  --batch 10 \
  --limit-per-cell 3 \
  --out data/interim/synth.trial.jsonl \
  --log data/interim/synth.trial.log.jsonl
