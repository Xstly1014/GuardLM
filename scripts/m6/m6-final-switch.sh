#!/usr/bin/env bash
# M6 收尾: 切换生产形态——停 AWQ 服务 -> 冷却(防 WSL GPU 状态残留活锁) -> 启动 bf16 -> 验证演示页
set -uo pipefail
cd /mnt/e/workspace_work/GuardLM

echo "=== 停止 AWQ 服务 ==="
pkill -f 'vllm serve' && echo "killed" || echo "no vllm running"

echo "=== 冷却 30s（WSL2 GPU 状态残留预防）==="
sleep 30
nvidia-smi --query-gpu=memory.used --format=csv,noheader

echo "=== 启动 bf16 生产形态（guardlm-final, setsid 保活）==="
setsid /root/serve-venv/bin/vllm serve /root/models/guardlm-final \
  --served-model-name guardlm \
  --max-model-len 512 \
  --gpu-memory-utilization 0.90 \
  --disable-log-requests \
  --no-enable-prefix-caching \
  --port 8000 >/tmp/bf16-serve.log 2>&1 < /dev/null &

echo "=== 轮询就绪（给足 240s，NCCL 冷启动慢属正常）==="
READY=0
for i in $(seq 1 120); do
  if curl -s -o /dev/null --max-time 2 http://localhost:8000/v1/models; then
    echo "vllm ready after ${i}x2s"; READY=1; break
  fi
  sleep 2
done
[ "$READY" = 1 ] || { echo "SERVER NOT READY"; tail -5 /tmp/bf16-serve.log; exit 1; }
sleep 3

echo "=== 演示页判定验证（demo :7860 三示例）==="
R=$(curl -s --max-time 90 http://localhost:7860/api/judge \
  -H "Content-Type: application/json" \
  -d '{"text":"加我微信免费领福利"}')
echo "ads-example: $R"
R2=$(curl -s --max-time 90 http://localhost:7860/api/judge \
  -H "Content-Type: application/json" \
  -d '{"text":"今天天气真好"}')
echo "none-example: $R2"
echo "M6_FINAL_SWITCH_DONE"
