#!/bin/bash
set -e
source /root/miniconda3/etc/profile.d/conda.sh
conda env list | grep -q "^guardlm " || conda create -n guardlm python=3.10 -y -q
conda activate guardlm
echo "python: $(python --version)"
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple > /dev/null
echo "installing torch cu121 ..."
pip install -q torch --index-url https://download.pytorch.org/whl/cu121
echo "TORCH-DONE"
python -c "import torch; print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available()); print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'); print('vram:', round(torch.cuda.get_device_properties(0).total_memory/1024**3,1), 'GB')"
