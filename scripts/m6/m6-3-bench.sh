#!/usr/bin/env bash
# M6-3 压测 runner：预热 -> structured ON（生产配置）-> structured OFF（对照）
# 纪律：in-flight 并发受信号量控制；prefix caching 已在服务端关闭；
#       每档并发 3 轮取中位数；客户端与服务同机（WSL2）如实记录。
set -euo pipefail
cd /mnt/e/workspace_work/GuardLM
PY=/root/guardlm-venv/bin/python

echo "=== warmup structured ON (grammar compile / cuda graph, excluded from stats) ==="
$PY bench/press.py --num-prompts 3 --concurrency 1 --rounds 1 --structured \
  -o /tmp/bench_warmup1.md >/dev/null
echo "=== warmup structured OFF ==="
$PY bench/press.py --num-prompts 3 --concurrency 1 --rounds 1 \
  -o /tmp/bench_warmup2.md >/dev/null

echo "=== BENCH: structured ON (production config) ==="
$PY bench/press.py --structured --rounds 3 -o reports/bench.md

echo "=== BENCH: structured OFF (control) ==="
$PY bench/press.py --rounds 3 -o reports/bench.md

rm -f /tmp/bench_warmup1.md /tmp/bench_warmup2.md
echo "ALL_BENCH_DONE"
