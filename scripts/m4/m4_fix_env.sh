#!/usr/bin/env bash
# 修复 trl 升级造成的依赖冲突: transformers 5.19 与 torch 2.5 不兼容
# 目标组合: trl 0.21 (GRPOTrainer) + transformers 4.56 + datasets 3.6 + hub 0.36
set -e
/root/guardlm-venv/bin/pip install -q \
  "trl==0.21.0" "transformers==4.56.1" "datasets==3.6.0" \
  "huggingface-hub==0.36.0" "tokenizers>=0.22,<0.23" 2>&1 | tail -3
/root/guardlm-venv/bin/python - <<'EOF'
import torch, transformers, trl, datasets, peft
print("torch", torch.__version__, "| transformers", transformers.__version__,
      "| trl", trl.__version__, "| datasets", datasets.__version__,
      "| peft", peft.__version__)
from trl import GRPOTrainer, GRPOConfig
print("GRPOTrainer OK")
from transformers import AutoModelForCausalLM, AutoTokenizer
print("transformers core OK")
EOF
