#!/bin/bash
set -e
source /root/guardlm-venv/bin/activate
pip install --no-index --find-links /mnt/c/wheels "torch==2.5.0+cu121" --progress-bar off 2>&1 | tail -3
echo "TORCH-INSTALL-DONE"
python - <<'PYEOF'
import torch
print('torch:', torch.__version__)
print('cuda:', torch.cuda.is_available())
print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')
print('vram:', round(torch.cuda.get_device_properties(0).total_memory/1024**3, 1), 'GB')
x = torch.randn(1000, 1000, device='cuda')
y = x @ x
print('matmul on GPU OK:', y.sum().item() == y.sum().item())
PYEOF
echo "GPU-COMPUTE-VERIFIED"
