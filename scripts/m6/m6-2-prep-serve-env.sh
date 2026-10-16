#!/bin/bash
# M6-2: 准备部署环境（独立 serve-venv，与训练 venv 隔离）
# 检查 pip 源配置与网络
echo "=== pip config ==="
/root/guardlm-venv/bin/pip config list 2>/dev/null
cat ~/.pip/pip.conf 2>/dev/null
cat /etc/pip.conf 2>/dev/null
echo "=== 网络连通 ==="
timeout 8 curl -sI https://mirrors.aliyun.com/pypi/simple/ | head -1
timeout 8 curl -sI https://pypi.tuna.tsinghua.edu.cn/simple/ | head -1
echo "=== 磁盘 ==="
df -h /root | tail -1
