#!/usr/bin/env bash
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python - <<'PYEOF'
import json, random
rows = [json.loads(l) for l in open('data/cpt/slang.jsonl', encoding='utf-8')]
random.seed(7)
for r in random.sample(rows, 30):
    print(f"{r['cat'][:4]} {r['word']} | {r['text']}")
PYEOF
