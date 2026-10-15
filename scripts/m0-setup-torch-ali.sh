#!/bin/bash
set -e
source /root/guardlm-venv/bin/activate
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple > /dev/null
echo "installing torch 2.5.0+cu121 from aliyun mirror ..."
pip install --progress-bar off "torch==2.5.0+cu121" -f https://mirrors.aliyun.com/pytorch-wheels/cu121/ --timeout 60 2>&1 | grep -v '^\s*$' | tail -5
echo "TORCH-DONE"
python -c "import torch; print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available()); print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'); print('vram:', round(torch.cuda.get_device_properties(0).total_memory/1024**3,1), 'GB')"
