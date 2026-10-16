#!/bin/bash
# 查看 merge_check 中翻转的 2 条样本（idx 14, 33）
python3 - <<'PY'
import json
rows = [json.loads(l) for l in open('/mnt/e/workspace_work/GuardLM/data/eval/t1.jsonl', encoding='utf-8') if l.strip()]
for i in (14, 33):
    r = rows[i]
    print(f"--- idx {i} | gold={r['gold']['label']} ---")
    print(r['input'])
PY
echo "=== merge_check diff 明细 ==="
python3 -c "import json; d=json.load(open('/mnt/e/workspace_work/GuardLM/reports/artifacts/m6_merge_check.json')); print(json.dumps(d['diffs'], ensure_ascii=False, indent=1))"
