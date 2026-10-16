#!/usr/bin/env bash
# M6-5: AWQ 挂起隔离测试 v2
# 区分三种假设:
#   A. marlin 内核挂起      -> Step1 挂起, GPU util 低
#   B. 宿主 GPU 环境干扰    -> Step1 慢但 180s 内返回, 采样有 util 异常
#   C. chat template 特有  -> Step1 OK, Step2 挂
set -uo pipefail   # 不用 -e: 即使某步失败也要继续观察
cd /mnt/e/workspace_work/GuardLM

echo "=== 清理旧服务 ==="
pkill -f 'vllm serve' 2>/dev/null && sleep 8 || true
nvidia-smi --query-gpu=memory.used --format=csv,noheader

echo "=== GPU 采样器（每 2s 记录 util/memory, 检测宿主干扰）==="
GPULOG=/tmp/gpu-samples.log
: > $GPULOG
( while true; do
    nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader >> $GPULOG
    sleep 2
  done ) &
SAMPLER=$!

echo "=== 启动 AWQ vLLM（setsid 脱离会话，防 SIGHUP 清理）==="
setsid /root/serve-venv/bin/vllm serve /root/models/guardlm-awq \
  --served-model-name guardlm \
  --max-model-len 512 \
  --gpu-memory-utilization 0.90 \
  --disable-log-requests \
  --no-enable-prefix-caching \
  --port 8000 >/tmp/awq-serve2.log 2>&1 < /dev/null &
echo "launcher pid=$!"

echo "=== 等待就绪 ==="
READY=0
for i in $(seq 1 90); do
  if curl -s -o /dev/null --max-time 2 http://localhost:8000/v1/models; then
    echo "server ready after ${i}x2s"; READY=1; break
  fi
  sleep 2
done
[ "$READY" = 1 ] || { echo "SERVER NOT READY"; kill $SAMPLER; exit 1; }
sleep 3

echo "=== Step1: /v1/completions 纯补全（绕过 chat template，180s 超时）==="
S1=$(date +%s)
timeout 180 curl -s http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"guardlm","prompt":"你是内容安全审核员。判定以下文本的风险类别并输出 JSON。\n今天天气真好\n输出：","max_tokens":48,"temperature":0.7,"top_p":0.8}' \
  > /tmp/step1.out 2>&1
E1=$?
echo "step1_exit=$E1 elapsed=$(( $(date +%s) - S1 ))s"
echo "step1_body: $(head -c 300 /tmp/step1.out)"
echo ""

echo "=== Step2: /v1/chat/completions（chat template 路径，180s 超时）==="
S2=$(date +%s)
timeout 180 curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"guardlm","messages":[{"role":"user","content":"你是内容安全审核员。判定以下文本的风险类别并输出 JSON。\n加我微信免费领福利"}],"max_tokens":48,"temperature":0.7,"top_p":0.8,"chat_template_kwargs":{"enable_thinking":false}}' \
  > /tmp/step2.out 2>&1
E2=$?
echo "step2_exit=$E2 elapsed=$(( $(date +%s) - S2 ))s"
echo "step2_body: $(head -c 300 /tmp/step2.out)"
echo ""

kill $SAMPLER 2>/dev/null
echo "=== GPU 采样统计（util 分布，检测宿主干扰窗口）==="
sort /tmp/gpu-samples.log | uniq -c | sort -rn | head -10
echo ""
echo "=== 引擎日志尾部 ==="
tail -15 /tmp/awq-serve2.log
echo "ISOLATE2_DONE"
