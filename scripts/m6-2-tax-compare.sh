#!/usr/bin/env bash
# M6-2: reasoning tax 对比——约束解码 ON/OFF 各跑一遍 Harness（650 条三档）
# 前置: vLLM 服务已启动 (scripts/m6-2-serve.sh)，served-model-name=guardlm
# 结论产出: reports/m6_tax_off.md / m6_tax_on.md，两列 F1 对比写入 experiments.md
cd /mnt/e/workspace_work/GuardLM
PY=/root/serve-venv/bin/python

echo "=== 约束解码 OFF（纯采样，M2 前四层容错兜底）==="
$PY -m harness.run \
  --backend vllm --model guardlm \
  --eval data/eval/ --tier T1,T2,T3 --no-think \
  --out reports/m6_tax_off.md \
  --tag "vLLM bf16, structured=OFF"
echo "tax_off exit=$?"

echo "=== 约束解码 ON（response_format json_schema，第 6 层）==="
$PY -m harness.run \
  --backend vllm --model guardlm --structured \
  --eval data/eval/ --tier T1,T2,T3 --no-think \
  --out reports/m6_tax_on.md \
  --tag "vLLM bf16, structured=ON"
echo "tax_on exit=$?"
