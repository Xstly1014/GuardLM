# -*- coding: utf-8 -*-
"""M3: 注册 guardlm_dpo 偏好对数据集（ranking 格式）到 LLaMA-Factory。"""
import json

P = "/root/LLaMA-Factory/data/dataset_info.json"
ENTRY = {
    "file_name": "/mnt/e/workspace_work/GuardLM/data/rl/prefs.jsonl",
    "ranking": True,
    "columns": {
        "prompt": "instruction",
        "query": "input",
        "chosen": "chosen",
        "rejected": "rejected",
    },
}

info = json.load(open(P, encoding="utf-8"))
info["guardlm_dpo"] = ENTRY
json.dump(info, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("registered guardlm_dpo (ranking) ->", ENTRY["file_name"])
