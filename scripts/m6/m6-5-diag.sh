#!/usr/bin/env bash
# M6-5: AWQ 评测停摆诊断
set -u
echo "== time =="; date
echo "== GPU =="; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
echo "== eval 进程 =="; ps aux | grep -E "harness.run" | grep -v grep | awk '{print $2, $3, $4, substr($0, index($0,$11), 80)}'
echo "== /v1/models =="; timeout 10 curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" http://localhost:8000/v1/models
echo "== 引擎日志尾 =="; ls /root/models/ >/dev/null && true
