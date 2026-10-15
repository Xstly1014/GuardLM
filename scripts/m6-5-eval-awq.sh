#!/usr/bin/env bash
# M6-5: AWQ 掉点评测——650 条三档，VLLMBackend + 约束解码 ON（与 m6_tax_on 同协议）
# 前置: AWQ vLLM 服务已启动 (scripts/m6-2-serve.sh guardlm /root/models/guardlm-awq)
# 结论产出: reports/m6_awq.md；对比基线 reports/m6_tax_on.md (bf16)
cd /mnt/e/workspace_work/GuardLM
PY=/root/serve-venv/bin/python

$PY -m harness.run \
  --backend vllm --model guardlm --structured \
  --eval data/eval/ --tier T1,T2,T3 --no-think \
  --out reports/m6_awq.md \
  --tag "vLLM AWQ 4bit (awq_marlin), structured=ON"
echo "awq_eval exit=$?"
