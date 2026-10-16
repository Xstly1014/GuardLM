#!/usr/bin/env bash
# M6-1: guardlm-final 合并权重全量三档评测（与 M4 grpo-v1 指标对比，验证合并零损耗）
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python -m harness.run \
  --model /root/models/guardlm-final \
  --eval data/eval/ \
  --tier T1,T2,T3 --no-think \
  --out reports/guardlm-final.md \
  --tag "M6 merged final (grpo-v1 -> guardlm-final)"
echo "exit=$?"
