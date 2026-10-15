#!/bin/bash
# 验证 serve-venv 关键链路：vllm import + autoawq import + GPU 可见
/root/serve-venv/bin/python - <<'PY'
import warnings
warnings.filterwarnings("ignore")
import torch, transformers, vllm
print("torch", torch.__version__, "| transformers", transformers.__version__, "| vllm", vllm.__version__)
print("cuda:", torch.cuda.is_available(), torch.cuda.get_device_name(0))
import awq
print("autoawq", awq.__version__)
import json_repair, pydantic, openai, fastapi
print("web/harness deps ok")
PY
