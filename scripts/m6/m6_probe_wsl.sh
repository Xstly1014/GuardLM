#!/usr/bin/env bash
# M6-3 停摆归因：WSL 环境证据采集（dmesg GPU/驱动事件、系统负载）
set -u
echo "=== dmesg GPU/driver events ==="
dmesg 2>/dev/null | grep -iE "nvrm|drm|gpu|cuda|xid" | tail -20 || echo "(dmesg 不可读)"
echo "=== load / vCPU ==="
uptime
nproc
echo "=== top GPU procs (host side via nvidia-smi) ==="
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>/dev/null | head -10
nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used --format=csv 2>/dev/null
echo "=== clock ==="
date
