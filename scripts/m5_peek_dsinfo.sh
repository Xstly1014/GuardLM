#!/usr/bin/env bash
# M5: 查看 llamafactory dataset_info.json 现有注册（M2 SFT 的方式）
cat /root/LLaMA-Factory/data/dataset_info.json 2>/dev/null | head -40
