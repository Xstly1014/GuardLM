#!/bin/bash
# 轮询 vLLM 服务直到就绪（最长 8 分钟）
for i in $(seq 1 96); do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:8000/v1/models 2>/dev/null)
  if [ "$code" = "200" ]; then
    echo "vLLM READY after ${i}x5s"
    curl -s http://localhost:8000/v1/models | head -c 200
    exit 0
  fi
  sleep 5
done
echo "TIMEOUT waiting for vLLM"
exit 1
