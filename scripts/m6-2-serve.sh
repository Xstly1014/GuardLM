#!/bin/bash
# M6-2: 启动 vLLM 服务（guardlm-final bf16）
# 压测纪律: --no-enable-prefix-caching 防重测虚高（对比性压测必须干净）
# 用法: wsl bash /mnt/e/workspace_work/GuardLM/scripts/m6-2-serve.sh [--awq]
set -e
MODEL=${2:-/root/models/guardlm-final}
NAME=${1:-guardlm}

exec /root/serve-venv/bin/vllm serve "$MODEL" \
  --served-model-name "$NAME" \
  --max-model-len 512 \
  --gpu-memory-utilization 0.90 \
  --disable-log-requests \
  --no-enable-prefix-caching \
  --port 8000
