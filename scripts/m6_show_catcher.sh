#!/usr/bin/env bash
# 定位 autoawq Catcher 实现（M6-5 兼容性补丁前置侦察）
set -u
F=/root/serve-venv/lib/python3.10/site-packages/awq/quantize/quantizer.py
grep -n "class Catcher" -A 25 "$F"
