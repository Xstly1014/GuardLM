#!/usr/bin/env bash
# M5: 查看 guardlm_sft 注册条目（确认文件路径引用方式）
grep -A3 'guardlm_sft' /root/LLaMA-Factory/data/dataset_info.json
