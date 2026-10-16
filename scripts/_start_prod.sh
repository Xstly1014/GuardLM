#!/usr/bin/env bash
# 启动生产形态: vLLM bf16 guardlm-final @ :8000 + 演示页 @ :7860
# 模式来源: m6-final-switch.sh（pkill+冷却防 WSL GPU 状态残留活锁, setsid 保活）
set -uo pipefail
cd /mnt/e/workspace_work/GuardLM

echo "=== 清理残留（如有）==="
pkill -f 'vllm serve' && echo "killed old vllm" || echo "no vllm running"
pkill -f 'VLLM::EngineCore' && echo "killed engine core" || echo "no engine core"
pkill -f 'demo.app:app' && echo "killed old demo" || echo "no demo running"

echo "=== 冷却 30s（EXP-006: WSL2 GPU 状态残留预防，必须遵守）==="
sleep 30
nvidia-smi --query-gpu=memory.used --format=csv,noheader

echo "=== 启动 vLLM bf16 生产形态（guardlm-final, setsid 保活）==="
setsid /root/serve-venv/bin/vllm serve /root/models/guardlm-final \
  --served-model-name guardlm \
  --max-model-len 512 \
  --gpu-memory-utilization 0.90 \
  --disable-log-requests \
  --no-enable-prefix-caching \
  --port 8000 >/tmp/bf16-serve.log 2>&1 < /dev/null &

echo "=== 启动演示页（uvicorn demo.app:app, setsid 保活）==="
setsid /root/serve-venv/bin/uvicorn demo.app:app \
  --host 0.0.0.0 --port 7860 >/tmp/demo-serve.log 2>&1 < /dev/null &

echo "=== 轮询 vLLM 就绪（给足 240s，NCCL 冷启动慢属正常）==="
READY=0
for i in $(seq 1 120); do
  if curl -s -o /dev/null --max-time 2 http://localhost:8000/v1/models; then
    echo "vllm ready after ${i}x2s"; READY=1; break
  fi
  sleep 2
done
[ "$READY" = 1 ] || { echo "SERVER NOT READY"; tail -15 /tmp/bf16-serve.log; exit 1; }

echo "=== 轮询演示页就绪 ==="
DREADY=0
for i in $(seq 1 30); do
  if curl -s -o /dev/null --max-time 2 http://localhost:7860/docs; then
    echo "demo ready after ${i}x2s"; DREADY=1; break
  fi
  sleep 2
done
[ "$DREADY" = 1 ] || { echo "DEMO NOT READY"; tail -15 /tmp/demo-serve.log; exit 1; }
sleep 2

echo "=== 演示页端到端验证（两示例）==="
curl -s --max-time 90 http://localhost:7860/moderate \
  -H "Content-Type: application/json" \
  -d '{"text":"加我微信免费领福利"}'
echo ""
curl -s --max-time 90 http://localhost:7860/moderate \
  -H "Content-Type: application/json" \
  -d '{"text":"今天天气真好"}'
echo ""
echo "PROD_START_DONE"
