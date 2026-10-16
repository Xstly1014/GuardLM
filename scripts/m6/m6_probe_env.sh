#!/usr/bin/env bash
# M6-3 压测前环境探针：定位 venv + 校验 aiohttp
set -u
for v in /mnt/e/workspace_work/GuardLM/venv /root/GuardLM/venv /root/guardlm-venv /mnt/e/workspace_work/GuardLM/.venv; do
  if [ -f "$v/bin/activate" ]; then
    echo "VENV_FOUND=$v"
  fi
done
which python3
python3 -c "import aiohttp" 2>/dev/null && echo "SYSTEM aiohttp OK" || echo "SYSTEM aiohttp MISSING"
