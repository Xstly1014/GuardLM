#!/bin/bash
# M6 环境检查：项目路径 / 依赖版本 / GPU 状态
echo "=== data/eval ==="
ls /mnt/e/workspace_work/GuardLM/data/eval/ 2>/dev/null
echo "=== versions ==="
/root/guardlm-venv/bin/python - <<'PY'
import transformers, torch
print("transformers", transformers.__version__)
print("torch", torch.__version__)
try:
    import vllm
    print("vllm", vllm.__version__)
except ImportError:
    print("vllm: NOT INSTALLED")
try:
    import awq
    print("autoawq", awq.__version__)
except ImportError:
    print("autoawq: NOT INSTALLED")
PY
echo "=== GPU ==="
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
echo "=== llamafactory ==="
ls /root/LLaMA-Factory/ | head -5
