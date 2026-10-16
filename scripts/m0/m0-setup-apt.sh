#!/bin/bash
set -e
cat > /etc/apt/sources.list <<'EOF'
deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy main restricted universe multiverse
deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-updates main restricted universe multiverse
deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-backports main restricted universe multiverse
deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-security main restricted universe multiverse
EOF
apt-get update -qq 2>&1 | tail -2
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq wget ca-certificates git curl bzip2 > /dev/null
echo "APT-SETUP-DONE"
git --version
curl --version | head -1
