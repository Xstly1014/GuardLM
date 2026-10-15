#!/bin/bash
# M6-2: vllm 安装（固定版本防依赖回溯；输出全量日志便于排查）
set -e
export LOG=/mnt/e/workspace_work/GuardLM/logs/m6-serve-env.log

echo "=== install vllm (pinned) ===" | tee -a "$LOG"
/root/serve-venv/bin/pip install "vllm==0.12.0" --progress-bar off 2>&1 | tail -5 | tee -a "$LOG"

echo "=== install web + harness deps ===" | tee -a "$LOG"
/root/serve-venv/bin/pip install autoawq fastapi "uvicorn[standard]" openai json_repair --progress-bar off 2>&1 | tail -3 | tee -a "$LOG"

echo "=== versions ===" | tee -a "$LOG"
/root/serve-venv/bin/python - <<'PY' 2>&1 | tee -a /mnt/e/workspace_work/GuardLM/logs/m6-serve-env.log
import torch, transformers
print("torch", torch.__version__)
print("transformers", transformers.__version__)
import vllm
print("vllm", vllm.__version__)
try:
    import awq
    print("autoawq", awq.__version__)
except ImportError as e:
    print("autoawq FAIL:", e)
PY
echo "DONE" | tee -a "$LOG"
