#!/usr/bin/env bash
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python - <<'PYEOF'
import json
with open('data/eval/t1.jsonl', encoding='utf-8') as f:
    r = json.loads(f.readline())
print(json.dumps(r, ensure_ascii=False, indent=1)[:600])
PYEOF
