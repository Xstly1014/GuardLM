# -*- coding: utf-8 -*-
"""M2: 注册 guardlm_sft 数据集到 LLaMA-Factory 的 dataset_info.json。"""
import json

P = "/root/LLaMA-Factory/data/dataset_info.json"
ENTRY = {
    "file_name": "/mnt/e/workspace_work/GuardLM/data/sft/train.jsonl",
    "columns": {"prompt": "instruction", "query": "input", "response": "output"},
}

info = json.load(open(P, encoding="utf-8"))
info["guardlm_sft"] = ENTRY
json.dump(info, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("registered guardlm_sft ->", ENTRY["file_name"])
