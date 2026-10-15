#!/bin/bash
set -e
cat > /root/.condarc <<'EOF'
channels:
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
show_channel_urls: true
EOF
source /root/miniconda3/etc/profile.d/conda.sh
echo "CONDARC-DONE"
conda config --show channels
