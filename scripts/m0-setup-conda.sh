#!/bin/bash
set -e
if [ ! -d /root/miniconda3 ]; then
  echo "downloading miniconda..."
  wget -q https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh
  bash /tmp/miniconda.sh -b -p /root/miniconda3
fi
/root/miniconda3/bin/conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
/root/miniconda3/bin/conda config --set show_channel_urls yes
echo "CONDA-DONE"
/root/miniconda3/bin/conda --version
