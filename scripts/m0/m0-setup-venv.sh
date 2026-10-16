#!/bin/bash
set -e
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv python3-full > /dev/null 2>&1
python3 --version
if [ ! -d /root/guardlm-venv ]; then
  python3 -m venv /root/guardlm-venv
fi
source /root/guardlm-venv/bin/activate
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple > /dev/null
echo "installing torch cu121 ..."
pip install -q torch --index-url https://download.pytorch.org/whl/cu121
echo "TORCH-DONE"
python -c "import torch; print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available()); print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'); print('vram:', round(torch.cuda.get_device_properties(0).total_memory/1024**3,1), 'GB')"
