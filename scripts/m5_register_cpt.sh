#!/usr/bin/env bash
# M5-2: 注册 guardlm_cpt 数据集到 llamafactory dataset_info.json（幂等）
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python - <<'PYEOF'
import json
P = '/root/LLaMA-Factory/data/dataset_info.json'
cfg = json.load(open(P, encoding='utf-8'))
cfg['guardlm_cpt'] = {
    "file_name": "/mnt/e/workspace_work/GuardLM/data/cpt/cpt_corpus.jsonl",
    "columns": {"prompt": "text"}
}
json.dump(cfg, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('registered guardlm_cpt:', json.dumps(cfg['guardlm_cpt'], ensure_ascii=False))
PYEOF
