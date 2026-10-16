#!/usr/bin/env bash
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python - <<'PYEOF'
import json
with open('data/raw/cvalues.jsonl', encoding='utf-8') as f:
    r = json.loads(f.readline())
print('keys:', list(r.keys()))
for k, v in r.items():
    s = str(v)
    print(f'  {k}: {s[:80]}')
PYEOF
