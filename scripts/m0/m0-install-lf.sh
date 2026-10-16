#!/bin/bash
# M0-6 (v3b): install llamafactory itself + bitsandbytes, then verify.
set -e
source /root/guardlm-venv/bin/activate

echo "[1/3] Installing llamafactory source dir alone (deps already in place)..."
pip install --no-deps --no-index --no-build-isolation /root/LLaMA-Factory

echo "[2/3] Installing bitsandbytes (extras, not in resolver set)..."
pip install --no-deps --no-index --find-links=/root/wheels/lf-deps "bitsandbytes==0.45.3"

echo "[3/3] VERIFY"
llamafactory-cli version
python - <<'PYEOF'
import torch, transformers, peft, trl, accelerate, datasets, bitsandbytes
print('torch:', torch.__version__, '| cuda:', torch.cuda.is_available())
print('transformers:', transformers.__version__)
print('peft:', peft.__version__)
print('trl:', trl.__version__)
print('accelerate:', accelerate.__version__)
print('datasets:', datasets.__version__)
print('bitsandbytes:', bitsandbytes.__version__)
from transformers import AutoConfig
c = AutoConfig.from_pretrained('/root/models/Qwen3-1.7B')
print('Qwen3 config model_type:', c.model_type)
PYEOF
echo "M0-6 DONE"
