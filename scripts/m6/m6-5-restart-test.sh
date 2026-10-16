#!/usr/bin/env bash
# M6-5: AWQ 服务重启 + 两步隔离测试（非约束 -> 约束）
# 用途: 区分「marlin 内核挂起」vs「structured x awq_marlin 活锁」vs「环境瞬时干扰」
set -euo pipefail
cd /mnt/e/workspace_work/GuardLM

echo "=== 等待旧引擎退出 ==="
sleep 8
nvidia-smi --query-gpu=memory.used --format=csv,noheader

echo "=== 启动 AWQ vLLM（后台）==="
/root/serve-venv/bin/vllm serve /root/models/guardlm-awq \
  --served-model-name guardlm \
  --max-model-len 512 \
  --gpu-memory-utilization 0.90 \
  --disable-log-requests \
  --no-enable-prefix-caching \
  --port 8000 >/tmp/awq-serve.log 2>&1 &
SRV=$!

echo "=== 等待就绪（轮询 /v1/models）==="
for i in $(seq 1 60); do
  if curl -s -o /dev/null --max-time 2 http://localhost:8000/v1/models; then
    echo "server ready after ${i}x2s"
    break
  fi
  sleep 2
done
sleep 3

echo "=== Step1: 非约束单请求（60s 超时，期望 <10s 返回）==="
timeout 60 curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"guardlm","messages":[{"role":"user","content":"你是内容安全审核员。判定以下文本的风险类别并输出 JSON。\n今天天气真好"}],"max_tokens":48,"temperature":0.7,"top_p":0.8,"chat_template_kwargs":{"enable_thinking":false}}' \
  | head -c 400
echo ""
echo "step1_exit=$?"

echo "=== Step2: 约束解码单请求（180s 超时，观察 grammar 编译是否 <=60s）==="
START=$(date +%s)
timeout 180 curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d @- <<'JSON' | head -c 400
{
  "model": "guardlm",
  "messages": [{"role": "user", "content": "你是内容安全审核员。判定以下文本的风险类别并输出 JSON。\n加我微信免费领福利"}],
  "max_tokens": 48, "temperature": 0.7, "top_p": 0.8,
  "chat_template_kwargs": {"enable_thinking": false},
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "verdict",
      "schema": {
        "type": "object",
        "properties": {
          "label": {"type": "string", "enum": ["insult", "porn", "ads", "illegal", "none"]},
          "risk": {"type": "number"},
          "reason": {"type": "string"}
        },
        "required": ["label", "risk", "reason"],
        "additionalProperties": false
      }
    }
  }
}
JSON
echo ""
echo "step2_exit=$? elapsed=$(( $(date +%s) - START ))s"
echo "ISOLATION_TEST_DONE (server still running, pid=$SRV)"
